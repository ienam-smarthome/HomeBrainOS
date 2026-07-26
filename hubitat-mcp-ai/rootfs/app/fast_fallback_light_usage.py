from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Callable, Iterable

from device_intelligence_index import (
    DeviceIntelligenceIndex,
    _DETAILED_FIELDS as _INDEX_DETAILED_FIELDS,
    _SUMMARY_FIELDS as _INDEX_SUMMARY_FIELDS,
    _label as _index_label,
)
from device_presentation import device_icon
from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_health import normalise_spoken_device_name
from fast_fallback_extended_reads import FastFallbackRouter as ExtendedReadsRouter, _rows
from fast_fallback_live import _looks_like_light, live_attributes
from light_usage_calculation import calculate_on_time, duration_text, switch_events
from mcp_client import MCPError, MCPToolResult
from presenter import (
    display_payload,
    first_value,
    normalise_text,
    present_rooms,
    safe_debug,
)

# Prayer Times

_PRAYERS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Fajr", ("fajr", "fajar"), "🌙"),
    ("Sunrise", ("sunrise", "shuruq", "ishraq"), "🌅"),
    ("Dhuhr", ("dhuhr", "dhur", "zuhr", "zohar"), "☀️"),
    ("Asr", ("asr",), "☁️"),
    ("Maghrib", ("maghrib", "magrib"), "🌆"),
    ("Isha", ("isha", "ishaa"), "🌌"),
)

_ALIAS_TO_NAME = {
    alias: name
    for name, aliases, _icon in _PRAYERS
    for alias in aliases
}

_ICON_BY_NAME = {name: icon for name, _aliases, icon in _PRAYERS}

_ORDER = [name for name, _aliases, _icon in _PRAYERS]

_SINGLE_PRAYER_RE = re.compile(
    r"^(?:what\s+time\s+(?:is|does)|when\s+(?:is|does)|tell\s+me\s+(?:the\s+)?)\s*"
    r"(fajr|fajar|sunrise|shuruq|ishraq|dhuhr|dhur|zuhr|zohar|asr|maghrib|magrib|isha|ishaa)"
    r"(?:\s+(?:start|begin|starts|begins))?(?:\s+(?:today|tonight))?[?.!]*$",
    re.IGNORECASE,
)

_SINGLE_PRAYER_TIME_RE = re.compile(
    r"^(fajr|fajar|sunrise|shuruq|ishraq|dhuhr|dhur|zuhr|zohar|asr|maghrib|magrib|isha|ishaa)"
    r"(?:\s+(?:prayer))?\s+time(?:\s+(?:today|tonight))?[?.!]*$",
    re.IGNORECASE,
)

_ALL_PRAYER_RE = re.compile(
    r"^(?:show|list|display|give\s+me|what\s+are|what(?:'s|\s+is))\s+"
    r"(?:today(?:'s)?\s+)?(?:pray|prayer)\s+times(?:\s+today)?[?.!]*$",
    re.IGNORECASE,
)

_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")

def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)

def _canonical_prayer(value: str) -> str | None:
    return _ALIAS_TO_NAME.get(_normalise(value))

def _time_text(value: Any) -> str | None:
    match = _TIME_RE.search(normalise_text(value))
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"

