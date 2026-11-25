"""Fail-closed approval exemption for explicitly authorised, verified routine ON/OFF.

User's original *new* Ask may authorize a benign routine device command,
but never an automation, security/heating/network control, unknown capability,
multi-target write, stale tool receipt, or a write containing extra parameters.
The model chooses the actual native command; this module only evaluates whether
the separate *UI click* is redundant. Upstream MCP permission/validation and
the existing write submission boundary are never bypassed.
"""
from __future__ import annotations

import json
import re

from routine_action_fastpath import _normal, _original
from routine_component_light import component_parent_id, verified_physical_bridge_parent

# These are device-capability declarations, not inferred side-effect proofs.
# Never assume generic "Switch" alone establishes a benign operation.
_SENSITIVE_CAPABILITIES = frozenset({
    "Lock", "LockCodes", "SecurityKeypad", "Alarm", "SmokeDetector",
    "CarbonMonoxideDetector", "Thermostat", "ThermostatOperatingState",
    "ThermostatHeatingSetpoint", "ThermostatCoolingSetpoint", "HeatingSetpoint",
    "CoolingSetpoint", "FanControl", "FanSpeed", "Valve", "DoorControl",
    "GarageDoorControl", "WindowShade", "WindowShadeLevel",
    "WaterValve", "WaterSensor", "Smoke", "CarbonMonoxide",
})
# Extra denial guard for labels/names advertising sensitive consequences.
# NOT used to determine a target or to grant privileges.
_SENSITIVE_WORDS = re.compile(
    r"(?:^|[^a-z0-9])(?:internet|network|router|vpn|block|unblock|"
    r"restrict|security|alarm|lock|camera|cctv|heat|heating|heater|boiler|"
    r"thermostat|trv|radiator|fan|ventilation|hvac|valve|pump|garage|"
    r"door|gate|water|gas|fire|smoke|mesh|freezer|fridge|washing|"
    r"dryer|dehumidifier|oven|cooker|hob|kettle)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)
_PHYSICAL_PROTOCOLS = frozenset({"zigbee", "z-wave", "zwave", "matter"})


def trusted_switch_ids(raw: str) -> frozenset[str]:
    """An explicit list of numeric native IDs, not label globs or wildcards."""
    if not isinstance(raw, str) or len(raw) > 3000:
        return frozenset()
    items = [item.strip() for item in raw.split(",")]
    # A mistyped entry must not accidentally broaden other entries.
    if len(items) > 50 or any(
        item and (not item.isascii() or not item.isdigit() or len(item) > 12)
        for item in items
    ):
        return frozenset()
    return frozenset(x for x in items if x)


def source_verified_auto_approval_class(
    candidate: dict | None, receipts: list[dict], *,
    auto_lights: bool,
    safe_switch_ids: frozenset[str],
) -> str | None:
    """Exemption for a source-verified one-command, already-selected writer.

    The caller MUST already have matched candidate to the original user
    imperative and the exact model-selected native proposal using
    routine_candidate(). Here we additionally check original detail and
    native inventory for risk. A non-sensitive capability list by itself is
    not proof a generic switch is safe: non-light switches require an explicit
    installed native device-ID allowlist and physical mesh protocol.
    """
    if (not isinstance(candidate, dict)
            or candidate.get("command") not in ("on", "off")
            or not isinstance(receipts, list) or not receipts):
        return None
    identifier, label = candidate.get("device_id"), candidate.get("label")
    if (not isinstance(identifier, str) or not identifier
            or not isinstance(label, str) or not label):
        return None
    # A current component-light parent check may add one independent parent
    # detail. The write target itself must still have exactly ONE matching
    # original detailed read; unrelated details never grant authority.
    device_rows = [
        row for row in receipts
        if isinstance(row, dict) and row.get("name") == "hub_get_device"
        and isinstance(row.get("arguments"), dict)
        and str(row["arguments"].get("deviceId", "")).strip() == identifier
    ]
    if len(device_rows) != 1:
        return None
    detail_row = device_rows[0]
    args = detail_row.get("arguments")
    detail = _original(detail_row)
    if (not isinstance(args, dict)
            or str(args.get("deviceId", "")).strip() != identifier
            or detail is None
            or str(detail.get("id", "")).strip() != identifier
            or _normal(str(detail.get("label", ""))) != _normal(label)
            or detail.get("disabled") is True):
        return None
    caps = detail.get("capabilities")
    if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
        return None
    classes = set(caps)
    if ("Switch" not in classes or
            classes & _SENSITIVE_CAPABILITIES):
        return None
    if (_SENSITIVE_WORDS.search(label)
            or _SENSITIVE_WORDS.search(str(detail.get("name") or ""))):
        return None
    # Inventory also needs to have identified this particular source as a
    # visible, enabled device, not merely a model-asserted ID in its tool call.
    matched = []
    for row in receipts:
        if not isinstance(row, dict) or row.get("name") != "hub_list_devices":
            continue
        doc = _original(row)
        if not doc or not isinstance(doc.get("devices"), list):
            continue
        for item in doc["devices"]:
            if (isinstance(item, dict)
                    and str(item.get("id", "")).strip() == identifier):
                matched.append(item)
    if not matched or any(
        _normal(str(item.get("label", ""))) != _normal(label)
        or item.get("disabled") is True
        or _SENSITIVE_WORDS.search(str(item.get("driver") or ""))
        for item in matched
    ):
        return None
    if "Light" in classes and auto_lights:
        # Generic virtual/software switches stay gated. A Hubitat component
        # LIGHT may report virtual protocol even when backed by a physical
        # Matter/Zigbee/Z-Wave bridge. Require fresh ORIGINAL native source
        # proof of that bridge's physical identity, plus a child dimmer
        # capability and unambiguous parent-child relationship.
        if "Outlet" in classes:
            return None
        child_is_virtual = any(
            str(item.get("protocol", "")).casefold() == "virtual"
            or "virtual" in str(item.get("driver", "")).casefold()
            for item in matched
        )
        if child_is_virtual:
            if verified_physical_bridge_parent(candidate, receipts):
                return "verified_physical_bridge_component_light"
            return None
        # Additional unrelated details are not needed for direct lights and
        # must never add confidence to an otherwise unverified native light.
        if any(
            isinstance(row, dict) and row.get("name") == "hub_get_device"
            and row is not detail_row for row in receipts
        ):
            return None
        return "verified_light"
    # A generic switch/plug is not inherently benign. Require the user to
    # name trusted IDs in local add-on settings, plus original native physical
    # Zigbee/Z-Wave/Matter device evidence; never permit virtual policy relays.
    if (identifier in safe_switch_ids
            and "Light" not in classes
            and all(str(item.get("protocol", "")).lower()
                    in _PHYSICAL_PROTOCOLS for item in matched)
            and all("virtual" not in str(item.get("driver", "")).lower()
                    for item in matched)):
        return "explicitly_trusted_physical_switch"
    return None


def matches_original_native_write(candidate: dict, name: str, args: dict) -> bool:
    """Single-use permission is bound to the exact currently selected writer."""
    if (name != "hub_call_device_command"
            or not isinstance(candidate, dict)
            or not isinstance(args, dict)
            or set(args) - {"deviceId", "command", "parameters", "waitFor"}):
        return False
    return (
        type(args.get("deviceId")) in (str, int)
        and str(args["deviceId"]).strip() == candidate.get("device_id")
        and args.get("command") == candidate.get("command")
        and args.get("parameters") in (None, [])
        and args.get("waitFor") == candidate.get("wait_for")
    )


MAX_BATCH_TARGETS = 8


def batch_light_candidates(args: dict, receipts: list[dict]) -> list[dict] | None:
    """Structured on/off write (one device or a ``commands`` list) -> per-device candidates, else None.

    Reads only the call arguments and original read receipts. Any extra key, parameter, duplicate
    id, non-on/off command, or id this request never saw in a successful read fails closed.
    Labels are display/matching hints only: the per-device policy re-checks them against detail
    and inventory rows read for that exact id.
    """
    if not isinstance(args, dict):
        return None
    if set(args) == {"deviceId", "command"}:
        items = [args]
    elif (set(args) == {"commands"} and isinstance(args["commands"], list)
          and 1 <= len(args["commands"]) <= MAX_BATCH_TARGETS):
        items = args["commands"]
    else:
        return None
    labels: dict[str, str] = {}

    def remember(item) -> None:
        if (isinstance(item, dict) and item.get("accessible") is not False
                and str(item.get("id", "")).strip() and isinstance(item.get("label"), str)
                and item["label"].strip()):
            labels.setdefault(str(item["id"]).strip(), item["label"])

    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        doc = _original(row)
        if row.get("name") in ("hub_list_devices", "hub_get_room"):
            for item in (doc or {}).get("devices") or []:
                remember(item)
        elif row.get("name") == "hub_get_device" and doc:
            remember(doc)
    out, seen = [], set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {"command", "deviceId"}
                or item["command"] not in ("on", "off")
                or type(item["deviceId"]) not in (str, int)):
            return None
        identifier = str(item["deviceId"]).strip()
        if (not identifier.isascii() or not identifier.isdigit() or len(identifier) > 12
                or identifier in seen or identifier not in labels):
            return None
        seen.add(identifier)
        out.append({"device_id": identifier, "label": labels[identifier], "command": item["command"]})
    return out


