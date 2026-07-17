from __future__ import annotations

import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import live_attributes
from fast_fallback_release import FastFallbackRouter as ReleaseFastFallbackRouter
from presenter import display_payload, first_value, safe_debug


_DEVICE_STATUS_PATTERNS = (
    re.compile(
        r"^(?:show|display|get)\s+(?:the\s+)?(?:status\s+(?:of|for)\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what(?:'s| is)\s+)?(?:the\s+)?status\s+(?:of|for)\s+(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(r"^(.+?)\s+status[?.!]*$", re.IGNORECASE),
)

_RESERVED_STATUS_TARGETS = {
    "hub cpu",
    "hub memory",
    "hub free memory",
    "hub resources",
    "hub temperature",
    "hub uptime",
    "hub health",
    "hub health status",
    "hub status",
    "hub logs",
    "hub logs and errors",
    "logs",
    "logs and errors",
    "weather",
    "forecast",
    "rooms",
    "rules",
    "devices",
    "all devices",
    "lights",
    "all lights",
    "switches",
    "low batteries",
}

_ATTRIBUTE_ORDER = (
    "switch",
    "power",
    "energy",
    "level",
    "temperature",
    "humidity",
    "battery",
    "motion",
    "contact",
    "presence",
    "thermostatOperatingState",
    "thermostatMode",
    "heatingSetpoint",
    "coolingSetpoint",
    "healthStatus",
    "status",
    "voltage",
    "current",
    "illuminance",
)

_ATTRIBUTE_LABELS = {
    "switch": "Switch",
    "power": "Power",
    "energy": "Energy",
    "level": "Level",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "battery": "Battery",
    "motion": "Motion",
    "contact": "Contact",
    "presence": "Presence",
    "thermostatOperatingState": "Operating state",
    "thermostatMode": "Thermostat mode",
    "heatingSetpoint": "Heating setpoint",
    "coolingSetpoint": "Cooling setpoint",
    "healthStatus": "Health",
    "status": "Status",
    "voltage": "Voltage",
    "current": "Current",
    "illuminance": "Illuminance",
}

_ATTRIBUTE_ICONS = {
    "switch": "⚡",
    "power": "🔌",
    "energy": "📈",
    "level": "🔆",
    "temperature": "🌡️",
    "humidity": "💧",
    "battery": "🔋",
    "motion": "🏃",
    "contact": "🚪",
    "presence": "📍",
    "thermostatOperatingState": "♨️",
    "thermostatMode": "🌡️",
    "heatingSetpoint": "🔥",
    "coolingSetpoint": "❄️",
    "healthStatus": "📡",
    "status": "ℹ️",
    "voltage": "🔋",
    "current": "⚡",
    "illuminance": "☀️",
}

_ATTRIBUTE_UNITS = {
    "power": "W",
    "energy": "kWh",
    "level": "%",
    "temperature": "°C",
    "humidity": "%",
    "battery": "%",
    "heatingSetpoint": "°C",
    "coolingSetpoint": "°C",
    "voltage": "V",
    "current": "A",
    "illuminance": "lx",
}


class FastFallbackRouter(ReleaseFastFallbackRouter):
    """Release router with exact device-status reads and honest fast-path errors."""

    async def answer(self, query: str) -> dict[str, Any]:
        answer = await super().answer(query)
        if answer.get("intent") != "fallback-unsupported":
            return answer

        requested_name = self._device_status_candidate(query)
        if requested_name:
            return await self._device_status(requested_name)

        answer = dict(answer)
        answer["message"] = (
            "The request was routed to the local MCP fast path, but no deterministic "
            "handler matched it. Ollama was not attempted for this fast-path request."
        )
        answer["fast_path_unhandled"] = True
        return answer

    @staticmethod
    def _device_status_candidate(query: str) -> str | None:
        text = str(query or "").strip()
        for pattern in _DEVICE_STATUS_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            candidate = re.sub(r"\s+", " ", match.group(1).strip(" .!?"))
            if not candidate or _normalise(candidate) in _RESERVED_STATUS_TARGETS:
                return None
            return candidate
        return None

    async def _device_status(self, requested_name: str) -> dict[str, Any]:
        result = await self._live_devices()
        candidates = self._device_rows(result.data)
        match, alternatives = self._match_device(requested_name, candidates)

        if not match and hasattr(self, "_humidity_speech_alias_match"):
            match = self._humidity_speech_alias_match(requested_name, candidates)

        if not match:
            if alternatives:
                message = (
                    f'I could not find one exact device named "{requested_name}". '
                    "Closest matches: " + ", ".join(alternatives[:5]) + "."
                )
                intent = "fallback-ambiguous-device-status"
            else:
                message = f'I could not find a selected MCP device named "{requested_name}".'
                intent = "fallback-device-status-not-found"
            response = self._response(message, intent, False, result)
            response["alternatives"] = alternatives[:5]
            response["technical"] = safe_debug(
                {
                    "requested_name": requested_name,
                    "candidate_count": len(candidates),
                }
            )
            return response

        label = _label(match) or f"Device {_device_id(match)}"
        attrs = live_attributes(match)
        metrics: list[dict[str, Any]] = []
        message_parts: list[str] = []

        for key in _ATTRIBUTE_ORDER:
            if key not in attrs:
                continue
            value = self._display_state_value(key, attrs.get(key))
            if value is None:
                continue
            metrics.append(
                {
                    "label": _ATTRIBUTE_LABELS.get(key, key),
                    "value": value,
                    "icon": _ATTRIBUTE_ICONS.get(key, "ℹ️"),
                }
            )
            message_parts.append(f"{_ATTRIBUTE_LABELS.get(key, key)}: {value}")
            if len(metrics) >= 10:
                break

        room = self._room_name(match)
        device_type = str(
            first_value(match, "deviceType", "type", "category", "driverName")
            or "Hubitat device"
        )
        primary = self._primary_state(attrs)
        message = f"{label}: {primary}."
        if message_parts:
            message += "\n" + "\n".join(message_parts)
        else:
            message += " No live currentStates were returned for this device."

        tone = "success" if _normalise(primary) in {
            "on",
            "active",
            "open",
            "present",
            "heating",
            "cooling",
        } else None
        display = display_payload(
            "device-status",
            label,
            subtitle=" · ".join(bit for bit in (room, device_type) if bit),
            metrics=metrics,
            items=[
                {
                    "icon": "📱",
                    "title": label,
                    "value": primary,
                    "subtitle": room or "No room assigned",
                    "tone": tone,
                }
            ],
            note="Live state was read from Hubitat MCP currentStates.",
        )
        response = self._response(
            message,
            "fallback-device-status",
            True,
            result,
        )
        response["display"] = display
        response["device_id"] = _device_id(match)
        response["device_label"] = label
        response["technical"] = safe_debug(
            {
                "requested_name": requested_name,
                "matched_device": match,
                "current_states": attrs,
            }
        )
        return response

    @staticmethod
    def _display_state_value(key: str, raw: Any) -> str | None:
        if isinstance(raw, dict):
            raw = (
                raw.get("value")
                or raw.get("currentValue")
                or raw.get("currentState")
            )
        if raw in (None, ""):
            return None
        text = str(raw).strip()
        if not text:
            return None
        unit = _ATTRIBUTE_UNITS.get(key, "")
        if unit and unit.lower() not in text.lower():
            text = f"{text}{unit}"
        if key in {
            "switch",
            "motion",
            "contact",
            "presence",
            "thermostatOperatingState",
            "thermostatMode",
            "healthStatus",
            "status",
        }:
            return text.replace("_", " ").title()
        return text


__all__ = ["FastFallbackRouter"]
