from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import re

from device_state_summary import device_attributes, is_light_device, room_name
from device_target_resolver import normalized_name, resolve_device_candidate
from mcp_client import HubitatMCPClient, MCPToolResult
from mcp_client import tool_succeeded as _shared_tool_succeeded
from request_metrics import increment_active_metric
from time_expressions import strip_trailing_time


logger = logging.getLogger("HomeBrainOS.DeviceControl")
DEVICE_CONTROL_TOOL = "homebrain_control_devices"

# hub_list_devices (via the hub_read_devices gateway) only reliably returns
# capability data -- what _is_switch_device()/is_light_device() key off of
# to tell a light apart from a thermostat radiator valve that also happens
# to advertise "Switch" -- when a field list is explicitly requested. The
# short-lived-cache path in mcp_client.py's get_cached_devices() already
# asks for this; the room-wide and labelFilter-scoped lookups below did
# not, and on a real Hubitat/Matter-bridge deployment that meant those
# lookups came back without a "capabilities" field at all. That silently
# emptied the kind-filtered `eligible`/`candidates` lists for every light
# resolved through this path (device_kind="auto" -- see _matches_kind()),
# defeating the "trust a narrow, real ambiguous result" fix in 0.10.385:
# the narrow lookup still reported finding the right devices, but they all
# failed the (capabilities-blind) kind check, so the guard's `not eligible`
# was true anyway and the broad, noisy full-manifest retry fired regardless.
_DEVICE_LOOKUP_FIELDS = [
    "id", "name", "label", "room", "capabilities", "attributes", "commands",
]

# A second, unrelated action can arrive smuggled onto the end of a
# device_names entry the same way a time expression can (see
# strip_trailing_time above and its call site below) -- e.g. "toilet light
# and restart the hub" reaching this tool as a single device_names entry
# instead of two separate tool calls, because the model folded the whole
# sentence into one call. Executing the routine part on the *whole*
# uncleaned string corrupts device resolution (nothing named "toilet light
# and restart the hub" exists); silently dropping the trailing clause and
# saying nothing would hide that a second action was requested and never
# happened. Detect and strip only a short, closed list of recognisably
# distinct actions -- restart/reboot the hub, lock/unlock a door, arm/
# disarm the alarm -- so the routine action still runs correctly, and the
# result carries a clear note that the second action needs its own request.
# This never executes the second action itself: doing that from a regex
# match on raw text, rather than a model-selected tool call, would be
# exactly the kind of prompt-text-gated mutation this codebase's own rules
# forbid (see CONTRIBUTING.md / CLAUDE.md: gate on structured tool calls,
# never on prompt wording).
_TRAILING_UNRELATED_ACTION = re.compile(
    r"^(?P<target>.*?\S)\s+and\s+"
    r"(?P<action>(?:restart|reboot)\s+the\s+hub"
    r"|(?:lock|unlock)\s+the\s+(?:front\s+|back\s+|garage\s+)?door"
    r"|(?:arm|disarm)\s+the\s+alarm)"
    r"\s*$",
    re.I,
)


def strip_trailing_unrelated_action(text: str) -> tuple[str, str | None]:
    """Split off a recognisably distinct second action, if present.

    Returns the cleaned target text and a human-readable description of the
    stripped action (or ``None`` if nothing matched). Only ever called on
    text already destined for device-name resolution -- never used to
    decide whether to execute anything.
    """

    match = _TRAILING_UNRELATED_ACTION.match(str(text).strip())
    if match is None:
        return str(text).strip(), None
    return match.group("target").strip(" ,."), match.group("action").strip()


# A bare, room-less "turn off the lights" carries no specific device or room
# name at all -- it means every light in the house. Live-observed regression:
# this fell straight into ordinary per-name fuzzy resolution (the same path
# that handles "turn off Bedroom1 Light"), which has nothing labelled "the
# lights" to match, so it reported "Unresolved" with an unrelated
# disambiguation offer instead of doing the obviously intended thing. This is
# deliberately a closed set of unqualified aggregate phrasings, not a loose
# keyword match -- "turn off the office lights" or "turn off Kitchen Light"
# must keep going through ordinary room/name resolution untouched.
_ALL_LIGHTS_TARGET_NAMES = {
    "the lights", "the light", "all lights", "all the lights",
    "all of the lights", "every light", "all my lights",
}


