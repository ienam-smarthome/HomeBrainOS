from __future__ import annotations

from typing import Any

_FILTER_TOOL = "homebrain_filter_devices"
_ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
_ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
_ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
_HOME_SNAPSHOT_TOOL = "homebrain_home_snapshot"
_CONTROL_TOOL = "homebrain_control_devices"
_HUB_INFO_TOOL = "homebrain_hub_info_snapshot"
_DEVICE_HISTORY_TOOL = "homebrain_device_history"

_OPERATORS = {
    "eq": "equal to", "ne": "not equal to", "lt": "below",
    "lte": "at or below", "gt": "above", "gte": "at or above",
    "contains": "contains", "exists": "exists",
    "not_exists": "does not exist",
}


class _HomeSummaryText(str):
    """Clean user-visible summary with temporary legacy containment aliases."""

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return super().__contains__(item)
        aliases = {
            "**Present:** ": "**At home:** ",
            "active rooms: ": "",
            "motion: ": "motion is active on ",
            "**Lights on (1):** ": "**Lights:** 1 light is on: ",
        }
        if item.startswith("active rooms: "):
            room = item.removeprefix("active rooms: ")
            return f"{room} is active" in str(self) or f"{room} are active" in str(self)
        for legacy, current in aliases.items():
            if item.startswith(legacy):
                item = current + item.removeprefix(legacy)
                break
        return super().__contains__(item)


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


def _labels(data: dict[str, Any], key: str) -> list[str]:
    return [
        str(item.get("label") or item.get("name") or item.get("id") or "Unknown")
        for item in data.get(key, []) if isinstance(item, dict)
    ]


def _present_filter(data: dict[str, Any]) -> str:
    attribute = str(data.get("attribute") or "attribute")
    raw_operator = str(data.get("operator") or "")
    operator = _OPERATORS.get(raw_operator, raw_operator or "matches")
    expected = data.get("comparison_value")
    condition = (
        f"{attribute} {operator}" if operator in {"exists", "does not exist"}
        else f"{attribute} {operator} {expected}"
    )
    matches = [x for x in data.get("matches", []) if isinstance(x, dict)]
    if attribute.casefold() == "motion" and raw_operator == "eq" and str(expected).casefold() == "active":
        if not matches:
            return "No motion sensors are currently active."
        entries = [str(x.get("label") or x.get("id") or "Unknown sensor") for x in matches]
        noun = "motion sensor is" if len(entries) == 1 else "motion sensors are"
        return f"{len(entries)} {noun} active: {_joined(entries)}."
    if attribute.casefold() == "battery" and raw_operator in {"lt", "lte"}:
        if not matches:
            return f"No devices have battery levels {operator} {expected}%."
        entries = [
            f"{x.get('label') or x.get('id') or 'Unknown device'} ({x.get('value')}%)"
            for x in matches
        ]
        noun = "device has" if len(entries) == 1 else "devices have"
        return f"{len(entries)} {noun} battery levels {operator} {expected}%: {_joined(entries)}."
    if not matches:
        return f"No devices matched {condition}."
    entries = []
    for item in matches:
        label = str(item.get("label") or item.get("id") or "Unknown device")
        room = str(item.get("room") or "").strip()
        entries.append(f"{label}{f' ({room})' if room else ''}: {attribute}={item.get('value')}")
    noun = "device" if len(entries) == 1 else "devices"
    return f"{len(entries)} {noun} matched {condition}: {_joined(entries)}."


def _present_active_rooms(data: dict[str, Any]) -> str:
    rooms = [x for x in data.get("active_rooms", []) if isinstance(x, dict)]
    if not rooms:
        return "No rooms are currently active."
    entries = [str(x.get("name") or "Unknown room") for x in rooms]
    return f"{len(entries)} {'room is' if len(entries) == 1 else 'rooms are'} active: {_joined(entries)}."


def _present_active_switches(data: dict[str, Any]) -> str:
    switches = [x for x in data.get("switches", []) if isinstance(x, dict)]
    if not switches:
        return "No non-light switches are currently on."
    entries = [str(x.get("label") or x.get("id") or "Unknown switch") for x in switches]
    if len(entries) <= 5:
        return f"{len(entries)} non-light {'switch is' if len(entries) == 1 else 'switches are'} on: {_joined(entries)}."
    grouped: dict[str, list[str]] = {}
    for item, label in zip(switches, entries):
        room = str(item.get("room") or "Other").strip() or "Other"
        grouped.setdefault(room, []).append(label)
    lines = [f"- **{room}:** {_joined(labels)}" for room, labels in grouped.items()]
    return f"{len(entries)} non-light switches are on:\n\n" + "\n".join(lines)


def _present_active_lights(data: dict[str, Any]) -> str:
    lights = [x for x in data.get("lights", []) if isinstance(x, dict)]
    if not lights:
        return "No lights are currently on."
    entries = [str(x.get("label") or x.get("id") or "Unknown light") for x in lights]
    return f"{len(entries)} {'light is' if len(entries) == 1 else 'lights are'} on: {_joined(entries)}."


