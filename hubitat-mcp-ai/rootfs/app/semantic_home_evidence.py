from __future__ import annotations

import re
from typing import Any

from device_intelligence_index import _device_rows
from environmental_insight_engine import build_environmental_insights


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _label(device: dict[str, Any]) -> str:
    return str(device.get("label") or device.get("displayName") or device.get("name") or "Unnamed device").strip()


def _room(device: dict[str, Any]) -> str:
    value = device.get("room") or device.get("roomName") or device.get("room_name") or ""
    if isinstance(value, dict):
        value = value.get("name") or value.get("label") or ""
    return str(value or "").strip()


def _states(device: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for container_name in ("currentStates", "current_states", "attributes", "states", "state"):
        container = device.get(container_name)
        if isinstance(container, dict):
            for name, value in container.items():
                values[_key(name)] = value
        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("attribute") or item.get("key")
                if name:
                    values[_key(name)] = item
    return values


def _value(value: Any) -> Any:
    if isinstance(value, dict):
        for name in ("currentValue", "value", "state", "currentState", "displayValue", "text"):
            if value.get(name) not in (None, ""):
                return _value(value[name])
        return None
    return value


def _number(value: Any) -> float | None:
    value = _value(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _state(device: dict[str, Any], *names: str) -> Any:
    states = _states(device)
    for name in names:
        key = _key(name)
        if key in states:
            return _value(states[key])
    return None


def _mode_name(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("currentMode", "mode", "activeMode"):
            current = value.get(key)
            if isinstance(current, dict):
                current = current.get("name") or current.get("label")
            if current not in (None, ""):
                return str(current)
        modes = value.get("modes")
        if isinstance(modes, list):
            for item in modes:
                if isinstance(item, dict) and item.get("active") is True:
                    return str(item.get("name") or item.get("label") or "") or None
    return None


_NON_ROOM_CLIMATE_TERMS = (
    "hub info",
    "hubitat",
    "weather",
    "open-meteo",
    "fridge",
    "freezer",
    "bridge",
    "appliance",
    "life360",
)


def _is_household_climate(label: str, room: str) -> bool:
    haystack = f"{label} {room}".lower()
    return not any(term in haystack for term in _NON_ROOM_CLIMATE_TERMS)


def _is_household_battery(label: str, room: str) -> bool:
    haystack = f"{label} {room}".lower()
    return "life360" not in haystack


def _required_facts(data: dict[str, Any]) -> list[str]:
    required = ["mode", "motion.active_count", "contacts.open_count", "lights.on_count"]
    low = data.get("low_batteries") if isinstance(data.get("low_batteries"), dict) else {}
    if int(low.get("count") or 0):
        required.append("low_batteries.count")
    if list(data.get("heating") or []):
        required.append("heating")
    if list(data.get("attention") or []):
        required.append("attention")
    return required


class SemanticHomeEvidenceBroker:
    """Build compact, typed home evidence for AI synthesis.

    Python performs state extraction, filtering, counting and aggregation so the
    language model only phrases verified household facts.
    """

    def __init__(self, application: Any, snapshot_service: Any) -> None:
        self.application = application
        self.snapshot_service = snapshot_service

    async def collect(self, *, limit: int = 20) -> dict[str, Any]:
        coverage_errors: list[str] = []
        raw_devices, diagnostics, hub_status = await self.snapshot_service._load_sources(
            force=False,
            coverage_errors=coverage_errors,
        )
        devices = _device_rows(raw_devices)
        snapshot = self.snapshot_service._build_snapshot(raw_devices, diagnostics, hub_status)

        mode = None
        mode_tool = {"name": "hub_list_modes", "success": False}
        try:
            result = await self.application.mcp.call_tool("hub_list_modes", {})
            mode_tool["success"] = not bool(getattr(result, "is_error", False))
            if mode_tool["success"]:
                mode = _mode_name(getattr(result, "data", None))
        except Exception as exc:
            coverage_errors.append(f"mode: {str(exc) or type(exc).__name__}")

        motion_active: list[dict[str, Any]] = []
        presence: list[dict[str, Any]] = []
        low_batteries: list[dict[str, Any]] = []
        temperatures: list[dict[str, Any]] = []
        humidities: list[dict[str, Any]] = []

        for device in devices:
            if not isinstance(device, dict) or device.get("disabled") is True:
                continue
            label = _label(device)
            room = _room(device)

            motion = str(_state(device, "motion") or "").strip().lower()
            if motion == "active":
                motion_active.append({"device": label, "room": room or None, "state": "active"})

            present = str(_state(device, "presence") or "").strip().lower()
            if present:
                if present in {"present", "on", "true", "1"}:
                    normalised_presence = "present"
                elif present in {"not present", "notpresent", "away", "off", "false", "0"}:
                    normalised_presence = "not present"
                else:
                    normalised_presence = present
                presence.append({"device": label, "room": room or None, "state": normalised_presence})

            battery = _number(_state(device, "battery", "batteryLevel"))
            if battery is not None and battery <= 20 and _is_household_battery(label, room):
                low_batteries.append({"device": label, "room": room or None, "value": battery, "unit": "%"})

            if _is_household_climate(label, room):
                temperature = _number(_state(device, "temperature"))
                if temperature is not None:
                    temperatures.append({"device": label, "room": room or None, "value": temperature, "unit": "°C"})

                humidity = _number(_state(device, "humidity", "relativeHumidity"))
                if humidity is not None:
                    humidities.append({"device": label, "room": room or None, "value": humidity, "unit": "%"})

        motion_active.sort(key=lambda item: (str(item.get("room") or ""), str(item.get("device") or "")))
        presence.sort(key=lambda item: str(item.get("device") or ""))
        low_batteries.sort(key=lambda item: (float(item.get("value") or 0), str(item.get("device") or "")))
        temperatures.sort(key=lambda item: (-float(item.get("value") or 0), str(item.get("device") or "")))
        humidities.sort(key=lambda item: (-float(item.get("value") or 0), str(item.get("device") or "")))

        environmental_insights = build_environmental_insights(
            {
                "temperatures": temperatures,
                "humidities": humidities,
            }
        )

        data = {
            "mode": mode,
            "environmental_insights": environmental_insights,
            "coverage": {
                "selected_devices": snapshot.get("selected_devices") or len(devices),
                "states_read": snapshot.get("states_read"),
            },
            "motion": {
                "active_count": len(motion_active),
                "active": motion_active[:limit],
            },
            "contacts": {
                "open_count": len(list(snapshot.get("open_contacts") or [])),
                "open": list(snapshot.get("open_contacts") or [])[:limit],
            },
            "lights": {
                "on_count": len(list(snapshot.get("lights_on") or [])),
                "on": list(snapshot.get("lights_on") or [])[:limit],
            },
            "heating": list(snapshot.get("heating") or [])[:limit],
            "attention": list(snapshot.get("attention") or [])[:limit],
            "presence": {
                "count": len(presence),
                "people": presence[:limit],
            },
            "low_batteries": {
                "threshold_percent": 20,
                "count": len(low_batteries),
                "items": low_batteries[:limit],
            },
            "climate": {
                "warmest": temperatures[: min(limit, 8)],
                "most_humid": humidities[: min(limit, 8)],
            },
        }

        return {
            "source": "semantic_home_evidence",
            "success": bool(devices),
            "coverage_errors": coverage_errors,
            "tools_used": [
                {"name": "home_snapshot", "success": bool(devices)},
                mode_tool,
            ],
            "data": data,
            "required_facts": _required_facts(data),
        }


__all__ = ["SemanticHomeEvidenceBroker"]
