"""Fail-closed approval exemption for explicitly authorised, verified routine ON/OFF.

User's original *new* Ask may authorize a benign routine device command,
but never an automation, security/heating/network control, unknown capability,
multi-target write, stale tool receipt, or a write containing extra parameters.
The model chooses the actual native command; this module only evaluates whether
the separate *UI click* is redundant. Upstream MCP permission/validation and
the existing write submission boundary are never bypassed.
"""
from __future__ import annotations

import re

from routine_action_fastpath import _normal, _original

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
    device_rows = [
        row for row in receipts
        if isinstance(row, dict) and row.get("name") == "hub_get_device"
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
        # Unknown mixed-purpose Light + Outlet or software/network controllers
        # remain approval-required, even if the name looks like a light.
        if "Outlet" in classes or any(
            str(item.get("protocol", "")).lower() == "virtual"
            or "virtual" in str(item.get("driver", "")).lower()
            for item in matched
        ):
            return None
        return "verified_light"
    # A generic switch/plug is not inherently benign. Require the user to
    # name trusted IDs in local add-on settings, plus original native physical
    # Zigbee/Z-Wave/Matter device evidence; never permit virtual policy relays.
    if (identifier in safe_switch_ids
            and "Light" not in classes
            and any("Switch" in classes for _ in (0,))
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