def extract_prayer_times(value: Any) -> dict[str, str]:
    """Extract the standard daily prayer times from attributes, HTML or events."""
    found: dict[str, str] = {}

    for item in _walk(value):
        if not isinstance(item, dict):
            continue
        for key, raw in item.items():
            canonical = _canonical_prayer(str(key))
            if canonical and canonical not in found:
                parsed = _time_text(raw)
                if parsed:
                    found[canonical] = parsed

    chunks: list[str] = []
    for item in _walk(value):
        if isinstance(item, str) and item.strip():
            chunks.append(normalise_text(item))
    text = " ".join(chunks)

    for name, aliases, _icon in _PRAYERS:
        if name in found:
            continue
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        match = re.search(
            rf"\b(?:{alias_pattern})\b[^0-9]{{0,30}}([01]?\d|2[0-3]):([0-5]\d)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            found[name] = f"{int(match.group(1)):02d}:{match.group(2)}"

    return {name: found[name] for name in _ORDER if name in found}

class PrayerTimesRouter(ExtendedReadsRouter):
    """Fast prayer-time answers sourced from the selected Pray times device."""

    async def answer(self, query: str) -> dict[str, Any]:
        if "event" not in _normalise(query):
            requested = self._requested_prayer(query)
            if requested is not False:
                return await self._prayer_times(requested)
        return await super().answer(query)

    @staticmethod
    def _requested_prayer(query: str) -> str | None | bool:
        text = str(query or "").strip()
        match = _SINGLE_PRAYER_RE.match(text) or _SINGLE_PRAYER_TIME_RE.match(text)
        if match:
            return _canonical_prayer(match.group(1))
        if _ALL_PRAYER_RE.match(text):
            return None
        return False

    async def _find_prayer_device(
        self,
    ) -> tuple[MCPToolResult, dict[str, Any] | None, list[str]]:
        live = await self._live_devices()
        candidates = self._device_rows(live.data)
        match, alternatives = self._match_device("Pray times", candidates)
        return live, match, alternatives

    async def _prayer_times(self, requested: str | None) -> dict[str, Any]:
        live, match, alternatives = await self._find_prayer_device()
        if not match:
            message = "I could not find one selected MCP device named Pray times."
            if alternatives:
                message += " Closest matches: " + ", ".join(alternatives[:5]) + "."
            response = self._response(message, "fallback-prayer-times-device-not-found", False, live)
            response["alternatives"] = alternatives[:5]
            return response

        attributes = live_attributes(match)
        times = extract_prayer_times(attributes)
        source_result: MCPToolResult = live
        source = "currentStates"
        updated = first_value(match, "lastActivity", "lastUpdated", "date", "timestamp")

        if requested not in times if requested else len(times) < 4:
            events = await self._read_tool(
                "hub_list_device_events",
                {"deviceId": _device_id(match), "hoursBack": 48},
            )
            event_rows = _rows(events.data, ("events", "items"))
            event_times = extract_prayer_times(event_rows)
            if len(event_times) > len(times) or (requested and requested in event_times):
                times = event_times
                source_result = events
                source = "recent device event"
                if event_rows:
                    updated = first_value(
                        event_rows[0],
                        "date",
                        "timestamp",
                        "time",
                        "createdAt",
                    )

        return self._prayer_response(
            result=source_result,
            times=times,
            requested=requested,
            source=source,
            updated=updated,
            matched_device=match,
        )

    def _prayer_response(
        self,
        *,
        result: MCPToolResult,
        times: dict[str, str],
        requested: str | None,
        source: str,
        updated: Any = None,
        matched_device: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        label = _label(matched_device or {}) or "Pray times"
        if not times:
            response = self._response(
                f"{label} did not return recognisable Fajr, Sunrise, Dhuhr, Asr, Maghrib or Isha times.",
                "fallback-prayer-times-unavailable",
                False,
                result,
            )
            response["technical"] = safe_debug(
                {
                    "source": source,
                    "updated": updated,
                    "device": matched_device,
                    "raw": result.data,
                }
            )
            return response

        if requested:
            selected = times.get(requested)
            if selected:
                message = f"{requested} is at {selected} today."
                shown = {requested: selected}
                subtitle = f"Today's {requested} time"
            else:
                message = f"I found prayer-time data, but {requested} was not included in it."
                shown = times
                subtitle = "Available prayer times"
        else:
            message = "Today's prayer times: " + ", ".join(
                f"{name} {time}" for name, time in times.items()
            ) + "."
            shown = times
            subtitle = "Today's times from the Pray times device"

        items = [
            {
                "icon": _ICON_BY_NAME.get(name, "🕌"),
                "title": name,
                "value": time,
                "subtitle": "Today",
            }
            for name, time in shown.items()
        ]
        display = display_payload(
            "prayer-times",
            requested or "Prayer times",
            subtitle=subtitle,
            metrics=[
                {
                    "label": name,
                    "value": time,
                    "icon": _ICON_BY_NAME.get(name, "🕌"),
                }
                for name, time in shown.items()
            ],
            items=items,
            note=(
                f"Read from {label} {source}."
                + (f" Updated {normalise_text(updated)}." if updated not in (None, "") else "")
            ),
        )
        response = self._response(message, "fallback-prayer-times", True, result)
        response["display"] = display
        response["prayer_times"] = times
        response["requested_prayer"] = requested
        response["technical"] = safe_debug(
            {
                "source": source,
                "updated": updated,
                "device_id": _device_id(matched_device or {}),
                "device_label": label,
                "prayer_times": times,
            }
        )
        return response

    async def _device_events(self, requested_name: str) -> dict[str, Any]:
        if normalise_spoken_device_name(requested_name) != normalise_spoken_device_name("Pray times"):
            return await super()._device_events(requested_name)

        live, match, alternatives = await self._find_prayer_device()
        if not match:
            return await super()._device_events(requested_name)

        events = await self._read_tool(
            "hub_list_device_events",
            {"deviceId": _device_id(match), "hoursBack": 24},
        )
        rows = _rows(events.data, ("events", "items"))
        times = extract_prayer_times(rows)
        updated = (
            first_value(rows[0], "date", "timestamp", "time", "createdAt")
            if rows
            else None
        )
        if times:
            return self._prayer_response(
                result=events,
                times=times,
                requested=None,
                source="most recent event",
                updated=updated,
                matched_device=match,
            )
        return await super()._device_events(requested_name)

# Device Types

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

class DeviceTypeFastFallbackRouter(PrayerTimesRouter):
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
        # Predicates distinguish overlapping Hubitat capabilities (for example,
        # almost every light, socket and appliance exposes ``Switch``).  Once a
        # type supplies that stronger classifier, do not fall through to its
        # broad state keys and accidentally accept the whole capability class.
        if spec.predicate:
            return spec.predicate(item, attrs, metadata)
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

# Device Types Compat

_COMPATIBLE_DEVICE_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "attributes",
    "capabilities",
    "commands",
    "deviceNetworkId",
    "disabled",
    "lastActivity",
    "mcpManaged",
    "parentDeviceId",
]

_MINIMAL_DEVICE_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "capabilities",
]

_GENERIC_CAPABILITIES = {
    "actuator",
    "sensor",
    "refresh",
    "configuration",
    "initialize",
    "health check",
    "battery",
}

