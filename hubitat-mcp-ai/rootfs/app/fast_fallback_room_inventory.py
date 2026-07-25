from __future__ import annotations

import re
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_essentials import FastFallbackRouter as EssentialsFastFallbackRouter
from fast_fallback_live import _looks_like_light, live_attributes
from mcp_client import MCPError
from presenter import display_payload, first_value, safe_debug, walk


_ROOM_DEVICE_PATTERNS = (
    re.compile(
        r"^(?:list|show|display|find)\s+(?:all\s+)?devices\s+"
        r"(?:listed\s+)?(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what|which)\s+devices\s+(?:are\s+)?(?:listed\s+)?"
        r"(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?(.+?)[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:list|show|display)\s+(?:the\s+)?(.+?)\s+room[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:list|show|display|find)\s+(?:all\s+)?(?:the\s+)?"
        r"(.+?)\s+devices[?.!]*$",
        re.IGNORECASE,
    ),
    # Mobile/voice shorthand: "List Apps" where Apps is an exact Hubitat room.
    re.compile(
        r"^(?:list|show|display)\s+(?:the\s+)?([a-z0-9][a-z0-9 &'_\-]{0,50})[?.!]*$",
        re.IGNORECASE,
    ),
)

_MAX_EMPTY_SENSOR_DETAIL_PROBES = 4


def _needs_empty_device_detail(
    item: dict[str, Any],
    attrs: dict[str, Any],
) -> bool:
    """Identify useful devices whose compact inventory omitted live states."""

    if attrs:
        return False

    text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in (
                "label",
                "name",
                "displayName",
                "deviceType",
                "type",
                "category",
                "capabilities",
            )
        )
    )

    return any(
        condition
        for condition in (
            " lux" in f" {text}",
            "illuminance" in text,
            " fan" in f" {text}",
            "fancontrol" in text,
            "fan control" in text,
            "power meter" in text,
            "powermeter" in text,
            "energy meter" in text,
            "energymeter" in text,
            "thermostat" in text,
            "temperaturemeasurement" in text,
            "lock" in text,
            "valve" in text,
            "water sensor" in text,
            "watersensor" in text,
            "leak" in text,
            "smoke" in text,
        )
    )


def _detail_device_record(value: Any, device_id: str) -> dict[str, Any] | None:
    """Find the requested device record inside a detailed MCP response."""

    fallback: dict[str, Any] | None = None

    for candidate in walk(value):
        if not isinstance(candidate, dict):
            continue

        candidate_id = str(
            candidate.get("id")
            or candidate.get("deviceId")
            or candidate.get("device_id")
            or ""
        )

        if candidate_id and candidate_id == device_id:
            return candidate

        if fallback is None and any(
            key in candidate
            for key in (
                "currentStates",
                "current_states",
                "attributes",
                "states",
                "illuminance",
                "speed",
                "switch",
                "power",
                "energy",
                "thermostatMode",
                "thermostatOperatingState",
                "thermostatSetpoint",
                "heatingSetpoint",
                "coolingSetpoint",
                "lock",
                "valve",
                "water",
                "smoke",
            )
        ):
            fallback = candidate

    return fallback


def _format_number(value: Any) -> str:
    try:
        number = float(str(value).replace("%", "").strip())
    except Exception:
        return str(value).strip()
    return f"{number:g}"


def _room_display_title(room_name: str) -> str:
    """Avoid titles such as 'Living Room room'."""

    name = str(room_name or "").strip()
    if _normalise(name).endswith(" room"):
        return name
    return f"{name} room"