async def read_batch_light_evidence(mcp, candidates: list[dict], receipts: list[dict], *,
                                    budget_seconds: float = 6.0) -> list[dict]:
    """Bounded native READS only: one detail per target plus each distinct bridge parent once."""
    import asyncio
    import time
    from routine_component_light import (_original_read_receipt, component_parent_id,
                                         read_component_parent_evidence)
    from mcp import MCPError
    start = time.monotonic()
    collected: list[dict] = []
    working = list(receipts)
    for cand in candidates:
        have = [r for r in working if isinstance(r, dict) and r.get("name") == "hub_get_device"
                and str((r.get("arguments") or {}).get("deviceId", "")).strip() == cand["device_id"]]
        if have:
            continue
        remaining = budget_seconds - (time.monotonic() - start)
        if remaining <= 0.5:
            return collected
        args = {"deviceId": cand["device_id"]}
        begin = time.monotonic()
        try:
            raw = await asyncio.wait_for(mcp.call("hub_get_device", args), timeout=remaining)
            record = _original_read_receipt("hub_get_device", args, raw,
                                            round((time.monotonic() - begin) * 1000))
        except (MCPError, asyncio.TimeoutError, ValueError) as exc:
            record = _original_read_receipt("hub_get_device", args, None,
                                            round((time.monotonic() - begin) * 1000), error=str(exc))
        collected.append(record)
        working.append(record)
    listed = {str(i.get("id", "")).strip() for r in working if isinstance(r, dict)
              and r.get("name") == "hub_list_devices" and r.get("success") is True
              for i in ((_original(r) or {}).get("devices") or []) if isinstance(i, dict)}
    missing = [c["device_id"] for c in candidates if c["device_id"] not in listed]
    remaining = budget_seconds - (time.monotonic() - start)
    if missing and remaining > 0.5:
        args = {"deviceIds": missing}
        begin = time.monotonic()
        try:
            raw = await asyncio.wait_for(mcp.call("hub_list_devices", args), timeout=remaining)
            record = _original_read_receipt("hub_list_devices", args, raw,
                                            round((time.monotonic() - begin) * 1000))
        except (MCPError, asyncio.TimeoutError, ValueError) as exc:
            record = _original_read_receipt("hub_list_devices", args, None,
                                            round((time.monotonic() - begin) * 1000), error=str(exc))
        collected.append(record)
        working.append(record)
    parents: list[str] = []
    for cand in candidates:
        scoped = [r for r in working if not (isinstance(r, dict) and r.get("name") == "hub_get_device"
                  and str((r.get("arguments") or {}).get("deviceId", "")).strip() != cand["device_id"])]
        parent = component_parent_id(cand, scoped)
        if parent and parent not in parents:
            parents.append(parent)
    for parent in parents:
        remaining = budget_seconds - (time.monotonic() - start)
        if remaining <= 0.5:
            break
        if any(isinstance(r, dict) and r.get("name") == "hub_get_device" and r.get("success") is True
               and str((r.get("arguments") or {}).get("deviceId", "")).strip() == parent
               for r in working):
            continue
        collected.extend(await read_component_parent_evidence(mcp, parent, budget_seconds=min(4.0, remaining)))
    return collected


