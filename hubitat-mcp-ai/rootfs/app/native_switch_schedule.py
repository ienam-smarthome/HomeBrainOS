"""Narrow MCP 5.1.6 native Rule Machine dated Switch contract.

The upstream #575 fix accepts type=date atDate# and persists it. Only
single-action, calendar-dated Switch rules are generated here. No remote calls,
confirmation, or permission changes. Never treat an undated clock as one-time.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

NAME_RE = re.compile(r"^HB one-shot \| .+ \(One-time (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\)$")
DATE_CAPABILITY = "Certain Time (and optional date)"


def create_dated_switch(
    *, name: str, parent_id: int, device_id: str,
    command: str, hub_local_at: datetime,
    best_practice_key: str | None = None,
) -> dict[str, Any]:
    """Produce one atomic native trigger/action candidate, never execute it."""
    if (not NAME_RE.fullmatch(name) or type(parent_id) is not int
            or parent_id <= 0 or not re.fullmatch(r"[1-9]\d*", str(device_id))
            or command not in {"on", "off"} or hub_local_at.tzinfo is None
            or hub_local_at.utcoffset() is None):
        raise ValueError("invalid native dated-switch proposal input")
    match = NAME_RE.fullmatch(name)
    assert match is not None
    if (hub_local_at.strftime("%Y-%m-%d") != match.group(1)
            or hub_local_at.strftime("%H:%M") != match.group(2)
            or hub_local_at.second != 0 or hub_local_at.microsecond != 0):
        raise ValueError("native rule name and scheduled local time disagree")
    day = hub_local_at.strftime("%Y-%m-%d")
    at_time = hub_local_at.strftime("%Y-%m-%dT%H:%M:%S.000%z")
    native: dict[str, Any] = {
        "operation": "create",
        "args": {
            "parent_id": parent_id,
            "name": name,
            "changes": [
                {"part": "trigger", "value": {
                    "capability": DATE_CAPABILITY,
                    "fields": [
                        {"name": "time#", "type": "enum", "value": "A specific time"},
                        {"name": "atTime#", "type": "time", "value": at_time},
                        {"name": "date#", "type": "bool", "value": True},
                        {"name": "year#", "type": "bool", "value": False},
                        {"name": "atDate#", "type": "date", "value": day},
                    ],
                }},
                {"part": "action", "value": {
                    "type": "switchActs", "subtype": "getOnOffSwitch",
                    "fields": [
                        {"name": "onOffSwitch.#", "type": "capability.switch",
                         "value": [str(device_id)]},
                        {"name": "onOff.#", "type": "bool",
                         "value": command == "on"},
                    ],
                }},
            ],
        },
    }
    if best_practice_key is not None:
        native["bestPracticeKey"] = best_practice_key
    return {"tool": "hub_set_rule", "args": native}


def dated_switch_proposal_error(payload: Any) -> str | None:
    """Strict syntactic gate on native create on proposal AND confirmation.

    This is not a source-attestation gate. The caller must separately verify
    current server version, native parent, target, backup and permission.
    """
    def invalid() -> str:
        return ("Invalid native dated Switch rule: require exactly one dated "
                "Certain Time trigger and one verified switch action, with "
                "matching calendar label/time. No write was queued.")
    if not isinstance(payload, dict) or set(payload) - {"operation", "args", "bestPracticeKey"}:
        return invalid()
    if payload.get("operation") != "create":
        return invalid()
    source = payload.get("args")
    if not isinstance(source, dict) or set(source) != {"parent_id", "name", "changes"}:
        return invalid()
    if type(source.get("parent_id")) is not int or source["parent_id"] <= 0:
        return invalid()
    name = source.get("name")
    match = NAME_RE.fullmatch(name) if isinstance(name, str) else None
    if match is None:
        return invalid()
    changes = source.get("changes")
    if not isinstance(changes, list) or len(changes) != 2:
        return invalid()
    try:
        t, a = changes
        if set(t) != {"part", "value"} or t["part"] != "trigger":
            return invalid()
        if set(a) != {"part", "value"} or a["part"] != "action":
            return invalid()
        trigger = t["value"]
        action = a["value"]
        if (set(trigger) != {"capability", "fields"}
                or trigger["capability"] != DATE_CAPABILITY
                or set(action) != {"type", "subtype", "fields"}
                or action["type"] != "switchActs"
                or action["subtype"] != "getOnOffSwitch"):
            return invalid()
        tf = trigger["fields"]
        af = action["fields"]
        if not isinstance(tf, list) or not isinstance(af, list):
            return invalid()
        if any(not isinstance(x, dict) or set(x) != {"name", "type", "value"}
               for x in tf + af):
            return invalid()
        if len({x["name"] for x in tf}) != len(tf) or len({x["name"] for x in af}) != len(af):
            return invalid()
        tm = {x["name"]: (x["type"], x["value"]) for x in tf}
        am = {x["name"]: (x["type"], x["value"]) for x in af}
        if set(tm) != {"time#", "atTime#", "date#", "year#", "atDate#"} or set(am) != {"onOffSwitch.#", "onOff.#"}:
            return invalid()
        if (tm["time#"] != ("enum", "A specific time")
                or tm["date#"] != ("bool", True)
                or tm["year#"] != ("bool", False)
                or tm["atDate#"] != ("date", match.group(1))
                or tm["atTime#"][0] != "time"
                or not isinstance(tm["atTime#"][1], str)):
            return invalid()
        when = datetime.strptime(tm["atTime#"][1], "%Y-%m-%dT%H:%M:%S.%f%z")
        if (when.strftime("%Y-%m-%d") != match.group(1)
                or when.strftime("%H:%M") != match.group(2)
                or when.second != 0 or when.microsecond != 0):
            return invalid()
        devices = am["onOffSwitch.#"]
        flag = am["onOff.#"]
        if (devices[0] != "capability.switch" or not isinstance(devices[1], list)
                or len(devices[1]) != 1
                or not isinstance(devices[1][0], str)
                or re.fullmatch(r"[1-9]\d*", devices[1][0]) is None
                or flag[0] != "bool" or type(flag[1]) is not bool):
            return invalid()
    except (KeyError, TypeError, ValueError, IndexError):
        return invalid()
    return None