def _room_device_icon(
    item: dict[str, Any],
    attrs: dict[str, Any],
    device_type: str,
) -> str:
    """Choose a meaningful room-card icon from label, type and live attributes."""

    text = _normalise(
        " ".join(
            (
                str(item.get("label") or ""),
                str(item.get("name") or ""),
                str(item.get("displayName") or ""),
                str(device_type or ""),
                " ".join(str(key) for key in attrs),
            )
        )
    )

    if _looks_like_light(item):
        return "💡"
    if "fan" in text or "speed" in attrs:
        return "🌀"
    if "illuminance" in attrs or " lux" in f" {text}":
        return "🔆"
    if any(
        key in attrs
        for key in (
            "thermostatMode",
            "thermostatOperatingState",
            "thermostatSetpoint",
            "heatingSetpoint",
            "coolingSetpoint",
        )
    ):
        return "♨️"
    if "power" in attrs or "energy" in attrs:
        return "⚡"
    if "lock" in attrs:
        return "🔒"
    if "valve" in attrs:
        return "🚰"
    if "water" in attrs:
        return "💧"
    if "smoke" in attrs:
        return "🚨"
    if "temperature" in attrs:
        return "🌡️"
    if "humidity" in attrs:
        return "💧"
    if "motion" in attrs:
        return "🏃"
    if "presence" in attrs:
        return "📍"
    if "contact" in attrs:
        return "🚪"
    if "battery" in attrs:
        return "🔋"
    if "switch" in attrs:
        return "🔌"
    return "📱"


def _room_device_states(attrs: dict[str, Any], primary_state: str) -> list[str]:
    """Return useful compact live states without discarding secondary metrics."""

    states: list[str] = []

    speed = attrs.get("speed")
    illuminance = attrs.get("illuminance")
    temperature = attrs.get("temperature")
    humidity = attrs.get("humidity")
    power = attrs.get("power")
    energy = attrs.get("energy")
    thermostat_mode = attrs.get("thermostatMode")
    operating_state = attrs.get("thermostatOperatingState")
    thermostat_setpoint = attrs.get("thermostatSetpoint")
    heating_setpoint = attrs.get("heatingSetpoint")
    cooling_setpoint = attrs.get("coolingSetpoint")

    if thermostat_mode not in (None, ""):
        states.append(
            str(thermostat_mode).strip().replace("_", " ").title()
        )

    if operating_state not in (None, ""):
        formatted_operating = (
            str(operating_state).strip().replace("_", " ").title()
        )
        if _normalise(formatted_operating) not in {
            _normalise(item) for item in states
        }:
            states.append(formatted_operating)

    setpoint = next(
        (
            value
            for value in (
                thermostat_setpoint,
                heating_setpoint,
                cooling_setpoint,
            )
            if value not in (None, "")
        ),
        None,
    )
    if setpoint is not None:
        states.append(f"{_format_number(setpoint)}°C setpoint")

    if speed not in (None, ""):
        states.append(str(speed).strip().replace("_", " ").title())

    if illuminance not in (None, ""):
        states.append(f"{_format_number(illuminance)} lx")

    if temperature not in (None, ""):
        states.append(f"{_format_number(temperature)}°C")

    if humidity not in (None, ""):
        states.append(f"{_format_number(humidity)}% humidity")

    if power not in (None, ""):
        states.append(f"{_format_number(power)} W")

    if energy not in (None, ""):
        states.append(f"{_format_number(energy)} kWh")

    for attribute, labels in (
        ("switch", {"on": "On", "off": "Off"}),
        ("motion", {"active": "Active", "inactive": "Inactive"}),
        ("contact", {"open": "Open", "closed": "Closed"}),
        ("presence", {"present": "Present", "not present": "Not present"}),
        ("lock", {"locked": "Locked", "unlocked": "Unlocked"}),
        ("valve", {"open": "Open", "closed": "Closed"}),
        ("water", {"wet": "Wet", "dry": "Dry"}),
        ("smoke", {"detected": "Smoke detected", "clear": "Clear"}),
    ):
        value = _normalise(attrs.get(attribute))
        formatted = labels.get(value)
        if formatted and _normalise(formatted) not in {
            _normalise(item) for item in states
        }:
            states.append(formatted)
            break

    battery = attrs.get("battery")
    if battery not in (None, "") and not states:
        states.append(f"{_format_number(battery)}% battery")

    if not states and primary_state:
        states.append(str(primary_state))

    return states