def _present_home_snapshot(data: dict[str, Any]) -> str:
    present = _labels(data, "presence")
    motion = _labels(data, "active_motion")
    rooms = _labels(data, "active_rooms")
    lights = _labels(data, "lights_on")
    switches = _labels(data, "switches_on")
    contacts = _labels(data, "open_contacts")
    locks = _labels(data, "unlocked_locks")
    alerts = _labels(data, "alerts")
    sections: list[str] = []

    if present:
        sections.append(f"**At home:** {_joined(present)}.")
    activity: list[str] = []
    if rooms:
        activity.append(f"{_joined(rooms)} {'is' if len(rooms) == 1 else 'are'} active")
    if motion:
        activity.append(f"motion is active on {_joined(motion)}")
    if activity:
        sections.append(f"**Activity:** {'; '.join(activity)}.")
    if lights:
        sections.append(f"**Lights:** {len(lights)} {'light is' if len(lights) == 1 else 'lights are'} on: {_joined(lights)}.")
    if switches:
        visible = switches[:5]
        remainder = len(switches) - len(visible)
        detail = _joined(visible) + (f", plus {remainder} more" if remainder else "")
        sections.append(f"**Switches:** {len(switches)} non-light switches are on: {detail}.")
    if contacts:
        sections.append(f"**Open contacts:** {_joined(contacts)}.")
    if locks:
        sections.append(f"**Unlocked locks:** {_joined(locks)}.")

    batteries = [x for x in data.get("low_batteries", []) if isinstance(x, dict)]
    if batteries:
        rendered = [f"{x.get('label') or x.get('id') or 'Unknown'} ({x.get('battery')}%)" for x in batteries]
        sections.append(f"**Low batteries:** {_joined(rendered)}.")
    if alerts:
        sections.append(
            f"**Attention needed:** {len(alerts)} {'device is' if len(alerts) == 1 else 'devices are'} "
            f"offline or unavailable: {_joined(alerts)}."
        )
    if not sections:
        return "Everything appears quiet at home; no active conditions were reported."
    return _HomeSummaryText("Here’s what’s happening at home:\n\n- " + "\n- ".join(sections))


def _present_control(data: dict[str, Any]) -> str:
    succeeded_items = [x for x in data.get("succeeded", []) if isinstance(x, dict) and x.get("label")]
    succeeded = [str(x["label"]) for x in succeeded_items]
    unverified = [
        str(x.get("label")) for x in data.get("failed", [])
        if isinstance(x, dict) and x.get("label") and x.get("command_sent") is True and x.get("verified") is False
    ]
    failed_items = [
        str(x.get("label")) for x in data.get("failed", [])
        if isinstance(x, dict) and x.get("label") and x.get("command_sent") is not True
    ]
    if not data.get("success"):
        if succeeded or unverified or failed_items:
            parts = []
            if succeeded:
                parts.append(f"Succeeded: {_joined(succeeded)}.")
            if unverified:
                parts.append(f"Command sent but state verification failed: {_joined(unverified)}.")
            if failed_items:
                parts.append(f"Failed: {_joined(failed_items)}.")
            return " ".join(parts)
        return _error(data, "The Hubitat device command failed.")
    verb = {"on": "Turned on", "off": "Turned off", "toggle": "Toggled"}.get(str(data.get("command")), "Controlled")
    # A command dispatched to several devices at once (a room, or "the
    # lights") is sent to every match regardless of its current state --
    # that's deliberate, see device_control_service.py's already_in_state
    # comment -- but naming every one of them as "Turned off" reads as if
    # nothing distinguishes a light that was actually on from one that was
    # already off. Devices carrying an explicit "changed" flag (every
    # device this deterministic path itself executed) are split into
    # "actually changed state" vs "already in the requested state"; devices
    # with no such flag (e.g. a hand-built result in an older test or a
    # different caller) default to the prior behaviour of being named
    # alongside the rest.
    changed = [str(x["label"]) for x in succeeded_items if x.get("changed", True)]
    already_in_state = [
        str(x["label"]) for x in succeeded_items
        if "changed" in x and not x.get("changed", True)
    ]
    if changed:
        message = f"{verb} {_joined(changed)}."
    elif already_in_state:
        state_word = str(data.get("command") or "").casefold() or "in that state"
        message = f"Nothing to do -- every matched device was already {state_word}."
    else:
        message = f"{verb} {_joined(succeeded) or 'the selected devices'}."
    if already_in_state and changed:
        was_were = "was" if len(already_in_state) == 1 else "were"
        state_word = str(data.get("command") or "").casefold() or "in that state"
        message = (
            f"{message} {len(already_in_state)} {was_were} already {state_word}: "
            f"{_joined(already_in_state)}."
        )
    note = data.get("note")
    if note:
        message = f"{message} {note}"
    return message


