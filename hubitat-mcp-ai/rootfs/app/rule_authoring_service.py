"""Deterministic compiler for common Rule Machine schedules.

The model may identify an automation goal, but it must not invent Hubitat's
``hub_set_rule`` JSON.  This service recognises a deliberately small,
high-confidence schedule grammar, resolves the target through the shared
device resolver, verifies the requested commands, and emits validated atomic
Rule Machine calls for the existing confirmation pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from device_query_service import DeviceQueryService
from device_state_summary import room_name
from device_target_resolver import normalized_name, resolve_device_candidate
from hub_timezone import HubTimezoneResolver
from mcp_client import HubitatMCPClient

logger = logging.getLogger("HomeBrainOS.RuleAuthoringService")
from time_expressions import AT_TIME as _SHARED_AT_TIME, parse_clock as _shared_parse_clock
from tool_registry import rule_machine_proposal_error


RULE_MACHINE_GATEWAY = "hub_manage_rule_machine"

# Placeholder substituted by ConfirmedActionCoordinator with the appId the
# hub assigns to a just-created rule, once that create action has been
# executed and verified. Lets a one-time rule's follow-up self-pause action
# be built and validated at proposal time -- before the real id exists --
# without teaching the coordinator anything about rule-authoring semantics
# beyond "replace this token with the previous rule write's appId."
NEW_RULE_ID_TOKEN = "__NEW_RULE_ID__"


@dataclass(frozen=True, slots=True)
class RuleAuthoringDecision:
    """Result of attempting the bounded deterministic rule grammar."""

    handled: bool
    message: str | None = None
    actions: tuple[dict[str, Any], ...] = ()
    rule_names: tuple[str, ...] = ()
    target: dict[str, Any] | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class _ScheduleIntent:
    target: str
    start_time: str
    start_command: str
    start_label: str
    end_time: str | None = None
    end_command: str | None = None
    end_label: str | None = None
    recurring: bool = True


class RuleAuthoringService:
    """Compile supported daily and one-time device schedules without model-authored JSON."""

    _AUTHORING = re.compile(
        r"\b(?:add|build|create|make|schedule|set up|setup|write)\b"
        r"[\s\S]{0,40}\b(?:automation|rule|schedule)\b",
        re.I,
    )
    # Plain routine-control phrasing ("turn on X at 7am", "turn on X every day
    # at 7am") is a legitimate rule-authoring request on its own -- it should
    # not require the user to additionally say the word "rule". This mirrors
    # the verb set request_classification.requests_mutation() already treats
    # as control language, so a phrase recognised as a control command
    # elsewhere in the codebase is recognised consistently here too.
    _CONTROL_LEAD = re.compile(
        r"^(?:please\s+)?(?:turn|switch|lock|unlock|close|shut|open|block|"
        r"disable|allow|enable)\b",
        re.I,
    )
    _WINDOW = re.compile(
        r"\bfrom\s+(?P<start>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)"
        r"\s+(?:to|until|through|-)\s+"
        r"(?P<end>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\b",
        re.I,
    )
    _RELATIVE_DELAY = re.compile(
        r"\b(?:"
        r"(?:in|after)\s+(?P<amount>\d+)\s*(?P<unit>minutes?|mins?|hours?|hrs?)"
        r"|(?P<later_amount>\d+)\s*(?P<later_unit>minutes?|mins?|hours?|hrs?)\s+later"
        r")\s*[.!?]*$",
        re.I,
    )
    # "every single day" is at least as natural as "every day" and must not
    # be left to fall through to the daily-vs-one-time branch undetected --
    # see _clean_goal, which strips whichever of these actually matched.
    _DAILY = re.compile(
        r"\b(?:daily|every\s+single\s+day|every\s*day|everyday)\b", re.I
    )
    _PREFIX = re.compile(
        r"^.*?\b(?:automation|rule|schedule)\b\s+(?:that\s+|to\s+)?",
        re.I,
    )
    # request_classification.routine_control_arguments() -- the deterministic
    # matcher for *immediate* (non-scheduled) control commands -- already
    # accepts a leading "please" in its own patterns. This grammar's device-
    # name extraction patterns (_SINGLE_PATTERNS / _window_intent's patterns)
    # never accounted for it, so "please turn on X at 7am" silently fell
    # through to the generic model loop instead of being recognised, even
    # though _CONTROL_LEAD above was already written to allow "please" at
    # the gate. Stripped in _clean_goal so both the single-trigger and
    # window grammars benefit uniformly.
    _LEADING_PLEASE = re.compile(r"^please\s+", re.I)
    _AT_TIME = _SHARED_AT_TIME

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
        *,
        now: Callable[[], datetime] = datetime.now,
        internet_control_aliases: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence
        self._now = now
        self._hub_timezone = HubTimezoneResolver(mcp_client, record_evidence)
        self.internet_control_aliases = self._parse_internet_control_aliases(
            internet_control_aliases
        )

    @staticmethod
    def _parse_internet_control_aliases(value: Any | None) -> dict[str, str]:
        if value in {None, ""}:
            return {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return {}
        if not isinstance(value, dict):
            return {}
        aliases: dict[str, str] = {}
        for alias, label in value.items():
            alias_text = str(alias or "").strip()
            label_text = str(label or "").strip()
            if alias_text and label_text:
                aliases[normalized_name(alias_text)] = label_text
        return aliases

    def _configured_internet_target(
        self, requested: str, identities: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        requested_key = normalized_name(requested)
        configured_label = self.internet_control_aliases.get(requested_key)
        if configured_label is None:
            for label in self.internet_control_aliases.values():
                if normalized_name(label) == requested_key:
                    configured_label = label
                    break
        if not configured_label:
            return None
        wanted = normalized_name(configured_label)
        matches = []
        for item in identities:
            if not isinstance(item, dict):
                continue
            names = (
                item.get("label"),
                item.get("name"),
                item.get("displayName"),
                item.get("deviceLabel"),
            )
            if any(normalized_name(name) == wanted for name in names if name):
                matches.append(dict(item))
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _clock(value: str) -> str | None:
        return _shared_parse_clock(value)

    @staticmethod
    def _next_occurrence_iso(clock_value: str, now: datetime) -> str:
        """Resolve a bare 'HH:MM' clock time to the next real occurrence.

        Hubitat's "Certain Time (and optional date)" trigger fires once and
        does not recur when ``atTime`` carries a specific calendar date
        (unlike the bare 'HH:MM' form used for daily rules, which recurs
        every day). If the time has already passed today, the next
        occurrence is tomorrow rather than today; this is a real clock read
        from the host, not a model guess, so it is deterministic and
        testable via the injected ``now`` callable.
        """

        hour, minute = (int(part) for part in clock_value.split(":"))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.strftime("%Y-%m-%dT%H:%M:%S")

    @classmethod
    def _clean_goal(cls, text: str, cut: int) -> str:
        """Strip the authoring prefix and the daily marker from a goal slice.

        The daily marker ("daily" / "every day" / "everyday") can precede
        or follow the time clause in natural phrasing -- "block internet
        every day from 10pm to 6am" is at least as common as "...from 10pm
        to 6am every day". Whichever side it lands on within this slice,
        it must not survive into the goal text or the verb-pattern
        fullmatch below will spuriously fail.
        """

        goal = cls._PREFIX.sub("", text[:cut])
        goal = cls._DAILY.sub("", goal)
        goal = " ".join(goal.split()).strip(" ,.-")
        goal = cls._LEADING_PLEASE.sub("", goal)
        return goal.strip(" ,.-")

    def matches_request(self, prompt: str) -> bool:
        """Return whether the bounded deterministic authoring grammar applies."""

        return self._intent(prompt) is not None

    def _intent(
        self, prompt: str, *, now: datetime | None = None
    ) -> _ScheduleIntent | None:
        text = " ".join(str(prompt).strip().split())
        authored = self._AUTHORING.search(text) is not None
        relative = self._RELATIVE_DELAY.search(text)
        # Plain control phrasing is recognised via a clock clause, a recurring
        # window, or a bounded relative delay. Relative delays are compiled
        # into a dated one-time trigger instead of leaving the model to invent
        # a Delay action inside the rule.
        plain_control = self._CONTROL_LEAD.match(text) is not None and (
            self._AT_TIME.search(text) is not None
            or self._WINDOW.search(text) is not None
            or relative is not None
        )
        if not authored and not plain_control:
            return None
        daily = self._DAILY.search(text) is not None
        window = self._WINDOW.search(text)
        if window is not None:
            # The auto-revert window grammar ("...from 10pm to 6am") only
            # makes sense as a recurring daily pair -- a one-shot version
            # would need its own end-date handling this grammar does not
            # attempt. Require the daily marker here, same as before.
            if not daily:
                return None
            return self._window_intent(text, window)
        if relative is not None:
            if daily:
                return None
            return self._relative_intent(text, relative, now=now)
        return self._single_intent(text, daily=daily, now=now)

    @classmethod
    def _window_intent(cls, text: str, window: re.Match[str]) -> _ScheduleIntent | None:
        start = cls._clock(window.group("start"))
        end = cls._clock(window.group("end"))
        if start is None or end is None or start == end:
            return None

        goal = cls._clean_goal(text, window.start())
        patterns = (
            (re.compile(r"^(?:block|disable|restrict)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I),
             "blockInternet", "allowInternet", "Block", "Unblock"),
            (re.compile(r"^(?:turn|switch)\s+(?P<target>.+?)\s+off$", re.I),
             "off", "on", "Turn off", "Turn on"),
            (re.compile(r"^lock\s+(?P<target>.+)$", re.I),
             "lock", "unlock", "Lock", "Unlock"),
            (re.compile(r"^(?:close|shut)\s+(?P<target>.+)$", re.I),
             "close", "open", "Close", "Open"),
        )
        for pattern, start_command, end_command, start_label, end_label in patterns:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if target:
                return _ScheduleIntent(
                    target=target,
                    start_time=start,
                    start_command=start_command,
                    start_label=start_label,
                    end_time=end,
                    end_command=end_command,
                    end_label=end_label,
                )
        return None

    _SINGLE_PATTERNS = (
        (re.compile(r"^turn\s+on\s+(?P<target>.+)$", re.I), "on", "Turn on"),
        (re.compile(r"^turn\s+(?P<target>.+?)\s+on$", re.I), "on", "Turn on"),
        (re.compile(r"^switch\s+on\s+(?P<target>.+)$", re.I), "on", "Turn on"),
        (re.compile(r"^switch\s+(?P<target>.+?)\s+on$", re.I), "on", "Turn on"),
        (re.compile(r"^turn\s+off\s+(?P<target>.+)$", re.I), "off", "Turn off"),
        (re.compile(r"^turn\s+(?P<target>.+?)\s+off$", re.I), "off", "Turn off"),
        (re.compile(r"^switch\s+off\s+(?P<target>.+)$", re.I), "off", "Turn off"),
        (re.compile(r"^switch\s+(?P<target>.+?)\s+off$", re.I), "off", "Turn off"),
        (re.compile(r"^lock\s+(?P<target>.+)$", re.I), "lock", "Lock"),
        (re.compile(r"^unlock\s+(?P<target>.+)$", re.I), "unlock", "Unlock"),
        (re.compile(r"^(?:close|shut)\s+(?P<target>.+)$", re.I), "close", "Close"),
        (re.compile(r"^open\s+(?P<target>.+)$", re.I), "open", "Open"),
        (re.compile(
            r"^(?:block|disable|restrict)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I,
        ), "blockInternet", "Block"),
        (re.compile(
            r"^(?:allow|enable)\s+(?:internet\s+(?:for\s+)?)?(?P<target>.+)$", re.I,
        ), "allowInternet", "Unblock"),
        # "unblock"/"restore" are only safe to treat as internet-access verbs
        # when "internet"/"access" is stated explicitly -- see the matching
        # note in request_classification.py's _ALLOW_INTERNET_EXPLICIT; both
        # words are heavily overloaded elsewhere ("restore the backup").
        (re.compile(
            r"^(?:unblock|restore)\s+(?:internet\s+(?:access\s+)?(?:for\s+)?|access\s+for\s+)"
            r"(?P<target>.+)$", re.I,
        ), "allowInternet", "Unblock"),
    )

    # Catches "turn on X on", "turn off X off", "switch on X on", "switch
    # off X off" -- a redundant trailing state word that duplicates the
    # leading verb. Live testing found "turn on livingroom light 1 on at
    # 12.05" resolved a device literally named "livingroom light 1 on":
    # `_SINGLE_PATTERNS`' first (greedy) alternative for "turn on" swallows
    # everything after it, including an accidental repeated "on" right
    # before the time clause -- a natural typo when the phrasing habit
    # "turn on X" gets combined with "X on at TIME". Only collapses when
    # the trailing word exactly matches the leading verb's state, so a
    # device genuinely named to end in "...on"/"...off" is not touched
    # unless someone also says the state word twice.
    _REDUNDANT_TRAILING_STATE = re.compile(
        r"^(?P<lead>turn\s+on|turn\s+off|switch\s+on|switch\s+off)\s+"
        r"(?P<target>.+?)\s+(?P<trail>on|off)$",
        re.I,
    )

    @classmethod
    def _drop_redundant_trailing_state(cls, goal: str) -> str:
        match = cls._REDUNDANT_TRAILING_STATE.fullmatch(goal)
        if match is None:
            return goal
        lead_state = match.group("lead").split()[-1].casefold()
        if lead_state != match.group("trail").casefold():
            return goal
        return f"{match.group('lead')} {match.group('target')}"

    @staticmethod
    def _relative_minutes(match: re.Match[str]) -> int | None:
        amount_text = match.group("amount") or match.group("later_amount")
        unit = match.group("unit") or match.group("later_unit") or "minutes"
        if not amount_text:
            return None
        amount = int(amount_text)
        if amount <= 0:
            return None
        return amount * (60 if unit.casefold().startswith(("hour", "hr")) else 1)

    def _relative_intent(
        self,
        text: str,
        relative: re.Match[str],
        *,
        now: datetime | None = None,
    ) -> _ScheduleIntent | None:
        minutes = self._relative_minutes(relative)
        if minutes is None:
            return None
        goal = self._clean_goal(text, relative.start())
        goal = self._drop_redundant_trailing_state(goal)
        for pattern, command, label in self._SINGLE_PATTERNS:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if not target:
                continue
            current = now if now is not None else self._now()
            trigger = current.replace(microsecond=0) + timedelta(minutes=minutes)
            return _ScheduleIntent(
                target=target,
                start_time=trigger.strftime("%Y-%m-%dT%H:%M:%S"),
                start_command=command,
                start_label=label,
                recurring=False,
            )
        return None

    def _single_intent(
        self, text: str, *, daily: bool, now: datetime | None = None
    ) -> _ScheduleIntent | None:
        """Recognise a single trigger with no auto-revert window.

        Deliberately narrow: exactly one advertised command is required and
        verified, exactly one atomic rule is emitted. "Turn on X every day
        at 7am" (recurring) and "turn on X at 7am" (one-time) are the
        intended shapes; neither is confused with the window grammar's
        auto-reverting "turn X off from A to B" pattern, since this path
        only runs when `_window_intent` found no window clause at all.

        ``daily`` selects the trigger shape: a bare 'HH:MM' recurs every
        day on Hubitat; a full calendar-date ISO datetime fires exactly
        once. The clock time itself is parsed identically either way --
        only what gets sent as ``atTime`` differs.
        """

        at_match = self._AT_TIME.search(text)
        if at_match is None:
            return None
        at_time = self._clock(at_match.group("time"))
        if at_time is None:
            return None

        goal = self._clean_goal(text, at_match.start())
        goal = self._drop_redundant_trailing_state(goal)
        for pattern, command, label in self._SINGLE_PATTERNS:
            match = pattern.fullmatch(goal)
            if match is None:
                continue
            target = match.group("target").strip(" ,.-")
            target = re.sub(r"^(?:the\s+)", "", target, flags=re.I)
            if target:
                trigger_time = (
                    at_time
                    if daily
                    else self._next_occurrence_iso(
                        at_time, now if now is not None else self._now()
                    )
                )
                return _ScheduleIntent(
                    target=target,
                    start_time=trigger_time,
                    start_command=command,
                    start_label=label,
                    recurring=daily,
                )
        return None

    @staticmethod
    def _commands(device: dict[str, Any]) -> set[str]:
        values = device.get("commands") or device.get("supportedCommands") or []
        if isinstance(values, dict):
            values = list(values)
        commands: set[str] = set()
        for item in values if isinstance(values, (list, tuple, set)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("command")
            if item:
                commands.add(str(item).casefold())
        return commands

    # Standard Hubitat capabilities and the commands they're documented to
    # expose. Used to prefer whichever capability actually backs the
    # command(s) this rule schedules, rather than picking by fixed
    # priority regardless of what's being scheduled -- a device
    # advertising both "Switch" and "GarageDoorControl" (e.g. a garage
    # door opener that also exposes a virtual switch) previously always
    # got "Switch" as its capabilityFilter because Switch sits first in
    # the priority list, even for a scheduled "close"/"open" rule that
    # "Switch" cannot perform -- Hubitat's runCommand action requires the
    # capabilityFilter to be a capability that actually exposes the
    # command, so this silently produced a rule that could never fire the
    # intended action.
    _CAPABILITY_COMMANDS: dict[str, frozenset[str]] = {
        "Switch": frozenset({"on", "off"}),
        "Lock": frozenset({"lock", "unlock"}),
        "DoorControl": frozenset({"open", "close"}),
        "GarageDoorControl": frozenset({"open", "close"}),
        "Valve": frozenset({"open", "close"}),
    }

    @classmethod
    def _capability_filter(cls, device: dict[str, Any], commands: set[str]) -> str:
        values = device.get("capabilities") or []
        if isinstance(values, dict):
            values = list(values)
        names = []
        for item in values if isinstance(values, (list, tuple, set)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("capability")
            if item:
                names.append(str(item))
        # Prefer, in the device's own reported capability order, whichever
        # capability's standard commands cover every command this rule
        # schedules (start and, for a window, end).
        wanted = {str(command).casefold() for command in commands}
        for name in names:
            canonical = next(
                (
                    cap for cap in cls._CAPABILITY_COMMANDS
                    if cap.casefold() == name.casefold()
                ),
                None,
            )
            if canonical and wanted and wanted.issubset(cls._CAPABILITY_COMMANDS[canonical]):
                return canonical
        # No capability's known standard commands cover what's being
        # scheduled -- this is expected for driver-specific commands like
        # blockInternet/allowInternet, which aren't part of any standard
        # capability's documented command set. Fall back to the original
        # fixed-priority selection among the device's own capabilities.
        for preferred in ("Switch", "Lock", "DoorControl", "GarageDoorControl"):
            if any(name.casefold() == preferred.casefold() for name in names):
                return preferred
        return names[0] if names else "Switch"

    @staticmethod
    def _rule_name(label: str, target_label: str, suffix: str) -> str:
        clean = re.sub(r"[-_]+", " ", target_label)
        clean = " ".join(clean.split())
        base = clean if clean.casefold().startswith(label.casefold() + " ") else f"{label} {clean}"
        return f"{base} ({suffix})"

    @classmethod
    def _action(
        cls,
        *,
        name: str,
        at_time: str,
        device_id: Any,
        capability_filter: str,
        command: str,
    ) -> dict[str, Any]:
        action = {
            "tool": "hub_set_rule",
            "args": {
                "name": name,
                "addTrigger": {
                    "capability": "Certain Time (and optional date)",
                    "time": "A specific time",
                    "atTime": at_time,
                },
                "addAction": {
                    "capability": "runCommand",
                    "deviceIds": [str(device_id)],
                    "capabilityFilter": capability_filter,
                    "command": command,
                },
            },
        }
        error = rule_machine_proposal_error(RULE_MACHINE_GATEWAY, action)
        if error is not None:
            raise ValueError(error)
        return action

    @staticmethod
    def _self_pause_action() -> dict[str, Any]:
        """Build the follow-up edit that pauses a just-created one-time rule.

        Hubitat's "Certain Time (and optional date)" trigger is documented
        to fire once and not recur when ``atTime`` carries a full calendar
        date, but a live scheduler job inspected during development still
        carried a `"recurring": true` label internally despite the dated
        trigger -- an unconfirmed ambiguity in Hubitat's own scheduler
        bookkeeping, not this app's behaviour. Rather than rely on that
        label being cosmetic, a one-time rule's action list ends with a
        native `pauseRule` action that pauses the rule itself, so even if
        the underlying job did try to fire again, the rule can never
        re-execute its actions.

        `pauseRule` requires an existing rule id for both the edit target
        (``appId``) and the action's own ``ruleIds`` -- neither of which
        exists yet at proposal time, since the rule this pauses hasn't been
        created. Both are filled with ``NEW_RULE_ID_TOKEN``, a placeholder
        `ConfirmedActionCoordinator` substitutes with the real appId
        returned by the immediately preceding create action, after
        verifying that write succeeded. `rule_machine_proposal_error` only
        checks that ``appId`` is non-empty, not that it looks numeric, so
        this validates cleanly with the token still in place.
        """

        action = {
            "tool": "hub_set_rule",
            "args": {
                "appId": NEW_RULE_ID_TOKEN,
                "addAction": {
                    "capability": "pauseRule",
                    "action": "pause",
                    "ruleIds": [NEW_RULE_ID_TOKEN],
                },
            },
        }
        error = rule_machine_proposal_error(RULE_MACHINE_GATEWAY, action)
        if error is not None:
            raise ValueError(error)
        return action

    @staticmethod
    def _rule_rows(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            for key in ("rules", "items", "apps", "data", "result", "output"):
                nested = value.get(key)
                rows = RuleAuthoringService._rule_rows(nested)
                if rows:
                    return rows
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    async def _existing_names(self) -> set[str] | None:
        arguments = {"tool": "hub_list_rules", "args": {}}
        started = time.monotonic()
        try:
            result = await self.mcp.call_tool("hub_read_rules", arguments)
        except Exception as exc:
            logger.warning("Could not read existing rule names", exc_info=True)
            self._record_evidence(
                "hub_read_rules",
                arguments,
                success=False,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                supports_live_claim=True,
                evidence_kind="rule_duplicate_check",
            )
            return None
        success = not result.is_error and not (
            isinstance(result.data, dict) and result.data.get("success") is False
        )
        rows = self._rule_rows(result.data)
        self._record_evidence(
            "hub_read_rules",
            arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(rows)} existing Rule Machine rules checked for duplicates",
            supports_live_claim=True,
            evidence_kind="rule_duplicate_check",
        )
        if not success:
            return None
        return {
            str(item.get("name") or item.get("label") or "").strip().casefold()
            for item in rows
            if item.get("name") or item.get("label")
        }

    @staticmethod
    def _create_name(arguments: dict[str, Any]) -> str | None:
        """Return the name only for a direct new-rule proposal."""

        if arguments.get("tool") != "hub_set_rule":
            return None
        payload = arguments.get("args")
        if not isinstance(payload, dict) or payload.get("appId") not in {None, ""}:
            return None
        name = str(payload.get("name") or "").strip()
        return name or None

    async def duplicate_create_error(
        self,
        arguments: dict[str, Any],
    ) -> str | None:
        return await self.duplicate_create_group_error([arguments])

    async def duplicate_create_group_error(
        self,
        arguments: list[dict[str, Any]],
    ) -> str | None:
        """Fail closed when a new Rule Machine name cannot be proved unique.

        This is intentionally reusable by both proposal-time validation and
        confirmation replay.  Checking twice closes the time-of-check/time-of-
        use window: another request may create the same rule while the user is
        reading the confirmation prompt.
        """

        names = [
            name
            for item in arguments
            if (name := self._create_name(item)) is not None
        ]
        if not names:
            return None
        normalized = [name.casefold() for name in names]
        duplicates_in_group = sorted(
            {
                name
                for name in names
                if normalized.count(name.casefold()) > 1
            }
        )
        if duplicates_in_group:
            rendered = ", ".join(f"**{name}**" for name in duplicates_in_group)
            return (
                "The Rule Machine action group was cancelled because it contains "
                f"the same new rule name more than once: {rendered}. Nothing was "
                "queued or executed."
            )
        existing = await self._existing_names()
        if existing is None:
            return (
                "The Rule Machine action was cancelled because HomeBrain could "
                "not verify the current rule list. Nothing was queued or "
                "executed; retry after the hub read succeeds."
            )
        collisions = [name for name in names if name.casefold() in existing]
        if collisions:
            rendered = ", ".join(f"**{name}**" for name in collisions)
            return (
                "No duplicate rule was created because the following Rule Machine "
                f"rule{'s' if len(collisions) != 1 else ''} already exist"
                f"{'s' if len(collisions) == 1 else ''}: {rendered}. Nothing was "
                "executed."
            )
        return None

    async def propose(
        self,
        prompt: str,
        *,
        available_gateways: set[str],
        can_read_rules: bool = True,
    ) -> RuleAuthoringDecision:
        """Return a complete validated plan only for the supported grammar.

        `can_read_rules` is accepted for backward compatibility but no
        longer gates the duplicate-rule check below (default changed to
        True). It used to be tied to whether `hub_read_rules` happened to
        survive this turn's per-request tool-catalog truncation
        (`tool_limit`, default 48) -- an incidental, discovery-dependent
        signal, not a guarantee that the gateway doesn't exist. That let a
        server exposing more than `tool_limit` gateways silently skip
        duplicate-rule protection on every single schedule request whose
        catalog build happened not to include `hub_read_rules`, creating
        additional duplicate Rule Machine rules for repeated identical
        requests instead of reporting "already exists". `_existing_names()`
        calls `hub_read_rules` directly via the MCP client, not through the
        model's declared-tool schema, so it never needed this turn's
        catalog to include the tool in the first place -- and it already
        fails closed to an empty set (skipping the check, not raising) if
        the call genuinely errors.
        """

        # First pass is a no-I/O grammar gate. Only genuine deterministic
        # scheduling requests pay for authoritative timezone resolution.
        intent = self._intent(prompt)
        if intent is None:
            return RuleAuthoringDecision(False)
        if RULE_MACHINE_GATEWAY not in available_gateways:
            return RuleAuthoringDecision(False)

        if not intent.recurring:
            runtime_now = self._now()
            if runtime_now.tzinfo is None:
                # The Home Assistant add-on container runs UTC in production.
                # Treat a naive injected/runtime clock as UTC before converting
                # it through the authoritative Hubitat location timezone.
                runtime_now = runtime_now.replace(tzinfo=timezone.utc)
            hub_now, _timezone_name, _timezone_source = (
                await self._hub_timezone.now_in_hub_timezone(lambda: runtime_now)
            )
            intent = self._intent(prompt, now=hub_now)
            if intent is None:
                return RuleAuthoringDecision(False)

        resolver = DeviceQueryService(self.mcp, self._record_evidence)
        internet_access = intent.start_command.casefold() in {
            "blockinternet", "allowinternet"
        }
        resolve_arguments: dict[str, Any] = {"name": intent.target}

        if internet_access:
            # Internet access controls are ordinary Hubitat Switch devices in
            # the authoritative Internet room. Their user-facing semantics are
            # intentionally inverted from the literal switch wording:
            # switch=on means Internet allowed; switch=off means Internet
            # blocked. Do not require synthetic blockInternet/allowInternet
            # driver commands. First scope fuzzy identity matching to the
            # Internet room so a normal device such as "Google TV Streamer
            # (ADB)" cannot win merely because its label is a closer match.
            identity_started = time.monotonic()
            try:
                # get_cached_devices() is the long-established enriched identity
                # interface used by the control/query paths and by older MCP
                # clients/test doubles. Prefer it here; fall back to the newer
                # get_device_identities() helper when only that interface exists.
                identity_reader = getattr(self.mcp, "get_cached_devices", None)
                if not callable(identity_reader):
                    identity_reader = getattr(self.mcp, "get_device_identities", None)
                if not callable(identity_reader):
                    raise AttributeError("No device identity reader is available")
                identities = list(await identity_reader() or [])
            except Exception as exc:
                self._record_evidence(
                    "homebrain_device_inventory",
                    {"group": "Internet"},
                    success=False,
                    elapsed_ms=round((time.monotonic() - identity_started) * 1000),
                    summary=f"Internet-group identity lookup failed: {type(exc).__name__}",
                    supports_live_claim=True,
                    evidence_kind="deterministic_internet_target_scope",
                )
                return RuleAuthoringDecision(
                    True,
                    "I could not read the authoritative **Internet** device group. "
                    "Nothing was queued.",
                )

            internet_candidates = [
                item
                for item in identities
                if isinstance(item, dict)
                and str(room_name(item) or "").casefold() == "internet"
            ]
            configured_target = self._configured_internet_target(
                intent.target,
                [item for item in identities if isinstance(item, dict)],
            )
            if configured_target is not None:
                scoped_target = configured_target
                scoped_alternatives: tuple[str, ...] = ()
                scope_source = "configured alias"
            else:
                scoped = resolve_device_candidate(intent.target, internet_candidates)
                scoped_target = scoped.target
                scoped_alternatives = scoped.alternatives
                scope_source = "Internet room"
            self._record_evidence(
                "homebrain_device_inventory",
                {"group": "Internet"},
                success=scoped_target is not None,
                elapsed_ms=round((time.monotonic() - identity_started) * 1000),
                summary=(
                    f"{len(internet_candidates)} Internet-group candidates; "
                    f"configured_aliases={len(self.internet_control_aliases)}; "
                    f"source={scope_source}; "
                    f"target={'resolved' if scoped_target is not None else 'unresolved'}"
                ),
                supports_live_claim=True,
                evidence_kind="deterministic_internet_target_scope",
            )
            if scoped_target is None:
                if scoped_alternatives:
                    return RuleAuthoringDecision(
                        True,
                        "I could not uniquely match that request to an Internet-control "
                        "device. Possible matches: "
                        + ", ".join(scoped_alternatives[:3])
                        + ". Nothing was queued.",
                    )
                return RuleAuthoringDecision(
                    True,
                    f"I could not match **{intent.target}** to a device in the "
                    "authoritative **Internet** group or configured Internet aliases. "
                    "Nothing was queued.",
                )

            selected_label = str(
                scoped_target.get("label")
                or scoped_target.get("name")
                or intent.target
            ).strip()
            actual_start_command = (
                "off"
                if intent.start_command.casefold() == "blockinternet"
                else "on"
            )
            actual_end_command = intent.end_command
            if intent.end_command is not None:
                if intent.end_command.casefold() == "blockinternet":
                    actual_end_command = "off"
                elif intent.end_command.casefold() == "allowinternet":
                    actual_end_command = "on"

            # Re-read the selected control surface by its authoritative label
            # and verify the real Switch command we will schedule. This keeps
            # command verification intact while avoiding any fake capability.
            resolve_arguments = {
                "name": selected_label,
                "required_command": actual_start_command,
            }
            result = await resolver.resolve_device(resolve_arguments)
            intent = _ScheduleIntent(
                target=intent.target,
                start_time=intent.start_time,
                start_command=actual_start_command,
                start_label=intent.start_label,
                end_time=intent.end_time,
                end_command=actual_end_command,
                end_label=intent.end_label,
                recurring=intent.recurring,
            )
        else:
            result = await resolver.resolve_device(resolve_arguments)
        data = result.data if isinstance(result.data, dict) else {}
        target = data.get("target") if isinstance(data.get("target"), dict) else None
        if target is None:
            alternatives = [str(item) for item in data.get("alternatives") or [] if str(item)]
            if alternatives:
                return RuleAuthoringDecision(
                    True,
                    "I found more than one plausible target. Please choose: "
                    + ", ".join(alternatives[:3])
                    + ". Nothing was queued.",
                )
            required_command = str(resolve_arguments.get("required_command") or "").strip()
            if required_command:
                return RuleAuthoringDecision(
                    True,
                    f"I could not resolve a Hubitat device matching **{intent.target}** "
                    f"that advertises the required command: {required_command.casefold()}. "
                    "Nothing was queued.",
                )
            return RuleAuthoringDecision(
                True,
                f"I could not resolve **{intent.target}** to one Hubitat device. "
                "Nothing was queued.",
            )

        device_id = target.get("id") or target.get("deviceId")
        target_label = str(target.get("label") or target.get("name") or intent.target)
        if device_id in {None, ""}:
            return RuleAuthoringDecision(
                True,
                f"The resolved device **{target_label}** has no stable Hubitat ID. "
                "Nothing was queued.",
                target=target,
            )
        supported = self._commands(target)
        required = {intent.start_command.casefold()}
        if intent.end_command is not None:
            required.add(intent.end_command.casefold())
        if not required.issubset(supported):
            missing = sorted(required - supported)
            return RuleAuthoringDecision(
                True,
                f"**{target_label}** does not advertise the required command"
                f"{'s' if len(missing) != 1 else ''}: {', '.join(missing)}. "
                "Nothing was queued.",
                target=target,
            )

        capability_filter = self._capability_filter(target, required)

        if intent.end_time is None:
            if intent.recurring:
                suffix = "Daily"
            else:
                # intent.start_time is a full ISO datetime for a one-time
                # trigger (see _next_occurrence_iso); surface the resolved
                # calendar date AND time in the rule name so it is visible
                # in Rule Machine's own listing, not just in this chat
                # response. The date alone is not enough to disambiguate --
                # two distinct one-time requests for the same device and
                # command on the same day (e.g. "at 7am" and later "at
                # noon") produced identical date-only names and the second
                # request was wrongly treated as a duplicate of the first
                # and silently skipped, even though they are genuinely
                # different rules.
                date_part, _, time_part = intent.start_time.partition("T")
                suffix = f"One-time {date_part} {time_part[:5]}"
            single_name = self._rule_name(intent.start_label, target_label, suffix)
            existing = await self._existing_names() if can_read_rules else set()
            if existing is None:
                return RuleAuthoringDecision(
                    True,
                    "The rule was not queued because HomeBrain could not verify "
                    "the current Rule Machine list. Retry after the hub read "
                    "succeeds.",
                    rule_names=(single_name,),
                    target=target,
                )
            if single_name.casefold() in existing:
                return RuleAuthoringDecision(
                    True,
                    "No duplicate rule was queued because this Rule Machine rule "
                    f"already exists: **{single_name}**.",
                    rule_names=(single_name,),
                    target=target,
                )
            create_action = self._action(
                name=single_name,
                at_time=intent.start_time,
                device_id=device_id,
                capability_filter=capability_filter,
                command=intent.start_command,
            )
            # One-time rules are deliberately left with only their dated
            # trigger and device action. The nightly HomeBrain cleanup removes
            # expired generated rules after the safety grace period; self-pause
            # proved unreliable on the live hub and is no longer required.
            actions = (create_action,)
            return RuleAuthoringDecision(
                True,
                actions=actions,
                rule_names=(single_name,),
                target=target,
            )

        start_name = self._rule_name(intent.start_label, target_label, "Start")
        end_name = self._rule_name(intent.start_label, target_label, "End")
        existing = await self._existing_names() if can_read_rules else set()
        if existing is None:
            return RuleAuthoringDecision(
                True,
                "The rules were not queued because HomeBrain could not verify "
                "the current Rule Machine list. Retry after the hub read "
                "succeeds.",
                rule_names=(start_name, end_name),
                target=target,
            )
        duplicates = [name for name in (start_name, end_name) if name.casefold() in existing]
        if duplicates:
            return RuleAuthoringDecision(
                True,
                "No duplicate rules were queued because these Rule Machine rules "
                "already exist: " + ", ".join(f"**{name}**" for name in duplicates) + ".",
                rule_names=(start_name, end_name),
                target=target,
            )

        actions = (
            self._action(
                name=start_name,
                at_time=intent.start_time,
                device_id=device_id,
                capability_filter=capability_filter,
                command=intent.start_command,
            ),
            self._action(
                name=end_name,
                at_time=intent.end_time,
                device_id=device_id,
                capability_filter=capability_filter,
                command=intent.end_command,
            ),
        )
        return RuleAuthoringDecision(
            True,
            actions=actions,
            rule_names=(start_name, end_name),
            target=target,
        )


__all__ = [
    "RULE_MACHINE_GATEWAY",
    "RuleAuthoringDecision",
    "RuleAuthoringService",
]