_RESERVED_SHORTHAND = {
    "all devices",
    "devices",
    "all lights",
    "lights",
    "switches",
    "rooms",
    "my rooms",
    "hubitat rooms",
    "my hubitat rooms",
    "rules",
    "active rules",
    "automation rules",
    "active automation rules",
    "low batteries",
    "batteries",
    "weather",
    "forecast",
    "motion sensors",
    "active motion sensors",
    "hub health",
    "hub status",
    "hub resources",
}


class FastFallbackRouter(EssentialsFastFallbackRouter):
    """Essential routes plus exact Hubitat room-device inventory lookup."""

    async def answer(self, query: str) -> dict[str, Any]:
        candidate = self._room_candidate(query)
        if candidate:
            room_answer = await self._room_inventory_if_exact(candidate)
            if room_answer is not None:
                return room_answer
        return await super().answer(query)

    async def _room_inventory_if_exact(self, requested_room: str) -> dict[str, Any] | None:
        rooms_result = await self._execute_catalog_tool(
            "hub_list_rooms",
            "hub_read_rooms",
            {},
        )
        if rooms_result.is_error:
            raise MCPError(rooms_result.text or "Room lookup failed")

        rooms = self._room_rows(rooms_result.data)
        requested_key = self._room_key(requested_room)
        exact = next(
            (room for room in rooms if self._room_key(room["name"]) == requested_key),
            None,
        )
        # Prefer an exact room whose real name includes "room". Only treat a
        # trailing "room" as descriptive wording when the full name did not
        # match, e.g. "devices under Apps room" for the room named "Apps".
        if exact is None:
            without_suffix = re.sub(
                r"\s+room$",
                "",
                str(requested_room or "").strip(),
                flags=re.IGNORECASE,
            )
            if without_suffix != str(requested_room or "").strip():
                fallback_key = self._room_key(without_suffix)
                exact = next(
                    (
                        room
                        for room in rooms
                        if self._room_key(room["name"]) == fallback_key
                    ),
                    None,
                )
        if exact is None:
            return None

        devices_result = await self._live_devices()
        if devices_result.is_error:
            raise MCPError(devices_result.text or "Device lookup failed")

        room_name = exact["name"]
        room_key = self._room_key(room_name)
        all_device_rows = self._device_rows(devices_result.data)
        devices = [
            item
            for item in all_device_rows
            if self._room_key(self._room_name(item)) == room_key
        ]

        items: list[dict[str, Any]] = []
        detail_reads: list[dict[str, Any]] = []
        detail_probes = 0
        on_count = 0
        active_count = 0

        for item in devices:
            attrs = live_attributes(item)

            if (
                detail_probes < _MAX_EMPTY_SENSOR_DETAIL_PROBES
                and _needs_empty_device_detail(item, attrs)
            ):
                device_id = str(_device_id(item) or "")
                if device_id:
                    detail_probes += 1
                    try:
                        detail_result = await self._execute_catalog_tool(
                            "hub_get_device",
                            "hub_read_devices",
                            {"deviceId": device_id},
                        )
                    except MCPError as exc:
                        detail_reads.append(
                            {
                                "device_id": device_id,
                                "label": _label(item),
                                "success": False,
                                "error": str(exc),
                            }
                        )
                    else:
                        detail_success = not detail_result.is_error
                        detail_reads.append(
                            {
                                "device_id": device_id,
                                "label": _label(item),
                                "success": detail_success,
                            }
                        )
                        if detail_success:
                            detail_record = _detail_device_record(
                                detail_result.data,
                                device_id,
                            )
                            detail_attrs = live_attributes(detail_record or {})
                            if detail_attrs:
                                attrs.update(detail_attrs)

            state = self._primary_state(attrs)
            presented_states = _room_device_states(attrs, state)
            state = ", ".join(presented_states)
            normalised_state = _normalise(self._primary_state(attrs))
            if _normalise(attrs.get("switch")) == "on":
                on_count += 1
            if normalised_state in {"active", "open", "present", "unlocked"}:
                active_count += 1

            device_type = str(
                first_value(item, "deviceType", "type", "category", "driverName")
                or "Hubitat device"
            )
            icon = _room_device_icon(item, attrs, device_type)

            items.append(
                {
                    "icon": icon,
                    "title": _label(item) or f"Device {_device_id(item)}",
                    "value": state,
                    "subtitle": device_type,
                    "tone": (
                        "success"
                        if normalised_state in {"on", "active", "open", "present"}
                        else None
                    ),
                }
            )

        items.sort(key=lambda item: item["title"].lower())
        count = len(items)
        if items:
            room_title = _room_display_title(room_name)
            message = (
                f"{count} device{'' if count == 1 else 's'} are assigned to {room_title}:\n"
                + "\n".join(
                    f"- {item['title']}: {item['value']}" for item in items
                )
            )
        else:
            message = f'The Hubitat room "{room_name}" exists, but no selected MCP devices are assigned to it.'

        display = display_payload(
            "room-device-inventory",
            _room_display_title(room_name),
            subtitle=f"{count} device{'' if count == 1 else 's'} assigned",
            metrics=[
                {"label": "Devices", "value": str(count), "icon": "📱"},
                {"label": "Switches on", "value": str(on_count), "icon": "⚡"},
                {"label": "Active/open", "value": str(active_count), "icon": "📡"},
            ],
            items=items,
            note=(
                "Room membership and live states come from Hubitat MCP. Devices not selected "
                "in MCP Rule Server cannot appear here."
            ),
        )
        response = self._response(
            message,
            "fallback-room-devices",
            True,
            devices_result,
        )
        response["display"] = display
        response["room"] = room_name
        response["technical"] = safe_debug(
            {
                "matched_room": exact,
                "inventory_count": len(all_device_rows),
                "room_device_count": len(devices),
                "detail_probes": detail_probes,
                "detail_reads": detail_reads,
            }
        )
        return response

    @classmethod
    def _room_candidate(cls, query: str) -> str | None:
        text = str(query or "").strip()
        for index, pattern in enumerate(_ROOM_DEVICE_PATTERNS):
            match = pattern.match(text)
            if not match:
                continue
            candidate = re.sub(r"\s+", " ", match.group(1).strip(" .!?"))
            if not candidate:
                return None

            # The general "<room name> devices" form correctly preserves
            # multi-word room names such as "living room". Clean up only
            # duplicated descriptive forms such as "Livingroom room" or
            # "Bedroom room".
            duplicated_room = re.fullmatch(
                r"(.+?room)\s+room",
                candidate,
                flags=re.IGNORECASE,
            )
            if duplicated_room:
                candidate = duplicated_room.group(1)

            if index >= len(_ROOM_DEVICE_PATTERNS) - 2:
                normalised = _normalise(candidate)
                if normalised in _RESERVED_SHORTHAND:
                    return None
                if len(normalised.split()) > 4:
                    return None
            return candidate
        return None

    @staticmethod
    def _room_key(value: Any) -> str:
        """Canonical room key tolerant of spaces, punctuation and spoken numbering."""
        return re.sub(r"[^a-z0-9]+", "", _normalise(value))

    @staticmethod
    def _room_rows(value: Any) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for item in walk(value):
            if not isinstance(item, dict):
                continue
            name = first_value(item, "name", "label", "roomName")
            room_id = first_value(item, "id", "roomId")
            if not name:
                continue
            key = FastFallbackRouter._room_key(name)
            if not key:
                continue
            rows[key] = {"name": str(name), "id": room_id}
        return sorted(rows.values(), key=lambda room: room["name"].lower())


__all__ = ["FastFallbackRouter"]