class CompatibleDeviceTypeRouter(DeviceTypeFastFallbackRouter):
    """Device-type inventory compatible with strict MCP field validation."""

    async def _all_devices_with_type_metadata(self) -> MCPToolResult:
        result = await self._device_inventory_call(_COMPATIBLE_DEVICE_FIELDS)

        # Keep compatibility with older/newer MCP builds whose accepted field set
        # may differ. A strict field error gets one conservative retry rather than
        # surfacing a raw Invalid params response to the user.
        if result.is_error and self._is_unknown_fields_error(result):
            result = await self._device_inventory_call(_MINIMAL_DEVICE_FIELDS)

        if result.is_error:
            raise MCPError(result.text or "Device-type inventory lookup failed")

        self._add_local_type_labels(result.data)
        return result

    async def _device_inventory_call(self, fields: list[str]) -> MCPToolResult:
        return await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": list(fields),
            },
        )

    @staticmethod
    def _is_unknown_fields_error(result: MCPToolResult) -> bool:
        text = str(result.text or "").lower()
        return "unknown fields" in text or (
            "invalid params" in text and "valid:" in text and "fields" in text
        )

    def _add_local_type_labels(self, data: Any) -> None:
        """Derive a readable type label from supported capability metadata.

        The base presenter understands a local ``type`` key. Adding it after the
        MCP response preserves useful subtitles without requesting the unsupported
        remote ``type``/``deviceType``/``driverName``/``category`` fields.
        """
        for item in self._device_rows(data):
            if any(item.get(key) for key in ("deviceType", "type", "driverName", "category")):
                continue
            label = self._capability_type_label(item.get("capabilities"))
            if not label:
                label = self._attribute_type_label(item.get("currentStates"))
            if label:
                item["type"] = label

    @staticmethod
    def _capability_type_label(value: Any) -> str | None:
        names: list[str] = []
        if isinstance(value, list):
            entries = value
        elif value in (None, ""):
            entries = []
        else:
            entries = [value]

        for entry in entries:
            if isinstance(entry, dict):
                name = (
                    entry.get("displayName")
                    or entry.get("name")
                    or entry.get("label")
                    or entry.get("id")
                )
            else:
                name = entry
            text = str(name or "").strip()
            if not text or text.lower() in _GENERIC_CAPABILITIES:
                continue
            if text not in names:
                names.append(text)

        if not names:
            return None
        return " / ".join(names[:2])

    @staticmethod
    def _attribute_type_label(value: Any) -> str | None:
        if not isinstance(value, dict):
            return None
        keys = {str(key) for key in value}
        ordered = (
            ("motion", "Motion sensor"),
            ("contact", "Contact sensor"),
            ("temperature", "Temperature sensor"),
            ("humidity", "Humidity sensor"),
            ("presence", "Presence sensor"),
            ("illuminance", "Illuminance sensor"),
            ("thermostatMode", "Thermostat"),
            ("lock", "Lock"),
            ("water", "Water sensor"),
            ("smoke", "Smoke detector"),
            ("power", "Power meter"),
            ("energy", "Energy meter"),
            ("switch", "Switch"),
        )
        for key, label in ordered:
            if key in keys:
                return label
        return None

# Device Types Live

_CAPABILITY_FILTERS: dict[str, tuple[str, ...]] = {
    "motion": ("Motion Sensor",),
    "contact": ("Contact Sensor",),
    "temperature": ("Temperature Measurement",),
    "humidity": ("Relative Humidity Measurement",),
    "presence": ("Presence Sensor",),
    "illuminance": ("Illuminance Measurement",),
    "battery": ("Battery",),
    "thermostat": ("Thermostat",),
    "lock": ("Lock",),
    "smoke": ("Smoke Detector",),
    "carbon-monoxide": ("Carbon Monoxide Detector",),
    "water": ("Water Sensor",),
    "power": ("Power Meter",),
    "energy": ("Energy Meter",),
    "light": ("Switch",),
    "switch": ("Switch",),
    "outlet": ("Switch",),
    "fan": ("Fan Control",),
    "valve": ("Valve",),
    "button": ("Pushable Button", "Holdable Button"),
    "alarm": ("Alarm",),
    "acceleration": ("Acceleration Sensor",),
    "sensor": ("Sensor",),
}

_SUMMARY_STATE_TYPES = {
    "motion",
    "contact",
    "temperature",
    "humidity",
    "battery",
    "light",
    "switch",
    "outlet",
    "sensor",
}

_LOCAL_FILTER_AFTER_CAPABILITY = {"light", "switch", "outlet"}

_SUMMARY_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "disabled",
    "lastActivity",
]

_DETAILED_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "attributes",
    "disabled",
    "lastActivity",
]