def batch_light_authorization(candidates: list[dict], receipts: list[dict], *,
                              safe_switch_ids: frozenset[str] = frozenset()) -> bool:
    """True only when EVERY target passes the single-device policy on its own evidence."""
    for cand in candidates:
        scoped = []
        parent_ids = set()
        details = [r for r in receipts if isinstance(r, dict) and r.get("name") == "hub_get_device"]
        own = [r for r in details if str((r.get("arguments") or {}).get("deviceId", "")).strip() == cand["device_id"]]
        if len(own) != 1:
            return False
        parent = component_parent_id(cand, [r for r in receipts if r not in details] + own)
        keep = {id(own[0])}
        if parent:
            parent_rows = [r for r in details if str((r.get("arguments") or {}).get("deviceId", "")).strip() == parent]
            keep.update(id(r) for r in parent_rows)
        scoped = []
        seen_reads: set[str] = set()
        for r in receipts:
            if r in details and id(r) not in keep:
                continue
            if isinstance(r, dict) and r.get("client_component_parent_verification_read"):
                # Identical client-issued parent reads (one per target) are one piece of evidence.
                signature = json.dumps([r.get("name"), r.get("arguments")], sort_keys=True, default=str)
                if signature in seen_reads:
                    continue
                seen_reads.add(signature)
            scoped.append(r)
        if source_verified_auto_approval_class(cand, scoped, auto_lights=True,
                                               safe_switch_ids=safe_switch_ids) is None:
            return False
    return True


