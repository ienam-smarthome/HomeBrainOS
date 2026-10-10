"""Deterministic read-only room-status presentation from detailed Hubitat devices.

This does not infer health from a stale activity timestamp. It never promotes
motion/presence/illuminance from an explicitly offline sensor into a current
room observation. Raw states remain available solely as qualified diagnostics.
"""
from __future__ import annotations

import re
from typing import Any

from device_state_summary import device_attributes, is_light_device, room_name


_ROOM_REQUEST = re.compile(
    r"^\s*(?:check|show|report)\s+(?:the\s+)?"
    r"(?P<room>[a-z\d][a-z\d\s_-]{1,80}?)\s+"
    r"(?:status\s+and\s+states|states)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_HEALTH_NAMES = frozenset({
    "sensorstatus", "healthstatus", "mqttstatus", "lastmessage", "lasterror",
})
_UNAVAILABLE = frozenset({
    "offline", "unavailable", "disconnected", "failed", "failure",
    "not responding", "not connected",
})
_UNTRUSTED_READINGS = ("motion", "presence", "illuminance", "temperature", "humidity")


def parse_room_status_request(prompt: str) -> str | None:
    """Match only clear room status requests, not arbitrary room questions."""

    match = _ROOM_REQUEST.fullmatch(str(prompt or ""))
    return match.group("room").strip() if match else None