class CapabilityDeviceRouter(CompatibleDeviceTypeRouter):
    """Capability-first device inventories with truthful zero-result handling."""

    async def _device_type_inventory(self, spec: DeviceTypeSpec) -> dict[str, Any]:
        result, rows, evidence = await self._matching_rows(spec)
        rows = self._dedupe_rows(rows)
        rows.sort(
            key=lambda item: (
                _normalise(self._room_name(item)),
                _normalise(_label(item)),
            )
        )

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
                or evidence.get("type_label")
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

        classification_complete = bool(evidence.get("classification_complete"))
        if rows:
            message = f"{len(rows)} {spec.title.lower()} found:\n" + "\n".join(lines)
            subtitle = f"{len(rows)} selected Hubitat device{'' if len(rows) == 1 else 's'}"
        elif classification_complete:
            message = (
                f"No {spec.title.lower()} were found among the devices selected in "
                "MCP Rule Server."
            )
            subtitle = "No matching selected devices"
        else:
            selected_count = evidence.get("selected_count")
            count_text = (
                f"{selected_count} selected devices"
                if isinstance(selected_count, int)
                else "the selected devices"
            )
            message = (
                f"MCP returned {count_text}, but did not expose enough capability or live-state "
                f"evidence to identify {spec.title.lower()}. I cannot confirm that the count is zero."
            )
            subtitle = "Type evidence incomplete"

        metrics = [
            {"label": "Devices", "value": str(len(rows)) if classification_complete or rows else "Unknown", "icon": spec.icon},
            {"label": "Live states", "value": str(state_count), "icon": "📡"},
        ]
        if attention_count:
            metrics.append(
                {"label": "Need attention", "value": str(attention_count), "icon": "⚠️"}
            )

        display = display_payload(
            "device-type-inventory",
            spec.title,
            subtitle=subtitle,
            metrics=metrics,
            items=items,
            note=(
                "Standard device classes are selected by Hubitat capabilityFilter. "
                "Live values come from currentStates or capability-filtered attributes. "
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
        response["device_count"] = len(rows) if classification_complete or rows else None
        response["technical"] = safe_debug(
            {
                "device_type": spec.key,
                "matched_devices": rows,
                "state_count": state_count,
                "attention_count": attention_count,
                "evidence": evidence,
            }
        )
        return response

    async def _matching_rows(
        self,
        spec: DeviceTypeSpec,
    ) -> tuple[MCPToolResult, list[dict[str, Any]], dict[str, Any]]:
        filters = _CAPABILITY_FILTERS.get(spec.key, ())
        source_results: list[MCPToolResult] = []
        rows: list[dict[str, Any]] = []
        matched_filters: list[str] = []

        for capability in filters:
            detailed = spec.key not in _SUMMARY_STATE_TYPES
            result = await self._capability_devices(capability, detailed=detailed)
            source_results.append(result)
            candidates = self._device_rows(result.data)
            if spec.key in _LOCAL_FILTER_AFTER_CAPABILITY:
                candidates = [
                    item for item in candidates if self._matches_type(spec, item)
                ]
            # The server has already performed the authoritative exact capability
            # match for all other classes, so do not require the response to repeat
            # capability metadata before accepting the devices.
            if candidates:
                matched_filters.append(capability)
                rows.extend(candidates)

        rows = self._dedupe_rows(rows)
        if rows:
            combined = self._combined_result(spec, source_results, rows)
            return combined, rows, {
                "classification_complete": True,
                "method": "capability-filter",
                "capability_filters": list(filters),
                "matched_filters": matched_filters,
                "selected_count": self._selected_count(source_results),
                "type_label": " / ".join(matched_filters[:2]) or spec.title.rstrip("s"),
            }

        # A capability spelling difference or an older MCP build must not produce a
        # false zero. Fetch one lightweight all-device summary and classify common
        # types from live currentStates and labels.
        summary = await self._summary_devices()
        source_results.append(summary)
        summary_rows = self._device_rows(summary.data)
        locally_matched = [
            item for item in summary_rows if self._matches_type(spec, item)
        ]
        locally_matched = self._dedupe_rows(locally_matched)
        if locally_matched:
            combined = self._combined_result(spec, source_results, locally_matched)
            return combined, locally_matched, {
                "classification_complete": True,
                "method": "summary-live-state-fallback",
                "capability_filters": list(filters),
                "selected_count": len(summary_rows),
                "type_label": spec.title.rstrip("s"),
            }

        # Capability-filtered zero is authoritative when the calls succeeded. For
        # classes without a standard capability and without usable summary evidence,
        # report unknown rather than claiming zero.
        complete = bool(filters) and all(not result.is_error for result in source_results[:-1])
        combined = self._combined_result(spec, source_results, [])
        return combined, [], {
            "classification_complete": complete,
            "method": "capability-filter-zero" if complete else "insufficient-evidence",
            "capability_filters": list(filters),
            "selected_count": len(summary_rows),
            "type_label": spec.title.rstrip("s"),
        }

    async def _capability_devices(
        self,
        capability: str,
        *,
        detailed: bool,
    ) -> MCPToolResult:
        fields = _DETAILED_FIELDS if detailed else _SUMMARY_FIELDS
        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": detailed,
                "format": "detailed" if detailed else "summary",
                "capabilityFilter": capability,
                "fields": list(fields),
            },
        )
        if result.is_error:
            raise MCPError(
                result.text or f"Device lookup for capability {capability} failed"
            )
        return result

    async def _summary_devices(self) -> MCPToolResult:
        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": list(_SUMMARY_FIELDS),
            },
        )
        if result.is_error:
            raise MCPError(result.text or "Device summary lookup failed")
        return result

    @staticmethod
    def _selected_count(results: list[MCPToolResult]) -> int | None:
        counts: list[int] = []
        for result in results:
            data = result.data
            if not isinstance(data, dict):
                continue
            for key in ("unfilteredTotal", "total", "count"):
                value = data.get(key)
                if isinstance(value, (int, float)):
                    counts.append(int(value))
                    break
        return max(counts) if counts else None

    @staticmethod
    def _combined_result(
        spec: DeviceTypeSpec,
        results: list[MCPToolResult],
        rows: list[dict[str, Any]],
    ) -> MCPToolResult:
        return MCPToolResult(
            name="hub_list_devices",
            arguments={"deviceType": spec.key},
            raw={
                "sources": [
                    {
                        "name": result.name,
                        "arguments": result.arguments,
                        "is_error": result.is_error,
                    }
                    for result in results
                ]
            },
            text="",
            data={
                "devices": rows,
                "count": len(rows),
                "sourceCalls": len(results),
            },
            is_error=False,
        )

# Device Index

_FRESH_CONTROL_READS: ContextVar[bool] = ContextVar(
    "hubitat_mcp_ai_fresh_control_reads",
    default=False,
)

