from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from device_state_summary import (
    capability_names,
    device_attributes,
    is_light_device,
    room_name,
)


_CONTROL_ABILITIES = {
    "switch",
    "brightness",
    "color_temperature",
    "color",
    "heating_setpoint",
    "cooling_setpoint",
    "thermostat_mode",
    "fan_speed",
    "lock",
}
_CONTEXT_ABILITIES = _CONTROL_ABILITIES | {
    "temperature",
    "humidity",
    "battery",
    "motion",
    "presence",
    "contact",
    "power",
    "energy",
}


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _command_names(device: dict[str, Any]) -> set[str]:
    raw = device.get("commands") or []
    names: set[str] = set()
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key:
                names.add(_normalized(key))
            if isinstance(value, dict):
                candidate = value.get("name") or value.get("command")
                if candidate:
                    names.add(_normalized(candidate))
        return {name for name in names if name}
    if isinstance(raw, str):
        return {_normalized(raw)} if raw.strip() else set()
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            if isinstance(item, dict):
                item = item.get("name") or item.get("command")
            if item:
                names.add(_normalized(item))
    return {name for name in names if name}


def device_abilities(device: dict[str, Any]) -> set[str]:
    """Return semantic abilities without exposing Hubitat protocol details.

    The result is identity/capability context only. It never claims a current
    device state and intentionally contains no device IDs or command payloads.
    """

    capabilities = {_normalized(value) for value in capability_names(device)}
    commands = _command_names(device)
    attributes = {_normalized(key) for key in device_attributes(device)}
    abilities: set[str] = set()

    if (
        "switch" in capabilities
        or {"on", "off"}.intersection(commands)
        or "switch" in attributes
    ):
        abilities.add("switch")

    if (
        is_light_device(device)
        and (
            capabilities.intersection({"switchlevel", "changelevel"})
            or "setlevel" in commands
            or "level" in attributes
        )
    ):
        abilities.add("brightness")

    if (
        "colortemperature" in capabilities
        or "setcolortemperature" in commands
        or "colortemperature" in attributes
    ):
        abilities.add("color_temperature")

    if (
        "colorcontrol" in capabilities
        or "setcolor" in commands
        or {"hue", "saturation"}.issubset(attributes)
    ):
        abilities.add("color")

    if (
        capabilities.intersection(
            {"thermostatheatingsetpoint", "heatingsetpoint", "thermostat"}
        )
        or "setheatingsetpoint" in commands
        or "heatingsetpoint" in attributes
    ):
        abilities.add("heating_setpoint")

    if (
        capabilities.intersection(
            {"thermostatcoolingsetpoint", "coolingsetpoint", "thermostat"}
        )
        or "setcoolingsetpoint" in commands
        or "coolingsetpoint" in attributes
    ):
        abilities.add("cooling_setpoint")

    if (
        "thermostatmode" in capabilities
        or "setthermostatmode" in commands
        or "thermostatmode" in attributes
    ):
        abilities.add("thermostat_mode")

    if (
        "fancontrol" in capabilities
        or "setspeed" in commands
        or "speed" in attributes
    ):
        abilities.add("fan_speed")

    if "lock" in capabilities or {"lock", "unlock"}.intersection(commands):
        abilities.add("lock")

    attribute_map = {
        "temperature": "temperature",
        "humidity": "humidity",
        "battery": "battery",
        "motion": "motion",
        "presence": "presence",
        "contact": "contact",
        "power": "power",
        "energy": "energy",
    }
    for attribute, ability in attribute_map.items():
        if attribute in attributes or attribute in capabilities:
            abilities.add(ability)

    return abilities


def semantic_device_kinds(device: dict[str, Any]) -> list[str]:
    abilities = device_abilities(device)
    capabilities = {_normalized(value) for value in capability_names(device)}
    kinds: list[str] = []
    if is_light_device(device):
        kinds.append("light")
    if "heating_setpoint" in abilities or "cooling_setpoint" in abilities:
        kinds.append("thermostat")
    if "fan_speed" in abilities:
        kinds.append("fan")
    if "lock" in abilities:
        kinds.append("lock")
    if "switch" in abilities and "light" not in kinds:
        kinds.append("switch")
    if capabilities.intersection(
        {"motionsensor", "presencesensor", "contactsensor", "temperaturesensor"}
    ):
        kinds.append("sensor")
    return kinds or ["device"]


def build_semantic_world(
    devices: list[dict[str, Any]],
    *,
    max_devices: int = 64,
) -> dict[str, Any]:
    """Build compact canonical identity/capability context for semantic planning."""

    rows: list[dict[str, Any]] = []
    room_abilities: dict[str, set[str]] = defaultdict(set)
    room_devices: dict[str, list[str]] = defaultdict(list)

    for device in devices:
        if not isinstance(device, dict):
            continue
        label = str(
            device.get("label")
            or device.get("name")
            or device.get("displayName")
            or ""
        ).strip()
        if not label:
            continue
        abilities = sorted(device_abilities(device) & _CONTEXT_ABILITIES)
        if not abilities:
            continue
        room = room_name(device) or "Unassigned"
        rows.append(
            {
                "name": label,
                "room": room,
                "kinds": semantic_device_kinds(device),
                "abilities": abilities,
            }
        )
        room_devices[room].append(label)
        room_abilities[room].update(abilities)

    rows.sort(key=lambda item: (str(item["room"]).casefold(), str(item["name"]).casefold()))
    rows = rows[: max(1, int(max_devices))]
    visible_names = {str(item["name"]) for item in rows}

    rooms: list[dict[str, Any]] = []
    for room in sorted(room_devices, key=str.casefold):
        names = [name for name in room_devices[room] if name in visible_names]
        if not names:
            continue
        rooms.append(
            {
                "name": room,
                "abilities": sorted(room_abilities[room]),
                "devices": sorted(names, key=str.casefold),
            }
        )

    return {
        "source": "cached-device-identity",
        "live_state": False,
        "rooms": rooms,
        "devices": rows,
    }


def render_semantic_world(
    world: dict[str, Any] | None,
    *,
    max_chars: int = 7000,
) -> str:
    """Render bounded planner context; never includes current state or IDs."""

    if not isinstance(world, dict):
        return ""
    payload = {
        "live_state": False,
        "rooms": world.get("rooms") or [],
        "devices": world.get("devices") or [],
    }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= max_chars:
        return text

    devices = list(payload["devices"])
    while devices and len(text) > max_chars:
        devices.pop()
        payload["devices"] = devices
        visible = {str(item.get("name") or "") for item in devices}
        trimmed_rooms = []
        for room in world.get("rooms") or []:
            room_devices = [
                name for name in room.get("devices") or [] if str(name) in visible
            ]
            if room_devices:
                trimmed_rooms.append({**room, "devices": room_devices})
        payload["rooms"] = trimmed_rooms
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text[:max_chars]


__all__ = [
    "build_semantic_world",
    "device_abilities",
    "render_semantic_world",
    "semantic_device_kinds",
]
