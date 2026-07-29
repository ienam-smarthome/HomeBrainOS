from __future__ import annotations

from typing import Any


_FILTER_TOOL = "homebrain_filter_devices"
_ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
_ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
_ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
_CONTROL_TOOL = "homebrain_control_devices"

_OPERATORS = {
    "eq": "=",
    "ne": "!=",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
    "contains": "contains",
    "exists": "exists",
    "not_exists": "does not exist",
}


def _joined(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _error(data: dict[str, Any], fallback: str) -> str:
    return str(data.get("error") or fallback)


def _present_filter(data: dict[str, Any]) -> str:
    attribute = str(data.get("attribute") or "attribute")
    operator = _OPERATORS.get(
        str(data.get("operator") or ""),
        str(data.get("operator") or "matches"),
    )
    expected = data.get("comparison_value")
    condition = (
        f"{attribute} {operator}"
        if operator in {"exists", "does not exist"}
        else f"{attribute} {operator} {expected}"
    )
    matches = [
        item for item in data.get("matches", []) if isinstance(item, dict)
    ]
    if not matches:
        return f"No devices matched {condition}."
    entries = []
    for item in matches:
        label = str(item.get("label") or item.get("id") or "Unknown device")
        value = item.get("value")
        room = str(item.get("room") or "").strip()
        suffix = f" ({room})" if room else ""
        entries.append(f"{label}{suffix}: {attribute}={value}")
    noun = "device" if len(entries) == 1 else "devices"
    return f"{len(entries)} {noun} matched {condition}: {_joined(entries)}."


def _present_active_rooms(data: dict[str, Any]) -> str:
    rooms = [
        item for item in data.get("active_rooms", []) if isinstance(item, dict)
    ]
    if not rooms:
        return "No rooms are currently active."
    entries = []
    for item in rooms:
        name = str(item.get("name") or "Unknown room")
        reasons = [
            str(reason) for reason in item.get("reasons", []) if reason
        ]
        entries.append(f"{name} ({', '.join(reasons)})" if reasons else name)
    noun = "room is" if len(entries) == 1 else "rooms are"
    return f"{len(entries)} active {noun}: {_joined(entries)}."


def _present_active_switches(data: dict[str, Any]) -> str:
    switches = [
        item for item in data.get("switches", []) if isinstance(item, dict)
    ]
    if not switches:
        return "No non-light switches are currently on."
    entries = []
    for item in switches:
        label = str(item.get("label") or item.get("id") or "Unknown switch")
        room = str(item.get("room") or "").strip()
        entries.append(f"{label} ({room})" if room else label)
    noun = "switch is" if len(entries) == 1 else "switches are"
    return f"{len(entries)} non-light {noun} on: {_joined(entries)}."


def _present_active_lights(data: dict[str, Any]) -> str:
    lights = [
        item for item in data.get("lights", []) if isinstance(item, dict)
    ]
    if not lights:
        return "No lights are currently on."
    entries = []
    for item in lights:
        label = str(item.get("label") or item.get("id") or "Unknown light")
        room = str(item.get("room") or "").strip()
        entries.append(f"{label} ({room})" if room else label)
    noun = "light is" if len(entries) == 1 else "lights are"
    return f"{len(entries)} {noun} on: {_joined(entries)}."


def _present_control(data: dict[str, Any]) -> str:
    succeeded = [
        str(item.get("label"))
        for item in data.get("succeeded", [])
        if isinstance(item, dict) and item.get("label")
    ]
    unverified = [
        str(item.get("label"))
        for item in data.get("failed", [])
        if (
            isinstance(item, dict)
            and item.get("label")
            and item.get("command_sent") is True
            and item.get("verified") is False
        )
    ]
    failed = [
        str(item.get("label"))
        for item in data.get("failed", [])
        if (
            isinstance(item, dict)
            and item.get("label")
            and item.get("command_sent") is not True
        )
    ]
    if not data.get("success"):
        if succeeded or unverified or failed:
            parts = []
            if succeeded:
                parts.append(f"Succeeded: {_joined(succeeded)}.")
            if unverified:
                parts.append(
                    f"Command sent but state verification failed: "
                    f"{_joined(unverified)}."
                )
            if failed:
                parts.append(f"Failed: {_joined(failed)}.")
            return " ".join(parts)
        return _error(data, "The Hubitat device command failed.")
    verb = {"on": "Turned on", "off": "Turned off", "toggle": "Toggled"}.get(
        str(data.get("command")), "Controlled"
    )
    return f"{verb} {_joined(succeeded) or 'the selected devices'}."


def present_tool_result(
    tool_name: str,
    data: Any,
    *,
    failed: bool = False,
    fallback_error: str = "",
) -> str | None:
    """Render authoritative local-tool data without another model round."""

    if tool_name not in {
        _FILTER_TOOL,
        _ACTIVE_LIGHTS_TOOL,
        _ACTIVE_ROOMS_TOOL,
        _ACTIVE_SWITCHES_TOOL,
        _CONTROL_TOOL,
    }:
        return None
    payload = data if isinstance(data, dict) else {}
    if failed and tool_name != _CONTROL_TOOL:
        return _error(payload, fallback_error or "The live Hubitat query failed.")
    if tool_name == _FILTER_TOOL:
        return _present_filter(payload)
    if tool_name == _ACTIVE_LIGHTS_TOOL:
        return _present_active_lights(payload)
    if tool_name == _ACTIVE_ROOMS_TOOL:
        return _present_active_rooms(payload)
    if tool_name == _ACTIVE_SWITCHES_TOOL:
        return _present_active_switches(payload)
    return _present_control(payload)


__all__ = ["present_tool_result"]