INTERNET_BLOCK_COMMANDS = frozenset({"blockInternet", "allowInternet"})


def _attr_value(detail: dict, name: str):
    for attr in detail.get("attributes") or []:
        if isinstance(attr, dict) and attr.get("name") == name:
            return attr.get("value")
    return None


def internet_block_candidate(args: dict, receipts: list[dict]) -> dict | None:
    """Exact parameterless blockInternet/allowInternet on ONE per-device internet-control device.

    Decided only from the declared tool call and this request's original successful
    ``hub_get_device`` read: the device must itself declare that exact command, an
    ``internetAccess`` attribute and its own non-empty deviceIP and deviceMAC (so an
    all-devices switch never qualifies). Labels and user prose are never consulted.
    """
    if (not isinstance(args, dict) or set(args) != {"deviceId", "command"}
            or args.get("command") not in INTERNET_BLOCK_COMMANDS
            or type(args.get("deviceId")) not in (str, int)):
        return None
    identifier = str(args["deviceId"]).strip()
    if not identifier.isdigit():
        return None
    rows = [r for r in receipts if isinstance(r, dict) and r.get("name") == "hub_get_device"
            and r.get("success") is True and isinstance(r.get("arguments"), dict)
            and str(r["arguments"].get("deviceId", "")).strip() == identifier]
    if len(rows) != 1:
        return None
    detail = _original(rows[0])
    if (detail is None or str(detail.get("id", "")).strip() != identifier
            or detail.get("disabled") is True
            or not isinstance(detail.get("label"), str) or not detail["label"].strip()):
        return None
    caps = detail.get("capabilities")
    if not isinstance(caps, list) or "Switch" not in caps or set(caps) & _SENSITIVE_CAPABILITIES:
        return None
    if _attr_value(detail, "internetAccess") not in ("allowed", "blocked"):
        return None
    for needed in ("deviceIP", "deviceMAC"):
        value = _attr_value(detail, needed)
        if not isinstance(value, str) or not value.strip():
            return None
    declared = [c for c in detail.get("commands") or []
                if isinstance(c, dict) and c.get("name") == args["command"]
                and c.get("arguments") in (None, [])]
    if len(declared) != 1:
        return None
    return {"device_id": identifier, "command": args["command"], "label": detail["label"].strip()}