def _normal(text: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").casefold())


def resolve_room(requested: str, identities: list[dict[str, Any]]) -> str | None:
    """Resolve 'livingroom' against the authoritative 'Living Room' room name."""

    matches = {
        room_name(device)
        for device in identities
        if room_name(device) and _normal(room_name(device)) == _normal(requested)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _attrs(device: dict[str, Any]) -> dict[str, Any]:
    return {
        _normal(key): value
        for key, value in device_attributes(device).items()
        if value is not None
    }


def _state(attributes: dict[str, Any], key: str) -> str | None:
    value = attributes.get(_normal(key))
    return str(value).strip() if value is not None and str(value).strip() else None


def _device_health(attributes: dict[str, Any]) -> tuple[str | None, list[str]]:
    """Use explicit driver observations, not assumed freshness or capabilities."""

    state = {
        name: _state(attributes, name)
        for name in ("sensorstatus", "healthstatus", "mqttstatus", "hapstatus", "lastmessage", "lasterror")
    }
    offline = any(
        str(state.get(name) or "").casefold() in _UNAVAILABLE
        for name in ("sensorstatus", "healthstatus", "lastmessage")
    )
    mqtt = str(state.get("mqttstatus") or "").casefold()
    hap = str(state.get("hapstatus") or "").casefold()
    last_error = str(state.get("lasterror") or "")
    connection_problem = bool(
        mqtt in {"connecting", "disconnected", "offline", "failed", "error"}
        or any(token in hap for token in ("connecting", "disconnected", "offline", "failed", "error"))
        or any(token in last_error.casefold() for token in (
            "connect fail", "connection fail", "mqttexception", "mqtt fail"
        ))
    )
    status = "Offline" if offline else "Connection warning" if connection_problem else None
    reasons = [
        f"{label}: {state[key]}"
        for key, label in (
            ("sensorstatus", "sensorStatus"),
            ("healthstatus", "healthStatus"),
            ("mqttstatus", "mqttStatus"),
            ("hapstatus", "hapStatus"),
            ("lastmessage", "lastMessage"),
            ("lasterror", "lastError"),
        )
        if state.get(key)
    ]
    return status, reasons


def linked_parent_ids(devices: list[dict[str, Any]]) -> list[str]:
    """Return deduplicated authoritative parent IDs absent from a room read.

    The MCP server exposes parentDeviceId on authorized detailed device rows.
    Never infer relationships from labels, capabilities, room names, or the
    numeric IDs of unrelated devices.
    """

    present = {
        str(item.get("id") or item.get("deviceId"))
        for item in devices if isinstance(item, dict)
        and (item.get("id") or item.get("deviceId")) is not None
    }
    parents = set()
    for device in devices:
        if not isinstance(device, dict):
            continue
        parent = str(device.get("parentDeviceId") or "").strip()
        if parent.isdecimal() and parent not in present:
            parents.add(parent)
    return sorted(parents, key=lambda value: int(value))


def _parent_reliability(parent: dict[str, Any] | None) -> tuple[str, list[str]]:
    """Classify parent connectivity as known-offline, verified, or unknown.

    No state container or missing health fields means *unknown*, not online.
    A parent connection warning always overrides an optimistic 'online' field.
    """

    if parent is None:
        return "unverified", ["Parent device not accessible in the MCP read."]
    states = _attrs(parent)
    health, reasons = _device_health(states)
    if health is not None:
        return ("offline" if health == "Offline" else "unverified"), reasons
    health_state = str(_state(states, "healthStatus") or "").casefold()
    hap = str(_state(states, "hapStatus") or "").casefold()
    if health_state in {"online", "healthy", "connected"} and not (
        hap and any(word in hap for word in ("connecting", "disconnected", "offline", "failed"))
    ):
        return "verified", ["healthStatus: " + str(_state(states, "healthStatus"))]
    if hap in {"connected", "connected (live)", "online", "live"}:
        return "verified", ["hapStatus: " + str(_state(states, "hapStatus"))]
    return "unverified", ["Parent record has no affirmative usable connection-health state."]


def format_room_status(
    room: str,
    devices: list[dict[str, Any]],
    *,
    has_more: bool = False,
    read_incomplete: bool = False,
    parent_records: dict[str, dict[str, Any] | None] | None = None,
    parent_read_failures: set[str] | None = None,
    parents_not_checked: set[str] | None = None,
) -> str:
    """Format one successful detailed, room-scoped inventory read.

    Missing explicit health fields mean unknown health, not confirmed online.
    If a sensor is explicitly offline, retained readings appear only in Health.
    """

    grouped: dict[str, list[str]] = {
        "Occupancy & motion": [],
        "Lights": [],
        "Other switches": [],
        "Environment": [],
        "Device health": [],
    }
    seen_ids: set[str] = set()
    included = 0
    parent_records = parent_records or {}
    parent_read_failures = parent_read_failures or set()
    parents_not_checked = parents_not_checked or set()
    room_parent_rows = {
        str(row.get("id") or row.get("deviceId")): row
        for row in devices
        if isinstance(row, dict) and (row.get("id") or row.get("deviceId"))
    }
    parent_status: dict[str, tuple[str, list[str], str]] = {}
    referenced = {
        str(item.get("parentDeviceId"))
        for item in devices
        if isinstance(item, dict)
        and str(item.get("parentDeviceId") or "").isdecimal()
    }
    for parent_id in sorted(referenced):
        parent = room_parent_rows.get(parent_id, parent_records.get(parent_id))
        status, reasons = _parent_reliability(parent)
        name = str((parent or {}).get("label") or (parent or {}).get("name") or
                   f"Device {parent_id}")
        if parent_id in parents_not_checked:
            status, reasons = "unverified", ["Parent health lookup was limited."]
        elif parent_id in parent_read_failures:
            status, reasons = "unverified", [
                "Parent is not readable via MCP. Check device selection in MCP Rule Server."
            ]
        parent_status[parent_id] = (status, reasons, name)
        if parent_id not in room_parent_rows and status != "verified":
            state_label = "Offline" if status == "offline" else "Connection unverified"
            grouped["Device health"].append(
                f"- **Linked parent {name} (ID {parent_id}): {state_label}.** " +
                "; ".join(reasons)
            )
    for device in devices:
        if not isinstance(device, dict):
            continue
        actual_room = room_name(device)
        if actual_room and _normal(actual_room) != _normal(room):
            continue
        device_id = str(device.get("id") or device.get("deviceId") or "")
        if device_id and device_id in seen_ids:
            continue
        if device_id:
            seen_ids.add(device_id)
        included += 1
        label = str(device.get("label") or device.get("name") or device_id or "Unlabelled device")
        attributes = _attrs(device)
        health, diagnostics = _device_health(attributes)
        parent_id = str(device.get("parentDeviceId") or "")
        parent_info = parent_status.get(parent_id)
        parent_problem = parent_info is not None and parent_info[0] != "verified"
        if parent_problem and health is None:
            parent_state, parent_reasons, parent_name = parent_info
            reason = "offline" if parent_state == "offline" else "not verified"
            diagnostics = [
                f"Linked parent {parent_name} (ID {parent_id}) is {reason}",
                *parent_reasons,
            ]
            health = "Parent connection offline" if parent_state == "offline" else "Parent health unverified"
        if health is not None:
            # Switch/on is reported power or software state, NOT proof the
            # offline sensor has functioning presence/illuminance telemetry.
            state_switch = _state(attributes, "switch")
            retained = [
                f"{key}={_state(attributes, key)}"
                for key in _UNTRUSTED_READINGS
                if _state(attributes, key) is not None
            ]
            details = "; ".join(diagnostics)
            if state_switch is not None:
                details = (details + "; " if details else "") + f"switch={state_switch}"
            if retained:
                details += f". Last reported, freshness unverified: {', '.join(retained)}"
            if parent_problem and not retained:
                details += ". State freshness cannot be verified while parent connectivity is uncertain."
            grouped["Device health"].append(
                f"- **{label}: {health}.** {details}"
            )
            continue

        for key in ("motion", "presence"):
            value = _state(attributes, key)
            if value is not None:
                grouped["Occupancy & motion"].append(f"- **{label}** — {key}: {value}")

        switch = _state(attributes, "switch")
        if switch is not None:
            if is_light_device(device):
                level = _state(attributes, "level")
                level_note = (
                    f" (level {level}%, last stored if off)"
                    if level is not None and switch.casefold() == "off"
                    else f" (level {level}%)" if level is not None else ""
                )
                grouped["Lights"].append(f"- **{label}** — {switch}{level_note}")
            else:
                grouped["Other switches"].append(f"- **{label}** — {switch}")

        readings = []
        for key, unit in (
            ("temperature", "°C"), ("humidity", "%"), ("illuminance", " lux"), ("battery", "%")
        ):
            value = _state(attributes, key)
            if value is not None:
                readings.append(f"{key}: {value}{unit}")
        if readings:
            grouped["Environment"].append(f"- **{label}** — " + "; ".join(readings))

    if not included:
        return f"No verified device records were returned for **{room}**."
    sections = [f"## {room} — device states", f"Detailed room read: **{included} device records**."]
    if has_more or read_incomplete:
        sections.append(
            "**Coverage warning:** the returned room inventory may be incomplete; "
            "do not treat missing devices or readings as absent."
        )
    for heading, entries in grouped.items():
        if entries:
            sections.append("### " + heading + "\n" + "\n".join(entries))
    if not grouped["Device health"]:
        sections.append(
            "No explicit offline/connection failure was present in the returned "
            "device states. This does **not** verify that every device is online."
        )
    return "\n\n".join(sections)


__all__ = ["parse_room_status_request", "resolve_room", "linked_parent_ids", "format_room_status"]
