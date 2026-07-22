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
        r"(?:listed\s+)?(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?(.+?)(?:\s+room)?[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what|which)\s+devices\s+(?:are\s+)?(?:listed\s+)?"
        r"(?:in|under|inside|from|assigned\s+to)\s+(?:the\s+)?(.+?)(?:\s+room)?[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:list|show|display)\s+(?:the\s+)?(.+?)\s+room(?:\s+devices)?[?.!]*$",
        re.IGNORECASE,
    ),
    # Mobile/voice shorthand: "List Apps" where Apps is an exact Hubitat room.
    re.compile(
        r"^(?:list|show|display)\s+(?:the\s+)?([a-z0-9][a-z0-9 &'_\-]{0,50})[?.!]*$",
        re.IGNORECASE,
    ),
)

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
        if exact is None:
            return None

        devices_result = await self._live_devices()
        if devices_result.is_error:
            raise MCPError(devices_result.text or "Device lookup failed")

        room_name = exact["name"]
        room_key = self._room_key(room_name)
        devices = [
            item
            for item in self._device_rows(devices_result.data)
            if self._room_key(self._room_name(item)) == room_key
        ]

        items: list[dict[str, Any]] = []
        on_count = 0
        active_count = 0
        for item in devices:
            attrs = live_attributes(item)
            state = self._primary_state(attrs)
            normalised_state = _normalise(state)
            if _normalise(attrs.get("switch")) == "on":
                on_count += 1
            if normalised_state in {"active", "open", "present", "unlocked"}:
                active_count += 1

            device_type = str(
                first_value(item, "deviceType", "type", "category", "driverName")
                or "Hubitat device"
            )
            if _looks_like_light(item):
                icon = "💡"
            elif "motion" in _normalise(device_type + " " + str(attrs.keys())):
                icon = "🏃"
            elif "temperature" in attrs or "humidity" in attrs:
                icon = "🌡️"
            else:
                icon = "📱"

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
            message = (
                f"{count} device{'' if count == 1 else 's'} are assigned to the {room_name} room:\n"
                + "\n".join(
                    f"- {item['title']}: {item['value']}" for item in items
                )
            )
        else:
            message = f'The Hubitat room "{room_name}" exists, but no selected MCP devices are assigned to it.'

        display = display_payload(
            "room-device-inventory",
            f"{room_name} room",
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
                "devices": devices_result.data,
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
            if index == len(_ROOM_DEVICE_PATTERNS) - 1:
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