def is_all_lights_target(name: str) -> bool:
    """True when ``name`` is an unqualified "every light in the house" phrase."""

    return str(name).strip().casefold() in _ALL_LIGHTS_TARGET_NAMES


# "turn off all lights except bedroom 2 and bedroom 3" carries a base
# all-lights phrase plus an exclusion clause neither is_all_lights_target
# nor ordinary per-name resolution has any concept of -- live-observed
# gap: without this, the whole string ("all lights except bedroom 2 and
# bedroom 3") reaches per-name fuzzy resolution as one literal device
# name, matches nothing, and fails exactly like the bare "the lights" bug
# this same file fixed in 0.10.382. This is deliberately narrow: it only
# recognises "except"/"excluding"/"but not"/"other than" directly after
# the base phrase, and the caller (execute(), below) only acts on the
# split when the base phrase itself is a genuine is_all_lights_target
# match -- "turn off Bedroom 1 except the lamp" does not go through this
# path at all, it keeps using ordinary room resolution untouched.
_EXCLUSION_CLAUSE = re.compile(
    r"^(?P<base>.+?)\s+(?:except(?:\s+for)?|excluding|but\s+not|other\s+than)\s+"
    r"(?P<excluded>.+)$",
    re.I,
)
_LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+", re.I)


def split_all_lights_exclusion(name: str) -> tuple[str, list[str]]:
    """Split "all lights except X[, Y and Z]" into (base phrase, excluded terms).

    Returns the original text unchanged with an empty exclusion list when
    no "except"/"excluding"/"but not"/"other than" clause is present.
    """

    match = _EXCLUSION_CLAUSE.match(str(name).strip())
    if match is None:
        return str(name).strip(), []
    base = match.group("base").strip()
    excluded_text = match.group("excluded").strip()
    # A comma-separated list's last item is very often prefixed with "and"/
    # "or" too ("A, B, and C" / "A, B and C") -- splitting on comma and on
    # " and "/" or " as fully independent alternatives leaves that last
    # item as "and C" instead of "C" whenever a comma directly precedes it,
    # since the comma-match already consumes the separating whitespace.
    # Allowing an optional trailing "and "/"or " right after the comma
    # match handles both the Oxford-comma and plain-comma forms the same
    # way as a bare " and "/" or " between exactly two items.
    parts = re.split(
        r"\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+", excluded_text, flags=re.I
    )
    excluded = [part.strip(" .") for part in parts if part.strip(" .")]
    return base, excluded


def _human_join(items: list[str]) -> str:
    values = [str(item) for item in items if str(item).strip()]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def resolve_all_lights_exclusions(
    excluded_terms: list[str],
    identity_manifest: list[dict[str, Any]],
) -> tuple[set[str], list[str]]:
    """Resolve each excluded term to real device IDs via room or device match.

    A term matching a real room name (e.g. "bedroom 2") excludes every
    device in that room; otherwise it is resolved like an ordinary device
    name (e.g. "the toilet light"). Returns ``(excluded_device_ids,
    unresolved_terms)`` -- an unresolved term is reported back to the
    caller rather than silently dropped, because silently including a
    device the user explicitly asked to exclude would be worse than
    refusing the whole command outright.
    """

    excluded_ids: set[str] = set()
    unresolved: list[str] = []
    room_index: dict[str, list[dict[str, Any]]] = {}
    for device in identity_manifest:
        room = room_name(device)
        if room:
            room_index.setdefault(normalized_name(room), []).append(device)
    for raw_term in excluded_terms:
        term = _LEADING_ARTICLE.sub("", raw_term.strip()).strip()
        normalized_term = normalized_name(term)
        matched = False
        if normalized_term and normalized_term in room_index:
            for device in room_index[normalized_term]:
                device_id = str(device.get("id") or device.get("deviceId") or "")
                if device_id:
                    excluded_ids.add(device_id)
            matched = True
        elif term:
            resolution = resolve_device_candidate(term, identity_manifest)
            if resolution.target is not None:
                device_id = str(
                    resolution.target.get("id") or resolution.target.get("deviceId") or ""
                )
                if device_id:
                    excluded_ids.add(device_id)
                matched = True
        if not matched:
            unresolved.append(raw_term.strip())
    return excluded_ids, unresolved