class IndexedDeviceRouter(CapabilityDeviceRouter):
    """Fast fallback router backed by one shared device intelligence index.

    The final router owns release-specific control settings because the long
    fallback mixin chain does not expose one consistent ``__init__`` signature.
    It also resolves exact spoken aliases through the shared index before fuzzy
    matching and forces fresh state reads throughout each active control request.
    """

    def __init__(
        self,
        *args: Any,
        device_index: DeviceIntelligenceIndex | None = None,
        control_verification_timeout_seconds: float = 7.0,
        control_verification_initial_delay_seconds: float = 0.2,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.device_index = device_index
        self.control_verification_timeout_seconds = max(
            2.0,
            min(20.0, float(control_verification_timeout_seconds)),
        )
        self.control_verification_initial_delay_seconds = max(
            0.05,
            min(2.0, float(control_verification_initial_delay_seconds)),
        )

    @staticmethod
    def _fresh_control_reads_enabled() -> bool:
        """Return the request-local fresh-read state for the current task."""
        return bool(_FRESH_CONTROL_READS.get())

    async def _direct_fresh_devices(
        self,
        capability_filter: str | None = None,
        *,
        detailed: bool = False,
    ) -> MCPToolResult | None:
        """Read Hubitat directly, beyond both index and broker caches.

        ``DeviceIntelligenceIndex(force=True)`` skips its own snapshot, but its
        client is normally the shared MCP broker. That broker may still return a
        cached response or coalesce with a read that began before the command.
        During control verification, use the broker's raw MCP client so every
        poll is a distinct upstream Hubitat read. Non-control reads keep using
        the normal shared caches.
        """
        if self.device_index is None:
            return None

        broker = getattr(self.device_index, "client", None)
        raw_client = getattr(broker, "client", None)
        raw_call = getattr(raw_client, "call_tool", None)
        if not callable(raw_call):
            return None

        arguments: dict[str, Any] = {
            "detailed": bool(detailed),
            "format": "detailed" if detailed else "summary",
            "fields": list(_INDEX_DETAILED_FIELDS if detailed else _INDEX_SUMMARY_FIELDS),
        }
        if capability_filter:
            arguments["capabilityFilter"] = capability_filter

        result = await raw_call("hub_list_devices", arguments)
        if result.is_error:
            raise MCPError(result.text or "Fresh Hubitat device lookup failed")
        return result

    async def _live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._live_devices(capability_filter)

        force = self._fresh_control_reads_enabled()
        if force:
            fresh = await self._direct_fresh_devices(capability_filter, detailed=False)
            if fresh is not None:
                return fresh

        if capability_filter:
            return await self.device_index.capability_result(
                capability_filter,
                detailed=False,
                force=force,
            )
        return await self.device_index.summary_result(force=force)

    async def _summary_devices(self) -> MCPToolResult:
        if self.device_index is None:
            return await super()._summary_devices()

        force = self._fresh_control_reads_enabled()
        if force:
            fresh = await self._direct_fresh_devices(detailed=False)
            if fresh is not None:
                return fresh
        return await self.device_index.summary_result(force=force)

    async def _capability_devices(
        self,
        capability: str,
        *,
        detailed: bool,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._capability_devices(capability, detailed=detailed)

        force = self._fresh_control_reads_enabled()
        if force:
            fresh = await self._direct_fresh_devices(
                capability,
                detailed=detailed,
            )
            if fresh is not None:
                return fresh
        return await self.device_index.capability_result(
            capability,
            detailed=detailed,
            force=force,
        )

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        """Resolve exact index aliases first, then run fully fresh control reads.

        This prevents an exact label such as ``Dehumidifier 2`` being downgraded
        to a fuzzy one-candidate confirmation when the capability response uses a
        slightly different label form. Duplicate aliases remain ambiguous because
        ``exact_device`` only returns a device when one ID owns that alias.

        A ContextVar keeps the fresh-read override local to this asyncio task. Two
        simultaneous controls therefore cannot clear each other's verification
        state while either command is still polling Hubitat.
        """
        resolved_name = requested_name
        if self.device_index is not None:
            try:
                exact, _ = await self.device_index.exact_device(requested_name)
                exact_label = _index_label(exact or {})
                if exact_label:
                    resolved_name = exact_label
            except Exception:
                # The live verified control path remains authoritative if the
                # optional identity index cannot resolve the alias.
                pass

        token = _FRESH_CONTROL_READS.set(True)
        try:
            answer = await super()._control_device(resolved_name, action)
        finally:
            _FRESH_CONTROL_READS.reset(token)

        if resolved_name != requested_name:
            answer["requested_name"] = requested_name
            answer["resolved_device_name"] = resolved_name
            answer["device_index_exact_match"] = True
        return answer

# Engagement

_ROOM_LIST_QUERY = re.compile(
    r"^(?:list|show|display|get)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?"
    r"(?:hubitat\s+)?rooms(?:\s+and\s+(?:their\s+)?device\s+counts?)?[?.!]*$"
    r"|^(?:what|which)\s+rooms\s+(?:do\s+i\s+have|are\s+(?:there|configured|available))[?.!]*$",
    re.IGNORECASE,
)

class EngagementFastFallbackRouter(IndexedDeviceRouter):
    """Final UI/read corrections plus the indexed verified-control router."""

    async def answer(self, query: str) -> dict[str, Any]:
        if _ROOM_LIST_QUERY.match(str(query or "").strip()):
            return await self._rooms_inventory()
        return await super().answer(query)

    async def _rooms_inventory(self) -> dict[str, Any]:
        result = await self._execute_catalog_tool(
            "hub_list_rooms",
            "hub_read_rooms",
            {},
        )
        if result.is_error:
            raise MCPError(result.text or "Room lookup failed")

        message, display = present_rooms(result.data)
        response = self._response(
            message,
            "fallback-rooms",
            True,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response

    async def _device_inventory(self, kind: str) -> dict[str, Any]:
        result = await self._live_devices("Switch" if kind == "light" else None)
        rows = self._device_rows(result.data)
        if kind == "light":
            rows = [item for item in rows if _looks_like_light(item)]

        inventory: list[dict[str, Any]] = []
        rooms: set[str] = set()
        on_count = 0
        for item in rows:
            label = _label(item) or f"Device {_device_id(item)}"
            room = self._room_name(item)
            if room:
                rooms.add(room)
            attrs = live_attributes(item)
            state = self._primary_state(attrs)
            state_key = _normalise(state)
            if _normalise(attrs.get("switch")) == "on":
                on_count += 1
            inventory.append(
                {
                    "icon": "💡" if kind == "light" else device_icon(item, attrs),
                    "title": label,
                    "value": state,
                    "subtitle": room or "No room assigned",
                    "tone": (
                        "success"
                        if state_key in {"on", "active", "open", "present", "heating"}
                        else "warning"
                        if state_key in {"offline", "unavailable", "wet", "unlocked"}
                        else None
                    ),
                }
            )

        inventory.sort(
            key=lambda item: (
                item["subtitle"].lower(),
                item["title"].lower(),
            )
        )
        noun = "light" if kind == "light" else "device"
        message = f"{len(inventory)} {noun}{'' if len(inventory) == 1 else 's'} returned."
        if inventory:
            message += "\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in inventory
            )

        display = display_payload(
            f"{kind}-inventory",
            "All lights" if kind == "light" else "All devices",
            subtitle=f"{len(inventory)} {noun}{'' if len(inventory) == 1 else 's'}",
            metrics=[
                {
                    "label": "Total",
                    "value": str(len(inventory)),
                    "icon": "💡" if kind == "light" else "📟",
                },
                {"label": "On", "value": str(on_count), "icon": "⚡"},
                {"label": "Rooms", "value": str(len(rooms)), "icon": "🚪"},
            ],
            items=inventory,
            note=(
                "Icons are inferred from each device's live attributes, capabilities and "
                "Hubitat label. States come from Hubitat MCP currentStates."
            ),
        )
        response = self._response(
            message,
            f"fallback-{kind}-inventory",
            True,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(result.data)
        return response

# Multi Control

_TARGET_SEPARATOR = re.compile(r"\s*(?:,|\band\b)\s*", re.IGNORECASE)

_TRAILING_DISPLAY_QUALIFIER = re.compile(
    r"\s*(?:\([^()]{1,80}\)|\[[^\[\]]{1,80}\])\s*$"
)

_UNSAFE_TARGET_TERMS = (
    " if ",
    " unless ",
    " when ",
    " except ",
    " but ",
    " then ",
    " after ",
    " before ",
    " whichever ",
    " which ",
    " that are ",
)

_CONTEXT_WORDS = {"it", "them", "that", "those", "these", "same", "other", "there"}

def split_explicit_control_targets(value: str) -> list[str] | None:
    """Return two to six safe explicit target names from one control phrase.

    This intentionally handles only conjunctions such as ``fan switch and fan
    boost``. Contextual pronouns, conditions and long natural-language clauses stay
    on the planner route. Every returned target still has to resolve uniquely to one
    live selected Hubitat device before any write is allowed.
    """

    text = re.sub(r"\s+", " ", str(value or "").strip(" .!?"))
    lowered = f" {text.lower()} "
    if not text or not ("," in text or re.search(r"\band\b", text, re.IGNORECASE)):
        return None
    if any(term in lowered for term in _UNSAFE_TARGET_TERMS):
        return None

    targets = [
        re.sub(r"^(?:the\s+)", "", item.strip(), flags=re.IGNORECASE)
        for item in _TARGET_SEPARATOR.split(text)
    ]
    if not 2 <= len(targets) <= 6 or any(not item for item in targets):
        return None

    for target in targets:
        words = re.findall(r"[a-z0-9]+", target.lower())
        if not words or len(words) > 8 or _CONTEXT_WORDS.intersection(words):
            return None
    return targets

def base_device_label(value: str) -> str:
    """Return a label without trailing display/integration qualifiers.

    Hubitat labels commonly include source suffixes such as ``(Tuya Local)``.
    Spoken commands may safely omit such a suffix only when the resulting base name
    identifies exactly one currently selected device. Multiple matching base labels
    remain ambiguous and are never controlled.
    """

    text = re.sub(r"\s+", " ", str(value or "").strip())
    previous = None
    while text and text != previous:
        previous = text
        text = _TRAILING_DISPLAY_QUALIFIER.sub("", text).strip()
    return _normalise(text)

class MultiControlRouter(EngagementFastFallbackRouter):
    """Final fallback router with exact, verified named multi-device controls."""

    def _match_named_target(
        self,
        requested_name: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[str], str | None]:
        """Resolve an exact label or one unique suffix-free label alias."""

        match, alternatives = self._match_device(requested_name, candidates)
        if match is not None:
            return match, alternatives, "exact-label"

        target = _normalise(requested_name)
        base_matches = [
            item
            for item in candidates
            if _label(item) and base_device_label(_label(item)) == target
        ]
        if len(base_matches) == 1:
            return base_matches[0], [_label(base_matches[0])], "unique-base-label"
        if len(base_matches) > 1:
            return (
                None,
                sorted({_label(item) for item in base_matches if _label(item)}, key=str.lower),
                "ambiguous-base-label",
            )
        return None, alternatives, None

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        targets = split_explicit_control_targets(requested_name)
        if targets is None:
            return await super()._control_device(requested_name, action)

        token = _FRESH_CONTROL_READS.set(True)
        try:
            live_result = await self._live_devices("Switch")
            candidates = self._device_rows(live_result.data)

            # A real selected device label may itself contain "and". Preserve that
            # exact single-device interpretation before treating the phrase as a list.
            whole_match, _, _ = self._match_named_target(requested_name, candidates)
            if whole_match is not None:
                return await super()._control_device(_label(whole_match), action)

            resolved: list[dict[str, Any]] = []
            resolution_details: list[dict[str, Any]] = []
            failures: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            for target in targets:
                match, alternatives, method = self._match_named_target(target, candidates)
                if match is None:
                    error = (
                        "Base device name matches more than one selected device"
                        if method == "ambiguous-base-label"
                        else "No unique selected-device label or safe base-label match"
                    )
                    failures.append(
                        {
                            "target": target,
                            "alternatives": alternatives[:5],
                            "error": error,
                            "match_method": method,
                        }
                    )
                    continue
                device_id = _device_id(match)
                key = str(device_id)
                if device_id is None:
                    failures.append(
                        {
                            "target": target,
                            "alternatives": [],
                            "error": "Matched device has no ID",
                            "match_method": method,
                        }
                    )
                    continue
                if key in seen_ids:
                    failures.append(
                        {
                            "target": target,
                            "alternatives": [_label(match)],
                            "error": "Two requested names resolved to the same device",
                            "match_method": method,
                        }
                    )
                    continue
                seen_ids.add(key)
                resolved.append(match)
                resolution_details.append(
                    {
                        "target": target,
                        "id": device_id,
                        "label": _label(match),
                        "match_method": method,
                    }
                )

            if failures:
                items = []
                lines = []
                for failure in failures:
                    alternatives = failure.get("alternatives") or []
                    detail = str(failure.get("error") or "Could not resolve")
                    if alternatives:
                        detail += ": " + ", ".join(str(item) for item in alternatives)
                    lines.append(f"- {failure['target']}: {detail}")
                    items.append(
                        {
                            "icon": "⚠️",
                            "title": str(failure["target"]),
                            "value": "Not changed",
                            "subtitle": detail,
                            "tone": "warning",
                        }
                    )
                display = display_payload(
                    "named-multi-device-control-blocked",
                    "Multi-device control blocked",
                    subtitle="No commands sent",
                    metrics=[
                        {"label": "Requested", "value": str(len(targets)), "icon": "🎛️"},
                        {"label": "Unique matches", "value": str(len(resolved)), "icon": "✅"},
                        {"label": "Unresolved", "value": str(len(failures)), "icon": "⚠️"},
                    ],
                    items=items,
                    note=(
                        "HomeBrain requires every named target to resolve uniquely before sending "
                        "any command. A trailing label qualifier such as (Tuya Local) may be "
                        "omitted only when the remaining base name is unique."
                    ),
                )
                response = self._response(
                    "No devices were changed because every requested target could not be matched uniquely.\n"
                    + "\n".join(lines),
                    "fallback-named-multi-control-unresolved",
                    False,
                    live_result,
                )
                response.update(
                    {
                        "display": display,
                        "requested_state": _normalise(action),
                        "requested_targets": targets,
                        "technical": safe_debug(
                            {
                                "requested_targets": targets,
                                "resolved": resolution_details,
                                "failures": failures,
                                "commands_sent": 0,
                            }
                        ),
                    }
                )
                return response

            answer = await self._control_group(
                " and ".join(_label(item) or target for item, target in zip(resolved, targets)),
                action,
                resolved,
                live_result,
            )
            answer = dict(answer)
            answer["intent"] = (
                "fallback-named-multi-control-confirmed"
                if answer.get("success")
                else "fallback-named-multi-control-partial"
            )
            answer["requested_targets"] = targets
            answer["resolved_targets"] = [
                {"id": _device_id(item), "label": _label(item)} for item in resolved
            ]
            answer["resolution_details"] = resolution_details
            display = answer.get("display")
            if isinstance(display, dict):
                display["note"] = (
                    "Every named target was uniquely matched before any command was sent. "
                    "Trailing display qualifiers may be omitted only for a unique base label. "
                    "Final switch states were read back from Hubitat using fresh MCP reads."
                )
            return answer
        finally:
            _FRESH_CONTROL_READS.reset(token)

# Light Usage

_PATTERNS = (
    r"^(?:show )?(?:the )?(?:total |combined )?lights? on time(?:(?: for)? today)?$",
    r"^how (?:long|much time) (?:have )?(?:all )?(?:the )?lights? (?:been )?on today$",
    r"^(?:show|calculate|get|give me) (?:the )?(?:total |combined )?(?:daily )?lights? (?:on time|usage) (?:for )?today$",
    r"^(?:which|what) lights? (?:were|have been) on (?:the )?longest today$",
)

def is_light_usage_today_query(query: str) -> bool:
    text = _normalise(query).strip(" .!?")
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in _PATTERNS)

class FastFallbackRouter(MultiControlRouter):
    """Calculate today's combined light usage from Hubitat switch events."""

    async def answer(self, query: str) -> dict[str, Any]:
        if is_light_usage_today_query(query):
            return await self._light_usage_today()
        return await super().answer(query)

    async def _light_usage_today(self) -> dict[str, Any]:
        now = datetime.now().astimezone()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        live = await self._live_devices("Switch")
        lights = [
            item for item in self._device_rows(live.data)
            if _looks_like_light(item) and _device_id(item)
        ]
        lights.sort(key=lambda item: (_normalise(self._room_name(item)), _normalise(_label(item))))

        if not lights:
            answer = self._response(
                "No selected Hubitat lights were found, so today's light-on time cannot be calculated.",
                "fallback-light-usage-today-empty",
                True,
                live,
            )
            answer["display"] = display_payload(
                "light-usage-today",
                "Today's light usage",
                subtitle="No selected lights",
                metrics=[{"label": "Lights", "value": "0", "icon": "💡"}],
                note="Only lights selected in MCP Rule Server can be included.",
            )
            return answer

        semaphore = asyncio.Semaphore(4)

        async def read(item: dict[str, Any]) -> tuple[dict[str, Any], Any, str | None]:
            async with semaphore:
                try:
                    result = await self.client.call_tool(
                        "hub_list_device_events",
                        {"deviceId": _device_id(item), "hoursBack": 36},
                    )
                    if result.is_error:
                        return item, result, result.text or "event history read failed"
                    return item, result, None
                except Exception as exc:
                    return item, None, str(exc) or exc.__class__.__name__

        reads = await asyncio.gather(*(read(item) for item in lights))
        usage: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for item, result, error in reads:
            label = _label(item) or f"Device {_device_id(item)}"
            if error or result is None:
                errors.append({"device": label, "error": error or "No result"})
                continue
            calculated = calculate_on_time(
                switch_events(result.data, now.tzinfo),
                day_start,
                now,
                _normalise(live_attributes(item).get("switch")),
            )
            usage.append(
                {
                    "id": _device_id(item),
                    "label": label,
                    "room": self._room_name(item) or "No room assigned",
                    **calculated,
                }
            )

        if not usage:
            answer = self._response(
                "Today's light-on time is unavailable because Hubitat returned no usable switch-event history.",
                "fallback-light-usage-today-unavailable",
                False,
                live,
            )
            answer["route"] = "mcp-fast"
            answer["display"] = display_payload(
                "light-usage-today-unavailable",
                "Light usage unavailable",
                subtitle="Historical switch events could not be read",
                metrics=[
                    {"label": "Lights", "value": str(len(lights)), "icon": "💡"},
                    {"label": "Event reads", "value": "0", "icon": "🕘"},
                    {"label": "Cloud", "value": "Not used", "icon": "🛡️"},
                ],
                note="; ".join(f"{item['device']}: {item['error']}" for item in errors[:6]),
            )
            answer["technical"] = safe_debug(
                {
                    "period_start": day_start.isoformat(),
                    "period_end": now.isoformat(),
                    "selected_light_count": len(lights),
                    "errors": errors,
                    "cloud_fallback_blocked": True,
                }
            )
            return answer

        usage.sort(key=lambda item: (-float(item["seconds"]), str(item["label"]).lower()))
        active = [item for item in usage if float(item["seconds"]) > 0]
        incomplete = [item for item in usage if item.get("incomplete")]
        total_seconds = sum(float(item["seconds"]) for item in usage)

        items: list[dict[str, Any]] = []
        lines: list[str] = []
        for item in active[:30]:
            notes = list(item.get("notes") or [])
            items.append(
                {
                    "icon": "💡",
                    "title": str(item["label"]),
                    "value": duration_text(float(item["seconds"]), True),
                    "subtitle": str(item["room"]) + (" · Incomplete: " + "; ".join(notes) if notes else ""),
                    "tone": "warning" if notes else None,
                }
            )
            lines.append(
                f"- {item['label']}: {duration_text(float(item['seconds']))}"
                + (" (history incomplete)" if notes else "")
            )

        if active:
            message = (
                f"Combined light-on time today is {duration_text(total_seconds)} across {len(active)} "
                f"light{'s' if len(active) != 1 else ''}. This is bulb-hours: overlapping lights "
                "are added together, so it is not wall-clock elapsed time.\n"
                + "\n".join(lines)
                + f"\nLongest individual on-time: {active[0]['label']} at "
                + duration_text(float(active[0]["seconds"]))
                + "."
            )
        else:
            message = "No complete light-on intervals were recorded from midnight to now."
        if incomplete:
            message += (
                f"\n{len(incomplete)} light event log{'s are' if len(incomplete) != 1 else ' is'} "
                "incomplete. Uncertain intervals were not estimated or added."
            )
        if errors:
            message += f"\nEvent history for {len(errors)} selected light{'s' if len(errors) != 1 else ''} was unavailable and excluded."

        answer = self._response(message, "fallback-light-usage-today", True, live)
        answer["route"] = "mcp-fast"
        answer["display"] = display_payload(
            "light-usage-today",
            "Today's light usage",
            subtitle=f"Midnight to {now.strftime('%H:%M')}",
            metrics=[
                {"label": "Combined bulb-hours", "value": duration_text(total_seconds, True), "icon": "⏱️"},
                {"label": "Lights with usage", "value": str(len(active)), "icon": "💡"},
                {"label": "Incomplete logs", "value": str(len(incomplete) + len(errors)), "icon": "⚠️"},
            ],
            items=items,
            note=(
                "Calculated from Hubitat switch on/off events. Individual durations are added, "
                "so simultaneous lights count separately. AI does not calculate the result."
            ),
        )
        answer.update(
            {
                "metric": "combined-bulb-hours",
                "combined_seconds": total_seconds,
                "lights_with_usage": len(active),
                "incomplete_logs": len(incomplete) + len(errors),
                "usage": usage,
            }
        )
        answer["technical"] = safe_debug(
            {
                "period_start": day_start.isoformat(),
                "period_end": now.isoformat(),
                "metric": "combined-bulb-hours",
                "selected_light_count": len(lights),
                "event_reads_succeeded": len(usage),
                "event_reads_failed": len(errors),
                "combined_seconds": total_seconds,
                "light_usage": usage,
                "errors": errors,
                "calculation": "Python paired Hubitat switch events; uncertain intervals were excluded.",
                "cloud_fallback_blocked": True,
            }
        )
        return answer

__all__ = [
    "CapabilityDeviceRouter",
    "CompatibleDeviceTypeRouter",
    "DeviceTypeFastFallbackRouter",
    "DeviceTypeSpec",
    "EngagementFastFallbackRouter",
    "FastFallbackRouter",
    "IndexedDeviceRouter",
    "MultiControlRouter",
    "PrayerTimesRouter",
    "_FRESH_CONTROL_READS",
    "_ROOM_LIST_QUERY",
    "base_device_label",
    "extract_prayer_times",
    "is_light_usage_today_query",
    "split_explicit_control_targets",
]
