from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import _looks_like_light, live_attributes
from fast_fallback_prayer_times import FastFallbackRouter as PrayerTimesRouter
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload, first_value, normalise_text, safe_debug


@dataclass(frozen=True)
class DeviceTypeSpec:
    key: str
    title: str
    icon: str
    aliases: tuple[str, ...]
    state_keys: tuple[str, ...]
    metadata_terms: tuple[str, ...] = ()
    predicate: Callable[[dict[str, Any], dict[str, Any], str], bool] | None = None


_SENSOR_STATE_KEYS = {
    "motion",
    "contact",
    "temperature",
    "humidity",
    "presence",
    "illuminance",
    "battery",
    "water",
    "moisture",
    "smoke",
    "carbonMonoxide",
    "acceleration",
    "soundPressureLevel",
}


def _light_predicate(item: dict[str, Any], _attrs: dict[str, Any], _metadata: str) -> bool:
    return _looks_like_light(item)


def _switch_predicate(item: dict[str, Any], attrs: dict[str, Any], _metadata: str) -> bool:
    return "switch" in attrs and not _looks_like_light(item)


def _outlet_predicate(_item: dict[str, Any], attrs: dict[str, Any], metadata: str) -> bool:
    return "switch" in attrs and any(term in metadata for term in ("socket", "outlet", "smart plug", " plug "))


def _sensor_predicate(_item: dict[str, Any], attrs: dict[str, Any], metadata: str) -> bool:
    return bool(_SENSOR_STATE_KEYS.intersection(attrs)) or "sensor" in metadata


def _thermostat_predicate(_item: dict[str, Any], attrs: dict[str, Any], metadata: str) -> bool:
    return bool(
        {"thermostatMode", "thermostatOperatingState", "heatingSetpoint", "coolingSetpoint"}.intersection(attrs)
    ) or any(term in metadata for term in ("thermostat", " trv", "radiator valve"))