class DeviceControlService:
    """Resolve and execute routine light/switch controls deterministically."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence

    @staticmethod
    def _tool_succeeded(result: MCPToolResult) -> bool:
        # Delegates to the shared implementation in mcp_client.py so this
        # and DeviceQueryService's identically-named method can never
        # diverge again -- see tool_succeeded()'s docstring for the
        # partial-failure bug this closes.
        return _shared_tool_succeeded(result)

    @staticmethod
    def _is_switch_device(device: dict[str, Any]) -> bool:
        capabilities = device.get("capabilities") or []
        if isinstance(capabilities, dict):
            capabilities = list(capabilities)
        elif isinstance(capabilities, str):
            capabilities = [capabilities]
        capability_text = " ".join(
            str(item.get("name") if isinstance(item, dict) else item)
            for item in capabilities
        ).casefold()
        return "switch" in capability_text

    def _matches_kind(self, kind: str, device: dict[str, Any]) -> bool:
        """True when ``device`` belongs to the requested ``device_kind``.

        ``"light"`` and ``"switch"`` are each a precise, single capability
        check, but ``"auto"`` -- the device_kind every plain "turn on/off
        <name>" request actually carries, see routine_control_arguments()
        -- means "either one", not "only a non-light switch". This must
        stay the single source of truth for that three-way rule: an
        earlier version of this file had two copies of a two-way version
        (light vs. switch-and-not-light) scattered across the live-lookup
        fallback paths below, silently dropping every light-capable device
        whenever kind was "auto" and resolution had to fall back to a live
        hub_read_devices call instead of the identity cache. Live-observed
        regression: "turn on livingroom light" (ambiguous between two real
        lights, forcing exactly that fallback) ended up dispatching to
        "Livingroom TRV" -- a thermostat radiator valve that happens to
        also advertise Switch, the nearest fuzzy match once every real
        light had already been filtered out of the candidate pool it was
        matched against.
        """

        if kind == "light":
            return is_light_device(device)
        if kind == "switch":
            return self._is_switch_device(device) and not is_light_device(device)
        return self._is_switch_device(device) or is_light_device(device)

    async def execute(
        self, arguments: dict[str, Any]
    ) -> MCPToolResult:
        room = str(arguments.get("room") or "").strip()
        names = arguments.get("device_names") or []
        kind = str(arguments.get("device_kind") or "").strip().lower()
        command = str(arguments.get("command") or "").strip()
        if (
            bool(room) == bool(names)
            or not isinstance(names, list)
            or kind not in {"auto", "light", "switch"}
            or command not in {"on", "off", "toggle"}
        ):
            return MCPToolResult(
                DEVICE_CONTROL_TOOL,
                arguments,
                {},
                "Invalid control arguments",
                {
                    "success": False,
                    "error": (
                        "Provide exactly one of room or device_names, plus a valid "
                        "device_kind and command."
                    ),
                },
                is_error=True,
            )

        # A second, unrelated action (restart the hub, lock/unlock a door,
        # arm/disarm the alarm) can arrive smuggled onto the end of `room`
        # or a `device_names` entry when the model folds a whole compound
        # sentence into one tool call instead of issuing two. Strip it
        # before resolution so the routine action still runs correctly
        # against a clean device name, and remember what was stripped so
        # the result can tell the user it needs its own separate request --
        # never execute the stripped action itself; see
        # strip_trailing_unrelated_action's docstring for why.
        stripped_action_note: str | None = None
        if room:
            cleaned, detected = strip_trailing_unrelated_action(room)
            if detected is not None:
                room = cleaned
                stripped_action_note = detected
        else:
            cleaned_entries: list[str] = []
            for item in names:
                cleaned, detected = strip_trailing_unrelated_action(str(item))
                cleaned_entries.append(cleaned)
                if detected is not None and stripped_action_note is None:
                    stripped_action_note = detected
            names = cleaned_entries

        # A time expression can arrive smuggled into `room` or a
        # `device_names` entry (e.g. "hallway lights at 11:11pm") when the
        # model has no dedicated time parameter to put it in. Executing
        # immediately would silently do something the person didn't ask
        # for -- turn the device on *now* instead of at the time they
        # specified -- and leaving the raw time text in the name corrupts
        # device resolution instead of failing honestly. Detect and refuse
        # with a clear explanation rather than either.
        time_source = room if room else " ".join(str(item) for item in names)
        _, requested_time = strip_trailing_time(time_source)
        if requested_time is not None:
            cleaned_room = strip_trailing_time(room)[0] if room else ""
            cleaned_names = [strip_trailing_time(str(item))[0] for item in names]
            target_description = cleaned_room or ", ".join(
                item for item in cleaned_names if item
            )
            # RuleAuthoringService (see rule_authoring_service.py) is the
            # primary handler for "<action> at <time>" requests and runs
            # earlier in the pipeline, before the model can reach this local
            # tool at all -- this branch is now a last-resort guard for the
            # narrower case where the model itself calls this tool directly
            # with a time smuggled into device_names/room (e.g. phrasing
            # RuleAuthoringService's stricter grammar didn't match). It must
            # still refuse rather than silently execute now or drop the time.
            return MCPToolResult(
                DEVICE_CONTROL_TOOL,
                arguments,
                {},
                "One-time scheduled action requested; not executed immediately",
                {
                    "success": False,
                    "error": (
                        f"This reads as a scheduled request for {requested_time} "
                        "rather than right now, but I could not turn it into a "
                        "rule automatically. Try rephrasing as "
                        f"'turn {target_description or 'this'} {command} at "
                        f"{requested_time}' for a one-time action, or add "
                        "'every day' for a recurring one -- or I can turn "
                        f"{target_description or 'this'} {command} immediately "
                        "instead."
                    ),
                    "requested_time": requested_time,
                    "device_names": cleaned_names or None,
                    "room": cleaned_room or None,
                },
                is_error=True,
            )

        identity_started = time.monotonic()
        identity_manifest: list[dict[str, Any]] = []
        try:
            identity_reader = getattr(
                self.mcp, "get_device_identities", self.mcp.get_cached_devices
            )
            identity_manifest = [
                device
                for device in (await identity_reader() or [])
                if isinstance(device, dict)
            ]
        except Exception as exc:
            logger.warning("Fast control identity lookup unavailable: %s", exc)
        identity_candidates = [
            device for device in identity_manifest if self._matches_kind(kind, device)
        ]
        # A single device_names entry can be a room name rather than a
        # device name -- the model has no dedicated slot to distinguish
        # "turn off Bedroom 1" (a room-wide action) from "turn off Bedroom1
        # Light" (one device), and resolve_device_candidate's ordinary
        # fuzzy matching has no room-awareness at all. This is a real,
        # observed bug: a smart plug literally labelled "Bedroom1 (MQTT)"
        # normalizes to the exact same string as the room "Bedroom 1"
        # (parenthetical qualifiers are stripped before comparison), so
        # per-name resolution silently picked that one unrelated device
        # instead of acting on the room -- the opposite of what "turn off
        # Bedroom 1" overwhelmingly means in natural speech. When a bare
        # device_names entry exactly matches a real room name, prefer the
        # room-wide interpretation deterministically (grounded in real
        # inventory data, not a guess): even in the rare case a device
        # happens to share that exact normalized name, it is very unlikely
        # to be what "turn off <room name>" was asking for.
        all_lights_requested = False
        excluded_ids: set[str] = set()
        if not room and len(names) == 1:
            candidate_room = str(names[0]).strip()
            wanted_candidate = normalized_name(candidate_room)
            room_names_present = {
                normalized_name(room_name(device))
                for device in identity_manifest
                if room_name(device)
            }
            if wanted_candidate and wanted_candidate in room_names_present:
                room = candidate_room
                names = []
            else:
                base_phrase, excluded_terms = split_all_lights_exclusion(candidate_room)
                if is_all_lights_target(base_phrase):
                    all_lights_requested = True
                    if excluded_terms:
                        excluded_ids, unresolved = resolve_all_lights_exclusions(
                            excluded_terms, identity_manifest
                        )
                        if unresolved:
                            error_message = (
                                f"I could not find {_human_join(unresolved)} to "
                                "exclude, so nothing was changed. Check the room "
                                "or device name and try again."
                            )
                            data = {
                                "success": False,
                                "error": error_message,
                                "matched": [],
                                "executed": 0,
                            }
                            return MCPToolResult(
                                DEVICE_CONTROL_TOOL, arguments, {}, error_message, data,
                                is_error=True,
                            )
        fast_targets: list[dict[str, Any]] = []
        if room:
            wanted_room = normalized_name(room)
            fast_targets = [
                device
                for device in identity_candidates
                if normalized_name(room_name(device)) == wanted_room
            ]
            fast_resolution_complete = bool(fast_targets)
        elif all_lights_requested:
            fast_targets = [
                device for device in identity_manifest
                if isinstance(device, dict)
                and is_light_device(device)
                and str(device.get("id") or device.get("deviceId") or "") not in excluded_ids
            ]
            fast_resolution_complete = bool(fast_targets)
        else:
            fast_resolution_complete = True
            for requested in names:
                resolution = resolve_device_candidate(
                    str(requested), identity_candidates
                )
                if resolution.target is None:
                    fast_resolution_complete = False
                    fast_targets = []
                    break
                target = dict(resolution.target)
                target["_resolved_label"] = resolution.matched_name
                fast_targets.append(target)
        if fast_resolution_complete:
            self._record_evidence(
                "hub_read_devices",
                {
                    "tool": "hub_list_devices",
                    "source": "identity_cache",
                },
                success=True,
                elapsed_ms=round(
                    (time.monotonic() - identity_started) * 1000
                ),
                summary=f"{len(fast_targets)} cached target candidates",
                supports_live_claim=False,
                evidence_kind="control_target_resolution",
            )

        lookup_arguments = (
            []
            if fast_resolution_complete
            else (
                [
                    {
                        "tool": "hub_list_devices",
                        "args": {"fields": list(_DEVICE_LOOKUP_FIELDS)},
                    }
                ]
                if room or all_lights_requested
                else [
                    {
                        "tool": "hub_list_devices",
                        "args": {
                            "labelFilter": str(requested),
                            "fields": list(_DEVICE_LOOKUP_FIELDS),
                        },
                    }
                    for requested in names
                ]
            )
        )

        async def lookup(
            source_arguments: dict[str, Any]
        ) -> tuple[MCPToolResult, int]:
            started = time.monotonic()
            source = await self.mcp.call_tool(
                "hub_read_devices", source_arguments
            )
            return source, round((time.monotonic() - started) * 1000)

        sources = await asyncio.gather(
            *(lookup(source_arguments) for source_arguments in lookup_arguments)
        )
        devices: list[dict[str, Any]] = []
        source_groups: list[list[dict[str, Any]]] = []
        lookup_errors: list[str] = []
        seen_source_ids: set[str] = set()
        for source_arguments, (source, elapsed_ms) in zip(
            lookup_arguments, sources, strict=True
        ):
            source_devices = [
                item
                for item in (
                    HubitatMCPClient._find_device_list(source.data) or []
                )
                if isinstance(item, dict)
            ]
            source_groups.append(source_devices)
            succeeded = self._tool_succeeded(source)
            self._record_evidence(
                "hub_read_devices",
                source_arguments,
                success=succeeded,
                elapsed_ms=elapsed_ms,
                summary=f"{len(source_devices)} target candidates",
                supports_live_claim=False,
                evidence_kind="control_target_resolution",
            )
            if not succeeded:
                lookup_errors.append(
                    source.text or "Hubitat target lookup failed."
                )
                continue
            for device in source_devices:
                source_id = str(
                    device.get("id") or device.get("deviceId") or id(device)
                )
                if source_id not in seen_source_ids:
                    seen_source_ids.add(source_id)
                    devices.append(device)
        if lookup_errors:
            data = {
                "success": False,
                "error": " ".join(lookup_errors),
                "matched": [],
                "executed": 0,
            }
            return MCPToolResult(
                DEVICE_CONTROL_TOOL, arguments, {}, json.dumps(data), data,
                is_error=True,
            )

        candidates = [
            device for device in devices
            if (
                is_light_device(device)
                if all_lights_requested
                else self._matches_kind(kind, device)
            )
            and (
                not all_lights_requested
                or str(device.get("id") or device.get("deviceId") or "") not in excluded_ids
            )
        ]
        targets: list[dict[str, Any]] = list(fast_targets)
        resolution_errors: list[str] = []
        resolution_choices: set[str] = set()
        if not targets and all_lights_requested:
            targets = list(candidates)
            if not targets:
                started = time.monotonic()
                try:
                    manifest = await self.mcp.get_cached_devices()
                except Exception as exc:
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=False,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=f"All-lights identity manifest unavailable: {exc}",
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                else:
                    light_candidates = [
                        device
                        for device in (manifest or [])
                        if isinstance(device, dict)
                        and is_light_device(device)
                        and str(device.get("id") or device.get("deviceId") or "") not in excluded_ids
                    ]
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=True,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=f"{len(light_candidates)} light candidates house-wide",
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                    targets = light_candidates
                if not targets:
                    resolution_errors.append("No lights were found in this house.")
        elif not targets and room:
            wanted_room = normalized_name(room)
            targets = [
                device for device in candidates
                if normalized_name(room_name(device)) == wanted_room
            ]
            if not targets:
                started = time.monotonic()
                try:
                    manifest = await self.mcp.get_cached_devices()
                except Exception as exc:
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=False,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=f"Room identity manifest unavailable: {exc}",
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                else:
                    room_candidates = [
                        device
                        for device in (manifest or [])
                        if isinstance(device, dict)
                        and normalized_name(room_name(device)) == wanted_room
                        and self._matches_kind(kind, device)
                    ]
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=True,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=(
                            f"{len(room_candidates)} {kind} candidates in "
                            f"normalized room {room!r}"
                        ),
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                    targets = room_candidates
                if not targets:
                    resolution_errors.append(
                        f"No {kind}s were found in room {room!r}."
                    )
        elif not targets:
            fallback_candidates: list[dict[str, Any]] | None = None
            for requested, source_devices in zip(
                names, source_groups, strict=True
            ):
                eligible = [
                    device for device in source_devices
                    if self._matches_kind(kind, device)
                ]
                resolution = resolve_device_candidate(
                    str(requested), eligible
                )
                # Only widen the search to the full house-wide manifest
                # when the targeted, labelFilter-scoped lookup found
                # nothing at all to judge (eligible empty) -- its own
                # search may simply have missed the device on a phrasing
                # or synonym quirk, and a broader look is worth trying.
                # When eligible is non-empty, resolve_device_candidate has
                # already made a real judgement call against a precise,
                # relevant candidate set (either "these two are equally
                # plausible" or "none of these few are close enough"), and
                # that judgement must not be silently overridden by a
                # second, noisier attempt against every device in the
                # house. Live-observed regression: "turn on livingroom
                # light" correctly came back ambiguous between two real
                # lights against the narrow set, but this used to retry
                # against the full ~30-device manifest anyway and picked
                # "Livingroom TRV" as the nearest fuzzy match once real
                # lights were excluded by the kind-filtering bug fixed
                # alongside this -- discarding a legitimate ambiguous
                # result in favour of a wrong single "winner".
                if resolution.target is None and not eligible:
                    if fallback_candidates is None:
                        started = time.monotonic()
                        try:
                            manifest = await self.mcp.get_cached_devices()
                        except Exception as exc:
                            fallback_candidates = []
                            self._record_evidence(
                                "hub_read_devices",
                                {
                                    "tool": "hub_list_devices",
                                    "source": "short_ttl_cache",
                                },
                                success=False,
                                elapsed_ms=round(
                                    (time.monotonic() - started) * 1000
                                ),
                                summary=f"Identity manifest unavailable: {exc}",
                                supports_live_claim=False,
                                evidence_kind="control_target_resolution",
                            )
                        else:
                            fallback_candidates = [
                                device
                                for device in (manifest or [])
                                if isinstance(device, dict)
                                and self._matches_kind(kind, device)
                            ]
                            self._record_evidence(
                                "hub_read_devices",
                                {
                                    "tool": "hub_list_devices",
                                    "source": "short_ttl_cache",
                                },
                                success=True,
                                elapsed_ms=round(
                                    (time.monotonic() - started) * 1000
                                ),
                                summary=(
                                    f"{len(fallback_candidates)} fallback "
                                    "target candidates"
                                ),
                                supports_live_claim=False,
                                evidence_kind="control_target_resolution",
                            )
                    resolution = resolve_device_candidate(
                        str(requested), fallback_candidates
                    )
                if resolution.target is not None:
                    target = dict(resolution.target)
                    target["_resolved_label"] = resolution.matched_name
                    targets.append(target)
                else:
                    resolution_errors.append(resolution.reason)
                    resolution_choices.update(resolution.alternatives)

        unique_targets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for target in targets:
            device_id = str(target.get("id") or target.get("deviceId") or "")
            if not device_id:
                resolution_errors.append(
                    f"{target.get('label') or target.get('name')!r} has no device ID."
                )
            elif device_id not in seen_ids:
                seen_ids.add(device_id)
                unique_targets.append(target)
        if resolution_errors:
            data = {
                "success": False,
                "error": " ".join(resolution_errors),
                "choices": sorted(resolution_choices),
                "matched": [],
                "executed": 0,
            }
            return MCPToolResult(
                DEVICE_CONTROL_TOOL, arguments, {}, json.dumps(data), data,
                is_error=True,
            )

        semaphore = asyncio.Semaphore(8)

        async def execute(target: dict[str, Any]) -> dict[str, Any]:
            device_id = str(target.get("id") or target.get("deviceId"))
            label = str(
                target.get("_resolved_label")
                or target.get("label")
                or target.get("name")
                or device_id
            )
            # Whatever cached "switch" reading came back with this target --
            # from the identity cache for the fast path, or from the live
            # hub_read_devices lookup for the fallback path -- lets the
            # result say whether this device actually changed state or was
            # already where the command wanted it, without any extra
            # round-trip. This is reporting-only: the command is still sent
            # to every matched device regardless of what the cache says, on
            # purpose -- the cache can be stale, and skipping a device
            # because a stale reading claimed it was "already off" would
            # silently fail to comply with an explicit "turn off the
            # lights" for a light that was actually still on. Live-observed
            # feedback: a bare "turn off the lights" command hit every real
            # light in the house and reported all of them as "Turned off",
            # even the ones that were already off, which reads as if the
            # assistant has no idea which lights were actually on.
            pre_switch = str(device_attributes(target).get("switch") or "").casefold()
            expected_value: str | None = command if command in {"on", "off"} else None
            if command == "toggle":
                # "on"/"off" have a known target state up front, so they can
                # ask the hub to waitFor convergence on it directly. "toggle"
                # doesn't -- without this, it never got a waitFor at all
                # (device_control_service.py had no verification path for
                # it, unlike on/off), so a toggle whose HTTP call succeeded
                # but whose physical device never actually changed state
                # (asleep repeater, brief RF collision, etc.) was reported
                # as success with no way to know it didn't happen. Reading
                # the current state first lets toggle get the exact same
                # waitFor-based verification on/off already have. If this
                # read fails or the attribute is missing, fall back to the
                # previous unverified behaviour rather than guessing.
                try:
                    async with semaphore:
                        state_result = await self.mcp.call_tool(
                            "hub_read_devices",
                            {
                                "tool": "hub_get_device_attribute",
                                "args": {"deviceId": device_id, "attribute": "switch"},
                            },
                        )
                    current_state = (
                        state_result.data.get("value")
                        if self._tool_succeeded(state_result)
                        and isinstance(state_result.data, dict)
                        else None
                    )
                except Exception:
                    current_state = None
                if isinstance(current_state, str) and current_state.casefold() in {"on", "off"}:
                    expected_value = "off" if current_state.casefold() == "on" else "on"
                    # This live read is strictly more trustworthy than the
                    # cached reading above -- toggle already pays for it.
                    pre_switch = current_state.casefold()
            call_arguments = {
                "tool": "hub_call_device_command",
                "args": {
                    "deviceId": device_id,
                    "command": command,
                    **(
                        {
                            "waitFor": {
                                "attribute": "switch",
                                "expectedValue": expected_value,
                                "timeoutMs": 5000,
                            }
                        }
                        if expected_value is not None
                        else {}
                    ),
                },
            }
            started = time.monotonic()
            command_success = False
            verified: bool | None = None
            verification_message = ""
            try:
                async with semaphore:
                    result = await self.mcp.call_tool(
                        "hub_manage_devices", call_arguments
                    )
                command_success = self._tool_succeeded(result)
                message = result.text
                if expected_value is not None:
                    wait_for = (
                        result.data.get("waitFor")
                        if isinstance(result.data, dict)
                        else None
                    )
                    verified = (
                        bool(wait_for.get("converged"))
                        if isinstance(wait_for, dict)
                        else False
                    )
                    verification_message = (
                        json.dumps(wait_for)
                        if isinstance(wait_for, dict)
                        else "Command response omitted waitFor confirmation."
                    )
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                logger.exception(
                    "High-level device command failed for %s", label
                )
            evidence_outcome = (
                "verified"
                if command_success and verified is True
                else "sent"
                if command_success
                else "failed"
            )
            self._record_evidence(
                "hub_manage_devices",
                call_arguments,
                success=command_success and verified is not False,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{command} {label}: {evidence_outcome}",
                supports_live_claim=True,
                evidence_kind="device_command_result",
            )
            success = command_success and verified is not False
            # already_in_state is only ever asserted True from a known prior
            # reading that matches the target command -- an unknown/missing
            # prior reading defaults to "changed" (already_in_state False),
            # so a device with no cached state still gets reported as acted
            # upon rather than silently dropped from the summary.
            already_in_state = (
                expected_value is not None and pre_switch == expected_value
            )
            return {
                "id": device_id,
                "label": label,
                "room": room_name(target),
                "success": success,
                "command_sent": command_success,
                "verified": verified,
                "message": message,
                "verification_message": verification_message,
                "already_in_state": already_in_state,
                "changed": success and not already_in_state,
            }

        results = await asyncio.gather(*(execute(target) for target in unique_targets))
        succeeded = [item for item in results if item["success"]]
        failed = [item for item in results if not item["success"]]
        if failed:
            # A routine light/switch command that didn't fully succeed --
            # either Hubitat rejected the command outright (command_sent
            # False, presented to the user as "Failed: <device>.") or
            # accepted it but the device never converged to the expected
            # switch state within the wait window (command_sent True,
            # verified False, presented as "Command sent but state
            # verification failed"). Neither case previously touched any
            # fixed outcome counter, so classify_completed_request() fell
            # through to its "success" default -- observed live, the WebUI
            # showed a green "Success" badge next to a message that
            # literally read "Failed: Livingroom Light 2 and Livingroom
            # Light 1." This counter closes that gap the same way
            # ConfirmedActionCoordinator already does for the sensitive-
            # mutation path via mutation_verification_failures.
            increment_active_metric("device_control_failures")
        data = {
            "success": not failed and bool(succeeded),
            "command": command,
            "device_kind": kind,
            "matched": len(unique_targets),
            "executed": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "complete": True,
        }
        if stripped_action_note is not None:
            data["note"] = (
                f"This request also mentioned \"{stripped_action_note}\", which "
                "was not part of this device action -- ask for it separately."
            )
        return MCPToolResult(
            DEVICE_CONTROL_TOOL, arguments, {}, json.dumps(data), data
        )


__all__ = [
    "DEVICE_CONTROL_TOOL",
    "DeviceControlService",
    "is_all_lights_target",
    "resolve_all_lights_exclusions",
    "split_all_lights_exclusion",
    "strip_trailing_unrelated_action",
]
