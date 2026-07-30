from __future__ import annotations

from typing import Any


def device_attributes(device: dict[str, Any]) -> dict[str, Any]:
    """Merge every Hubitat state container into one canonical attribute map."""

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
    return attributes


def room_name(device: dict[str, Any]) -> str | None:
    room: Any = device.get("roomName") or device.get("room")
    if isinstance(room, dict):
        room = room.get("name") or room.get("label")
    value = str(room or "").strip()
    return value if value and value.lower() not in {"none", "null", "unassigned"} else None


def is_light_device(device: dict[str, Any]) -> bool:
    capabilities = str(device.get("capabilities") or "").lower()
    return "light" in capabilities or "bulb" in capabilities


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
    "device_attributes",
    "is_light_device",
    "room_name",
]
