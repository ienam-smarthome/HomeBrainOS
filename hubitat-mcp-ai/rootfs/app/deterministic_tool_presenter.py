from __future__ import annotations

from typing import Any


_FILTER_TOOL = "homebrain_filter_devices"
_ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
_ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
_ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
_CONTROL_TOOL = "homebrain_control_devices"
_HUB_INFO_TOOL = "homebrain_hub_info_snapshot"

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
    raw_operator = str(data.get("operator") or "")
    operator = _OPERATORS.get(
        raw_operator,
        raw_operator or "matches",
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
    if attribute.casefold() == "motion" and raw_operator == "eq" and str(
        expected
    ).casefold() == "active":
        if not matches:
            return "No motion sensors are currently active."
        entries = [
            str(item.get("label") or item.get("id") or "Unknown sensor")
            for item in matches
        ]
        noun = "motion sensor is" if len(entries) == 1 else "motion sensors are"
        return f"{len(entries)} {noun} active: {_joined(entries)}."
    if attribute.casefold() == "battery" and raw_operator in {"lt", "lte"}:
        if not matches:
            return f"No devices have battery levels {operator} {expected}%."
        entries = []
        for item in matches:
            label = str(item.get("label") or item.get("id") or "Unknown device")
            value = item.get("value")
            entries.append(f"{label} ({value}%)")
        noun = "device has" if len(entries) == 1 else "devices have"
        return (
            f"{len(entries)} {noun} battery levels {operator} {expected}%: "
            f"{_joined(entries)}."
        )
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
    entries = [str(item.get("name") or "Unknown room") for item in rooms]
    noun = "room is" if len(entries) == 1 else "rooms are"
    return f"{len(entries)} {noun} active: {_joined(entries)}."


def _present_active_switches(data: dict[str, Any]) -> str:
    switches = [
        item for item in data.get("switches", []) if isinstance(item, dict)
    ]
    if not switches:
        return "No non-light switches are currently on."
    entries = [
        str(item.get("label") or item.get("id") or "Unknown switch")
        for item in switches
    ]
    noun = "switch is" if len(entries) == 1 else "switches are"
    if len(entries) <= 5:
        return f"{len(entries)} non-light {noun} on: {_joined(entries)}."
    grouped: dict[str, list[str]] = {}
    for item, label in zip(switches, entries):
        room = str(item.get("room") or "Other").strip() or "Other"
        grouped.setdefault(room, []).append(label)
    lines = [
        f"- **{room}:** {_joined(labels)}"
        for room, labels in grouped.items()
    ]
    return (
        f"{len(entries)} non-light switches are on:\n\n"
        + "\n".join(lines)
    )


def _present_active_lights(data: dict[str, Any]) -> str:
    lights = [
        item for item in data.get("lights", []) if isinstance(item, dict)
    ]
    if not lights:
        return "No lights are currently on."
    entries = [
        str(item.get("label") or item.get("id") or "Unknown light")
        for item in lights
    ]
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


def _present_hub_info(data: dict[str, Any]) -> str:
    scope = str(data.get("scope") or "full")
    installed = data.get("installed_firmware")
    available = data.get("available_firmware")
    update_available = bool(data.get("update_available"))
    parts = []
    if scope in {"firmware", "full"}:
        if installed and update_available and available:
            parts.append(
                f"Hub firmware {installed} is installed and {available} is available."
            )
        elif installed:
            parts.append(f"Hub firmware {installed} is up to date.")
        else:
            parts.append("The installed hub firmware version was not reported.")
    if scope in {"resources", "full"}:
        resources = []
        cpu_load = data.get("cpu_5_min")
        cpu_percent = data.get("cpu_percent")
        if cpu_load not in {None, ""}:
            cpu = f"{cpu_load}"
            if cpu_percent not in {None, ""}:
                cpu += f" / {cpu_percent}%"
            resources.append(f"**CPU load (5 min):** {cpu}")
        free_memory = data.get("free_memory")
        if free_memory not in {None, ""}:
            unit = str(data.get("free_memory_unit") or "").strip()
            resources.append(
                f"**Free memory:** {free_memory}{f' {unit}' if unit else ''}"
            )
        temperature = data.get("temperature")
        if temperature not in {None, ""}:
            rendered = str(temperature).strip()
            unit = str(data.get("temperature_unit") or "").strip()
            if unit and unit.casefold() not in rendered.casefold():
                rendered += f" {unit}"
            resources.append(f"**Temperature:** {rendered}")
        uptime = data.get("uptime")
        if uptime not in {None, ""}:
            resources.append(f"**Uptime:** {uptime}")
        database_size = data.get("database_size")
        if database_size not in {None, ""}:
            unit = str(data.get("database_size_unit") or "MB").strip()
            resources.append(f"**Database size:** {database_size} {unit}")
        if resources:
            parts.append("Hub resources:\n\n- " + "\n- ".join(resources))
    return " ".join(parts) or "The Hub Info device returned no usable attributes."


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
        _HUB_INFO_TOOL,
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
    if tool_name == _HUB_INFO_TOOL:
        return _present_hub_info(payload)
    return _present_control(payload)


__all__ = ["present_tool_result"]
