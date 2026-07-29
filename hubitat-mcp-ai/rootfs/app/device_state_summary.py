from __future__ import annotations

from typing import Any


def device_attributes(device: dict[str, Any]) -> dict[str, Any]:
    attributes = (
        device.get("attributes")
        or device.get("currentStates")
        or device.get("states")
        or {}
    )
    if isinstance(attributes, list):
        return {
            str(item.get("name")): item.get("currentValue", item.get("value"))
            for item in attributes
            if isinstance(item, dict) and item.get("name")
        }
    return dict(attributes) if isinstance(attributes, dict) else {}


def room_name(device: dict[str, Any]) -> str | None:
    room: Any = device.get("roomName") or device.get("room")
    if isinstance(room, dict):
        room = room.get("name") or room.get("label")
    value = str(room or "").strip()
    return value if value and value.lower() not in {"none", "null", "unassigned"} else None


def active_room_summary(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rooms with active motion or at least one light switched on."""

    active: dict[str, set[str]] = {}
    for device in devices:
        room = room_name(device)
        if not room:
            continue
        attributes = device_attributes(device)
        capabilities = str(device.get("capabilities") or "").lower()
        switch = str(attributes.get("switch") or device.get("switch") or "").lower()
        motion = str(attributes.get("motion") or device.get("motion") or "").lower()
        if switch == "on" and ("light" in capabilities or "bulb" in capabilities):
            active.setdefault(room, set()).add("light on")
        if motion == "active":
            active.setdefault(room, set()).add("motion")
    return [
        {"name": name, "reasons": sorted(reasons)}
        for name, reasons in sorted(active.items(), key=lambda item: item[0].lower())
    ]


__all__ = ["active_room_summary", "device_attributes", "room_name"]