def _camera_predicate(_item: dict[str, Any], _attrs: dict[str, Any], metadata: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", metadata))
    return "camera" in words or "cam" in words or any(word.endswith("cam") for word in words)


def _fan_predicate(_item: dict[str, Any], attrs: dict[str, Any], metadata: str) -> bool:
    return "speed" in attrs or "fanSpeed" in attrs or "fan" in set(re.findall(r"[a-z0-9]+", metadata))


def _button_predicate(_item: dict[str, Any], attrs: dict[str, Any], metadata: str) -> bool:
    return bool({"pushed", "held", "doubleTapped", "released", "numberOfButtons"}.intersection(attrs)) or "button" in metadata


_DEVICE_TYPES: tuple[DeviceTypeSpec, ...] = (
    DeviceTypeSpec("motion", "Motion sensors", "🏃", ("motion sensor", "motion sensors", "motion detector", "motion detectors"), ("motion",), ("motion sensor",)),
    DeviceTypeSpec("contact", "Contact sensors", "🚪", ("contact sensor", "contact sensors", "door sensor", "door sensors", "window sensor", "window sensors", "open close sensor", "open close sensors"), ("contact",), ("contact sensor", "door sensor", "window sensor")),
    DeviceTypeSpec("temperature", "Temperature sensors", "🌡️", ("temperature sensor", "temperature sensors", "temperature device", "temperature devices"), ("temperature",), ("temperature measurement",)),
    DeviceTypeSpec("humidity", "Humidity sensors", "💧", ("humidity sensor", "humidity sensors", "humidity device", "humidity devices"), ("humidity",), ("humidity measurement",)),
    DeviceTypeSpec("presence", "Presence sensors", "📍", ("presence sensor", "presence sensors", "occupancy sensor", "occupancy sensors"), ("presence",), ("presence sensor", "occupancy sensor")),
    DeviceTypeSpec("illuminance", "Illuminance sensors", "☀️", ("illuminance sensor", "illuminance sensors", "light sensor", "light sensors", "lux sensor", "lux sensors"), ("illuminance",), ("illuminance measurement", "light sensor")),
    DeviceTypeSpec("battery", "Battery devices", "🔋", ("battery device", "battery devices", "battery sensor", "battery sensors"), ("battery",), ("battery",)),
    DeviceTypeSpec("thermostat", "Thermostats and TRVs", "🌡️", ("thermostat", "thermostats", "trv", "trvs", "radiator valve", "radiator valves"), ("thermostatOperatingState", "thermostatMode", "heatingSetpoint", "coolingSetpoint"), predicate=_thermostat_predicate),
    DeviceTypeSpec("lock", "Locks", "🔒", ("lock", "locks", "door lock", "door locks", "smart lock", "smart locks"), ("lock",), ("lock",)),
    DeviceTypeSpec("smoke", "Smoke detectors", "🚨", ("smoke detector", "smoke detectors", "smoke alarm", "smoke alarms"), ("smoke",), ("smoke detector", "smoke alarm")),
    DeviceTypeSpec("carbon-monoxide", "Carbon-monoxide detectors", "☠️", ("carbon monoxide detector", "carbon monoxide detectors", "carbon monoxide sensor", "carbon monoxide sensors", "co detector", "co detectors"), ("carbonMonoxide",), ("carbon monoxide", "co detector")),
    DeviceTypeSpec("water", "Water and leak sensors", "💦", ("water sensor", "water sensors", "leak sensor", "leak sensors", "water leak sensor", "water leak sensors"), ("water",), ("water sensor", "leak sensor")),
    DeviceTypeSpec("moisture", "Moisture sensors", "🌱", ("moisture sensor", "moisture sensors", "soil sensor", "soil sensors"), ("moisture",), ("moisture sensor", "soil sensor")),
    DeviceTypeSpec("power", "Power meters", "🔌", ("power meter", "power meters", "power monitor", "power monitors", "power device", "power devices"), ("power",), ("power meter",)),
    DeviceTypeSpec("energy", "Energy meters", "📈", ("energy meter", "energy meters", "energy monitor", "energy monitors", "energy device", "energy devices"), ("energy",), ("energy meter",)),
    DeviceTypeSpec("light", "Lights", "💡", ("light", "lights", "lamp", "lamps", "bulb", "bulbs", "dimmer", "dimmers"), ("switch", "level"), predicate=_light_predicate),
    DeviceTypeSpec("switch", "Switches", "⚡", ("switch", "switches"), ("switch",), predicate=_switch_predicate),
    DeviceTypeSpec("outlet", "Sockets and outlets", "🔌", ("socket", "sockets", "outlet", "outlets", "smart plug", "smart plugs", "plug", "plugs"), ("switch", "power", "energy"), predicate=_outlet_predicate),
    DeviceTypeSpec("camera", "Cameras", "📷", ("camera", "cameras", "cam", "cams"), ("status", "healthStatus", "switch"), predicate=_camera_predicate),
    DeviceTypeSpec("fan", "Fans", "🌀", ("fan", "fans", "ventilation fan", "ventilation fans"), ("speed", "fanSpeed", "switch"), predicate=_fan_predicate),
    DeviceTypeSpec("valve", "Valves", "🚰", ("valve", "valves"), ("valve", "switch"), ("valve",)),
    DeviceTypeSpec("button", "Buttons", "🔘", ("button", "buttons", "scene button", "scene buttons"), ("pushed", "held", "doubleTapped", "numberOfButtons"), predicate=_button_predicate),
    DeviceTypeSpec("alarm", "Sirens and alarms", "🚨", ("siren", "sirens", "alarm", "alarms"), ("alarm",), ("siren", "alarm")),
    DeviceTypeSpec("acceleration", "Acceleration sensors", "📳", ("acceleration sensor", "acceleration sensors", "vibration sensor", "vibration sensors"), ("acceleration",), ("acceleration sensor", "vibration sensor")),
    DeviceTypeSpec("sensor", "Sensors", "📡", ("sensor", "sensors", "all sensors"), tuple(_SENSOR_STATE_KEYS), predicate=_sensor_predicate),
)

_ALIAS_TO_SPEC = {
    _normalise(alias): spec
    for spec in _DEVICE_TYPES
    for alias in spec.aliases
}

_TYPE_QUERY_PATTERNS = (
    re.compile(
        r"^(?:show|list|find|get|display)\s+(?:me\s+)?(?:(?:all|every|the)\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what|which)\s+(.+?)\s+(?:devices?\s+)?(?:do\s+i\s+have|are\s+(?:there|available|selected|configured))[?.!]*$",
        re.IGNORECASE,
    ),
)

_STATE_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "battery": "%",
    "illuminance": " lx",
    "power": " W",
    "energy": " kWh",
    "moisture": "%",
    "heatingSetpoint": "°C",
    "coolingSetpoint": "°C",
}

