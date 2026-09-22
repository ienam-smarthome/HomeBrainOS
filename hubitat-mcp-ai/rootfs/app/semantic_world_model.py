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


def _focus_tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 1
    }


def _focus_score(*, focus_text: str, room: str, label: str) -> int:
    """Prioritize semantic details explicitly referenced by the current request.

    The room summaries remain complete regardless of this score. Scoring only
    decides which per-device details survive the bounded context budget.
    """

    focus_normalized = _normalized(focus_text)
    if not focus_normalized:
        return 0

    room_normalized = _normalized(room)
    label_normalized = _normalized(label)
    score = 0
    if label_normalized and label_normalized in focus_normalized:
        score += 1000
    if room_normalized and room_normalized in focus_normalized:
        score += 500

    focus_terms = _focus_tokens(focus_text)
    score += 20 * len(_focus_tokens(label) & focus_terms)
    score += 10 * len(_focus_tokens(room) & focus_terms)
    return score


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
            {"thermostatheatingsetpoint", "heatingsetpoint"}
        )
        or "setheatingsetpoint" in commands
        or "heatingsetpoint" in attributes
    ):
        abilities.add("heating_setpoint")

    if (
        capabilities.intersection(
            {"thermostatcoolingsetpoint", "coolingsetpoint"}
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
    focus_text: str = "",
) -> dict[str, Any]:
    """Build compact canonical identity/capability context for semantic planning.

    Room-level capability summaries are intentionally complete across the whole
    identity snapshot. Only per-device detail is bounded. This prevents a large
    home from making a later-sorting room appear not to exist merely because the
    first N detailed devices exhausted the planner budget.
    """

    all_rows: list[dict[str, Any]] = []
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
        all_rows.append(
            {
                "name": label,
                "room": room,
                "kinds": semantic_device_kinds(device),
                "abilities": abilities,
                "_focus_score": _focus_score(
                    focus_text=focus_text,
                    room=room,
                    label=label,
                ),
            }
        )
        room_devices[room].append(label)
        room_abilities[room].update(abilities)

    all_rows.sort(
        key=lambda item: (
            -int(item.get("_focus_score") or 0),
            str(item["room"]).casefold(),
            str(item["name"]).casefold(),
        )
    )
    rows = all_rows[: max(1, int(max_devices))]
    for row in rows:
        row.pop("_focus_score", None)

    visible_by_room: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        visible_by_room[str(row["room"])].append(str(row["name"]))

    rooms: list[dict[str, Any]] = []
    for room in sorted(room_devices, key=str.casefold):
        all_names = sorted(room_devices[room], key=str.casefold)
        visible_names = sorted(visible_by_room.get(room, []), key=str.casefold)
        rooms.append(
            {
                "name": room,
                "abilities": sorted(room_abilities[room]),
                "device_count": len(all_names),
                "devices": visible_names,
                "details_complete": len(visible_names) == len(all_names),
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
