from __future__ import annotations

import re
from typing import Any

from device_presentation import device_icon
from fallback_router import _device_id, _label, _normalise
from fast_fallback_device_index import FastFallbackRouter as IndexedDeviceRouter
from fast_fallback_live import _looks_like_light, live_attributes
from mcp_client import MCPError
from presenter import display_payload, present_rooms, safe_debug


_ROOM_LIST_QUERY = re.compile(
    r"^(?:list|show|display|get)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?"
    r"(?:hubitat\s+)?rooms(?:\s+and\s+(?:their\s+)?device\s+counts?)?[?.!]*$"
    r"|^(?:what|which)\s+rooms\s+(?:do\s+i\s+have|are\s+(?:there|configured|available))[?.!]*$",
    re.IGNORECASE,
)


class FastFallbackRouter(IndexedDeviceRouter):
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


__all__ = ["FastFallbackRouter"]