_WARNING_STATES = {"open", "wet", "detected", "smoke", "carbon monoxide", "unlocked", "not present", "offline", "unavailable"}
_SUCCESS_STATES = {"active", "on", "present", "locked", "clear", "dry", "inactive", "closed", "online", "available"}


class FastFallbackRouter(PrayerTimesRouter):
    """Authoritative inventories for questions about a class of Hubitat devices."""

    async def answer(self, query: str) -> dict[str, Any]:
        spec = self._device_type_candidate(query)
        if spec is not None:
            return await self._device_type_inventory(spec)
        return await super().answer(query)

    @staticmethod
    def _device_type_candidate(query: str) -> DeviceTypeSpec | None:
        text = str(query or "").strip()
        for pattern in _TYPE_QUERY_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            candidate = _normalise(match.group(1)).strip(" .!?")
            candidate = re.sub(r"^(?:all|every|the)\s+", "", candidate)
            candidate = re.sub(r"\s+(?:devices?|units?)$", "", candidate)
            return _ALIAS_TO_SPEC.get(candidate)
        return None

    async def _device_type_inventory(self, spec: DeviceTypeSpec) -> dict[str, Any]:
        result = await self._all_devices_with_type_metadata()
        rows = [
            item
            for item in self._device_rows(result.data)
            if self._matches_type(spec, item)
        ]
        rows = self._dedupe_rows(rows)
        rows.sort(key=lambda item: (_normalise(self._room_name(item)), _normalise(_label(item))))

        items: list[dict[str, Any]] = []
        lines: list[str] = []
        state_count = 0
        attention_count = 0
        for item in rows[:60]:
            label = _label(item) or f"Device {_device_id(item)}"
            attrs = live_attributes(item)
            state = self._state_for_type(spec, attrs)
            if state != "Available":
                state_count += 1
            tone = self._tone_for_state(state)
            if tone == "warning":
                attention_count += 1
            room = self._room_name(item) or "No room assigned"
            device_type = normalise_text(
                first_value(item, "deviceType", "type", "driverName", "category")
                or "Hubitat device"
            )
            subtitle = " · ".join(bit for bit in (room, device_type) if bit)
            items.append(
                {
                    "icon": spec.icon,
                    "title": label,
                    "value": state,
                    "subtitle": subtitle,
                    "tone": tone,
                }
            )
            lines.append(f"- {label}: {state} ({room})")

        if rows:
            message = f"{len(rows)} {spec.title.lower()} found:\n" + "\n".join(lines)
        else:
            message = (
                f"No {spec.title.lower()} were found in the selected MCP devices. "
                "Check that the relevant devices are selected in MCP Rule Server."
            )

        metrics = [
            {"label": "Devices", "value": str(len(rows)), "icon": spec.icon},
            {"label": "Live states", "value": str(state_count), "icon": "📡"},
        ]
        if attention_count:
            metrics.append({"label": "Need attention", "value": str(attention_count), "icon": "⚠️"})

        display = display_payload(
            "device-type-inventory",
            spec.title,
            subtitle=f"{len(rows)} selected Hubitat device{'' if len(rows) == 1 else 's'}",
            metrics=metrics,
            items=items,
            note=(
                "Device type is determined from live currentStates, capabilities and Hubitat metadata. "
                "Devices not selected in MCP Rule Server cannot appear."
            ),
        )
        response = self._response(
            message,
            f"fallback-device-type-{spec.key}",
            True,
            result,
        )
        response["display"] = display
        response["device_type"] = spec.key
        response["device_count"] = len(rows)
        response["technical"] = safe_debug(
            {
                "device_type": spec.key,
                "matched_devices": rows,
                "state_count": state_count,
                "attention_count": attention_count,
            }
        )
        return response

    async def _all_devices_with_type_metadata(self) -> MCPToolResult:
        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": [
                    "id",
                    "name",
                    "label",
                    "room",
                    "currentStates",
                    "capabilities",
                    "deviceType",
                    "type",
                    "category",
                    "driverName",
                    "disabled",
                    "lastActivity",
                ],
            },
        )
        if result.is_error:
            raise MCPError(result.text or "Device-type inventory lookup failed")
        return result

    @staticmethod
    def _metadata(item: dict[str, Any]) -> str:
        parts: list[str] = []
        for key in (
            "label",
            "name",
            "displayName",
            "deviceType",
            "type",
            "category",
            "driverName",
            "capabilities",
        ):
            value = item.get(key)
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        parts.extend(str(bit) for bit in entry.values())
                    else:
                        parts.append(str(entry))
            elif isinstance(value, dict):
                parts.extend(str(bit) for bit in value.values())
            elif value not in (None, ""):
                parts.append(str(value))
        return " " + _normalise(" ".join(parts)) + " "

    def _matches_type(self, spec: DeviceTypeSpec, item: dict[str, Any]) -> bool:
        attrs = live_attributes(item)
        metadata = self._metadata(item)
        if spec.predicate and spec.predicate(item, attrs, metadata):
            return True
        if any(key in attrs for key in spec.state_keys):
            return True
        return any(term in metadata for term in spec.metadata_terms)

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        for item in rows:
            key = str(_device_id(item) or _label(item) or id(item))
            found.setdefault(key, item)
        return list(found.values())

    def _state_for_type(self, spec: DeviceTypeSpec, attrs: dict[str, Any]) -> str:
        for key in spec.state_keys:
            if key not in attrs:
                continue
            shown = self._format_state(key, attrs.get(key))
            if shown:
                if spec.key == "thermostat" and key in {"heatingSetpoint", "coolingSetpoint"}:
                    return f"Setpoint {shown}"
                return shown
        for key in (
            "switch",
            "status",
            "healthStatus",
            "presence",
            "motion",
            "contact",
            "battery",
            "temperature",
        ):
            if key in attrs:
                shown = self._format_state(key, attrs.get(key))
                if shown:
                    return shown
        return "Available"

    @staticmethod
    def _format_state(key: str, raw: Any) -> str | None:
        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("currentValue") or raw.get("currentState")
        if raw in (None, ""):
            return None
        text = normalise_text(raw).strip()
        if not text:
            return None
        unit = _STATE_UNITS.get(key, "")
        if unit and unit.strip().lower() not in text.lower():
            text = f"{text}{unit}"
        if key in {
            "switch",
            "motion",
            "contact",
            "presence",
            "lock",
            "smoke",
            "carbonMonoxide",
            "water",
            "acceleration",
            "alarm",
            "valve",
            "status",
            "healthStatus",
            "thermostatMode",
            "thermostatOperatingState",
        }:
            return text.replace("_", " ").title()
        return text

    @staticmethod
    def _tone_for_state(state: str) -> str | None:
        normalised = _normalise(state)
        if normalised in _WARNING_STATES or any(term in normalised for term in ("offline", "unavailable", "low battery")):
            return "warning"
        if normalised in _SUCCESS_STATES:
            return "success"
        return None


__all__ = ["DeviceTypeSpec", "FastFallbackRouter"]