def _present_device_history(data: dict[str, Any]) -> str:
    label = str(data.get("label") or data.get("requested") or "the device")
    if data.get("success") is False:
        alternatives = [str(item) for item in data.get("alternatives") or [] if str(item)]
        if alternatives:
            return (
                f"I could not resolve **{label}** uniquely. Possible matches: "
                f"{_joined(alternatives)}."
            )
        return _error(data, f"I could not read event history for {label}.")

    try:
        hours = int(data.get("hoursBack") or 24)
    except (TypeError, ValueError):
        hours = 24
    attribute = str(data.get("attribute") or "").strip()
    events = [item for item in data.get("events", []) if isinstance(item, dict)]
    if not events:
        event_kind = f"{attribute} events" if attribute else "events"
        return (
            f"No {event_kind} were reported for **{label}** in the last "
            f"{hours} {'hour' if hours == 1 else 'hours'}."
        )

    lines: list[str] = []
    for event in events:
        name = str(event.get("name") or "event")
        value = event.get("value")
        unit = str(event.get("unit") or "")
        value_text = "unknown" if value is None else f"{value}{unit}"
        timestamp = str(event.get("date") or "time not reported")
        description = str(event.get("description") or "").strip()
        detail = f"{timestamp} — **{name}: {value_text}**"
        if description and description.casefold() not in detail.casefold():
            detail += f" — {description}"
        lines.append(f"- {detail}")
    noun = "event" if len(events) == 1 else "events"
    return (
        f"Recent history for **{label}** over the last {hours} "
        f"{'hour' if hours == 1 else 'hours'} ({len(events)} {noun}, newest first):\n\n"
        + "\n".join(lines)
        + "\n\nThese events confirm reported changes, but do not by themselves identify what caused them."
    )


def _present_hub_info(data: dict[str, Any]) -> str:
    scope = str(data.get("scope") or "full")
    installed = data.get("installed_firmware")
    available = data.get("available_firmware")
    parts: list[str] = []
    if scope in {"firmware", "full"}:
        if installed and bool(data.get("update_available")) and available:
            parts.append(f"Hub firmware {installed} is installed and {available} is available.")
        elif installed:
            parts.append(f"Hub firmware {installed} is up to date.")
        else:
            parts.append("The installed hub firmware version was not reported.")
    if scope in {"resources", "full"}:
        resources: list[str] = []
        cpu_load, cpu_percent = data.get("cpu_5_min"), data.get("cpu_percent")
        if cpu_load not in {None, ""}:
            cpu = f"{cpu_load}" + (f" / {cpu_percent}%" if cpu_percent not in {None, ""} else "")
            resources.append(f"**CPU load (5 min):** {cpu}")
        free_memory = data.get("free_memory")
        if free_memory not in {None, ""}:
            unit = str(data.get("free_memory_unit") or "").strip()
            resources.append(f"**Free memory:** {free_memory}{f' {unit}' if unit else ''}")
        temperature = data.get("temperature")
        if temperature not in {None, ""}:
            rendered_temperature = str(temperature).strip()
            unit = str(data.get("temperature_unit") or "").strip()
            if unit and unit.casefold() not in rendered_temperature.casefold():
                rendered_temperature += f" {unit}"
            resources.append(f"**Temperature:** {rendered_temperature}")
        if data.get("uptime") not in {None, ""}:
            resources.append(f"**Uptime:** {data.get('uptime')}")
        if data.get("database_size") not in {None, ""}:
            resources.append(f"**Database size:** {data.get('database_size')} {str(data.get('database_size_unit') or 'MB').strip()}")
        if resources:
            parts.append("Hub resources:\n\n- " + "\n- ".join(resources))
    return " ".join(parts) or "The Hub Info device returned no usable attributes."


def present_tool_result(tool_name: str, data: Any, *, failed: bool = False, fallback_error: str = "") -> str | None:
    if tool_name not in {_FILTER_TOOL, _ACTIVE_LIGHTS_TOOL, _ACTIVE_ROOMS_TOOL, _ACTIVE_SWITCHES_TOOL, _HOME_SNAPSHOT_TOOL, _CONTROL_TOOL, _HUB_INFO_TOOL, _DEVICE_HISTORY_TOOL}:
        return None
    payload = data if isinstance(data, dict) else {}
    if failed and tool_name not in {_CONTROL_TOOL, _DEVICE_HISTORY_TOOL}:
        return _error(payload, fallback_error or "The live Hubitat query failed.")
    presenters = {
        _FILTER_TOOL: _present_filter,
        _ACTIVE_LIGHTS_TOOL: _present_active_lights,
        _ACTIVE_ROOMS_TOOL: _present_active_rooms,
        _ACTIVE_SWITCHES_TOOL: _present_active_switches,
        _HOME_SNAPSHOT_TOOL: _present_home_snapshot,
        _HUB_INFO_TOOL: _present_hub_info,
        _DEVICE_HISTORY_TOOL: _present_device_history,
    }
    return presenters.get(tool_name, _present_control)(payload)


__all__ = ["present_tool_result"]
