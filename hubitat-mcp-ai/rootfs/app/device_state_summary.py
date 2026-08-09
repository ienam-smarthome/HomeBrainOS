from __future__ import annotations

import re
from typing import Any


_LEADING_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _numeric_prefix(text: str) -> float | None:
    match = _LEADING_NUMBER.match(text.strip())
    if match is None:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def device_attributes(device: dict[str, Any]) -> dict[str, Any]:
    """Merge every Hubitat state container into one canonical attribute map.

    Some community/bridge drivers (seen live on Home-Assistant-imported
    sensors, e.g. Octopus Energy) report a reading as a `value`/`valueStr`
    pair where `value` is always null and the real, human-formatted number
    lives only in `valueStr` (e.g. "231 W"). Nothing downstream -- contextual
    reads, ranking/aggregation, the compact device manifest -- looks at
    `valueStr`, so these devices silently read as having no value at all
    even though the reading is right there. When `value` comes back null
    and a sibling `valueStr` has a parseable leading number, backfill
    `value` with that number so every existing numeric-attribute consumer
    picks it up for free; `valueStr` is left untouched alongside it.
    """

    attributes: dict[str, Any] = {}
    for raw in (
        device.get("attributes"),
        device.get("states"),
        device.get("currentStates"),
    ):
        if isinstance(raw, dict):
            attributes.update(raw)
            continue
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("attribute")
            if name:
                attributes[str(name)] = item.get(
                    "currentValue", item.get("value")
                )
    if attributes.get("value") is None:
        value_str = attributes.get("valueStr")
        if isinstance(value_str, str) and value_str.strip():
            numeric = _numeric_prefix(value_str)
            if numeric is not None:
                attributes["value"] = numeric
    return attributes


def room_name(device: dict[str, Any]) -> str | None:
    room: Any = device.get("roomName") or device.get("room")
    if isinstance(room, dict):
        room = room.get("name") or room.get("label")
    value = str(room or "").strip()
    return value if value and value.lower() not in {"none", "null", "unassigned"} else None


def capability_names(device: dict[str, Any]) -> set[str]:
    """Return every capability name a device advertises, casefolded.

    Single source of truth for capability extraction -- this used to be
    duplicated as a private `_capability_names` inside
    `device_query_service.py` with its own, richer light-detection logic
    (capabilities intersecting `{"light", "bulb", "colorcontrol",
    "colortemperature"}`, plus a label check for "lamp"/"bulb"/" light")
    while `is_light_device` below only ever did a crude substring search
    over `str(capabilities)` for "light"/"bulb" -- missing color bulbs
    that only advertise `ColorControl`/`ColorTemperature` and devices
    labelled e.g. "Bedroom Lamp" with no light-ish capability token at
    all. The two diverging implementations meant a color bulb could be
    included as a light in one code path and excluded in another. Both
    now share this helper and the richer detection logic in
    `is_light_device` below.
    """

    values = device.get("capabilities") or []
    if isinstance(values, dict):
        values = values.keys()
    names: set[str] = set()
    for item in values if isinstance(values, (list, tuple, set, dict)) else []:
        if isinstance(item, dict):
            item = item.get("name") or item.get("capability")
        if item:
            names.add(str(item).casefold())
    return names


def is_light_device(device: dict[str, Any]) -> bool:
    capabilities = capability_names(device)
    label = str(device.get("label") or device.get("name") or "").casefold()
    return bool(
        capabilities & {"light", "bulb", "colorcontrol", "colortemperature"}
    ) or any(word in label for word in (" light", "lamp", "bulb"))


def active_non_light_switches(
    devices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return switched-on devices, excluding every light/bulb device."""

    matches = []
    for device in devices:
        attributes = device_attributes(device)
        switch = str(attributes.get("switch") or device.get("switch") or "").lower()
        if switch != "on" or is_light_device(device):
            continue
        matches.append(
            {
                "id": device.get("id") or device.get("deviceId"),
                "label": device.get("label") or device.get("name"),
                "room": room_name(device) or "Unassigned",
                "switch": "on",
            }
        )
    return sorted(
        matches,
        key=lambda item: str(item.get("label") or "").lower(),
    )


def active_lights(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every light device whose current switch state is on."""

    matches = []
    for device in devices:
        attributes = device_attributes(device)
        switch = str(attributes.get("switch") or device.get("switch") or "").lower()
        if switch != "on" or not is_light_device(device):
            continue
        matches.append(
            {
                "id": device.get("id") or device.get("deviceId"),
                "label": device.get("label") or device.get("name"),
                "room": room_name(device) or "Unassigned",
                "switch": "on",
            }
        )
    return sorted(
        matches,
        key=lambda item: str(item.get("label") or "").lower(),
    )


def active_room_summary(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rooms with active motion or at least one light switched on."""

    active: dict[str, set[str]] = {}
    for device in devices:
        room = room_name(device)
        if not room:
            continue
        attributes = device_attributes(device)
        switch = str(attributes.get("switch") or device.get("switch") or "").lower()
        motion = str(attributes.get("motion") or device.get("motion") or "").lower()
        if switch == "on" and is_light_device(device):
            active.setdefault(room, set()).add("light on")
        if motion == "active":
            active.setdefault(room, set()).add("motion")
    return [
        {"name": name, "reasons": sorted(reasons)}
        for name, reasons in sorted(active.items(), key=lambda item: item[0].lower())
    ]


__all__ = [
    "active_lights",
    "active_non_light_switches",
    "active_room_summary",
    "capability_names",
    "device_attributes",
    "is_light_device",
    "room_name",
]