def internet_block_answer(candidate: dict, receipts: list[dict]) -> str | None:
    """Receipt-backed completion for an accepted block/allow command (no extra model round)."""
    writes = [r for r in receipts if isinstance(r, dict) and r.get("possible_native_action") is True]
    if len(writes) != 1 or writes[0].get("name") != "hub_call_device_command":
        return None
    args = writes[0].get("arguments")
    if (not isinstance(args, dict) or args.get("command") != candidate["command"]
            or str(args.get("deviceId", "")).strip() != candidate["device_id"]):
        return None
    doc = _original(writes[0])
    if (doc is None or doc.get("success") is not True or doc.get("command") != candidate["command"]
            or doc.get("parameters") not in (None, [])):
        return None
    state = doc.get("state")
    reported = None
    if isinstance(state, dict) and isinstance(state.get("internetAccess"), dict):
        reported = state["internetAccess"].get("value")
    expected = "blocked" if candidate["command"] == "blockInternet" else "allowed"
    label = re.sub(r"([\\\x60*_{}\[\]()#+!|>])", r"\\\1", candidate["label"])
    verb = "block" if expected == "blocked" else "allow"
    if reported == expected:
        return (f"**{label}: {verb} command accepted.** Hubitat's reply reports internet access "
                f"as {expected}. That is the hub's stored state, not a network test of the device.")
    return (f"**{label}: {verb} command accepted by Hubitat.** Its reply did not report "
            f"internet access as {expected}, so check the device before relying on it.")


def batch_light_answer(args: dict, candidates: list[dict], receipts: list[dict]) -> str | None:
    """Receipt-backed one-line completion for an accepted light on/off write (no review rounds)."""
    writes = [r for r in receipts if isinstance(r, dict) and r.get("possible_native_action") is True]
    if len(writes) != 1 or writes[0].get("name") != "hub_call_device_command" \
            or writes[0].get("arguments") != args:
        return None
    doc = _original(writes[0])
    if not isinstance(doc, dict) or doc.get("success") is not True:
        return None
    if "commands" in args:
        results = doc.get("results")
        if (not isinstance(results, list) or len(results) != len(candidates)
                or doc.get("failedCount") not in (0, None)
                or doc.get("sentCount") not in (len(candidates), None)):
            return None
        names = []
        for cand in candidates:
            hit = [r for r in results if isinstance(r, dict)
                   and str(r.get("deviceId", "")).strip() == cand["device_id"]]
            if (len(hit) != 1 or hit[0].get("success") is not True
                    or hit[0].get("command") != cand["command"]):
                return None
            names.append(str(hit[0].get("device") or cand["label"]))
    else:
        cand = candidates[0]
        if doc.get("command") != cand["command"]:
            return None
        names = [str(doc.get("device") or cand["label"])]
    direction = candidates[0]["command"].upper()
    if any(c["command"] != candidates[0]["command"] for c in candidates):
        direction = "ON/OFF"
    safe = ", ".join(re.sub(r"([\\\x60*_{}\[\]()#+!|>])", r"\\\1", n) for n in names)
    count = f"{len(names)} of {len(names)} devices" if len(names) > 1 else "the device"
    return (f"**{safe}: {direction} command accepted.** Hubitat reported {count} accepted with no "
            "failures. That is the hub's reply, not a check of the physical lights.")
