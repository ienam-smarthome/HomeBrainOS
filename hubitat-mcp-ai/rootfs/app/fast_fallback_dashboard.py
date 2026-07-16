from __future__ import annotations

import json
import re
from statistics import mean
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_inventory import FastFallbackRouter as InventoryFastFallbackRouter
from fast_fallback_live import _looks_like_light, live_attributes
from hub_cpu_probe import probe_hub_cpu
from mcp_client import MCPError
from presenter import (
    compact_number,
    display_payload,
    first_mapping,
    first_value,
    format_memory_kb,
    safe_debug,
)


_COMPARE_RE = re.compile(
    r"^compare\s+(humidity|temperature)\s+(?:in|between)\s+(?:the\s+)?(.+?)\s+and\s+(?:the\s+)?(.+?)[?.!]*$",
    re.IGNORECASE,
)


class FastFallbackRouter(InventoryFastFallbackRouter):
    """Fast structured inventories, room comparisons and live hub resources."""

    def __init__(
        self,
        client: Any,
        attention_stale_hours: float = 48,
        *,
        cpu_probe_enabled: bool = True,
        cpu_probe_timeout_seconds: float = 2.5,
    ) -> None:
        super().__init__(client, attention_stale_hours=attention_stale_hours)
        self.cpu_probe_enabled = bool(cpu_probe_enabled)
        self.cpu_probe_timeout_seconds = max(0.5, float(cpu_probe_timeout_seconds))

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if re.match(r"^(?:list|show)\s+(?:all\s+)?devices\??$", q):
            return await self._device_inventory("device")
        if re.match(r"^(?:list|show)\s+(?:all\s+)?lights\??$", q):
            return await self._device_inventory("light")
        comparison = _COMPARE_RE.match(q)
        if comparison:
            return await self._compare_rooms(
                attribute=comparison.group(1).lower(),
                first_room=comparison.group(2),
                second_room=comparison.group(3),
            )
        return await super().answer(query)

    async def _hub_resources(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        data = first_mapping(result.data)
        model = first_value(data, "name", "hubName", "model") or "Hubitat hub"
        firmware = first_value(data, "firmwareVersion", "currentVersion")
        local_ip = first_value(data, "localIP", "ip", "ipAddress")
        free_memory = format_memory_kb(
            first_value(data, "freeMemoryKB", "freeMemoryKb")
        )
        temperature = compact_number(
            first_value(data, "internalTempCelsius", "temperature"),
            "°C",
        )
        database_size = format_memory_kb(
            first_value(data, "databaseSizeKB", "databaseSizeKb")
        )
        uptime = first_value(
            data,
            "uptimeFormatted",
            "formattedUptime",
            "uptime",
        )

        cpu = (
            await probe_hub_cpu(
                local_ip,
                timeout_seconds=self.cpu_probe_timeout_seconds,
            )
            if self.cpu_probe_enabled
            else {
                "available": False,
                "mode": "disabled",
                "error": "Direct local CPU probing is disabled in add-on options.",
            }
        )

        metrics: list[dict[str, Any]] = []
        if cpu.get("available"):
            metrics.append(
                {
                    "label": str(cpu.get("label") or "CPU load"),
                    "value": str(cpu.get("value") or "—"),
                    "icon": "🧠",
                }
            )
        else:
            metrics.append(
                {
                    "label": "CPU load",
                    "value": "Unavailable",
                    "icon": "🧠",
                }
            )

        for label, value, icon in (
            ("Free memory", free_memory, "💾"),
            ("Temperature", temperature, "🌡️"),
            ("Database", database_size, "🗄️"),
            ("Uptime", uptime, "⏱️"),
        ):
            if value not in (None, ""):
                metrics.append({"label": label, "value": str(value), "icon": icon})

        lines: list[str] = []
        if cpu.get("mode") == "percent":
            lines.append(f"Hub CPU load is {cpu['value']}.")
        elif cpu.get("mode") == "load-average":
            core_text = (
                f" across {cpu['processors']} processors"
                if cpu.get("processors")
                else ""
            )
            lines.append(
                f"Hub CPU one-minute load average is {cpu['value']}{core_text}."
            )
        else:
            lines.append(
                "Hub CPU load could not be read from the local /hub/cpuInfo endpoint."
            )
        if free_memory:
            lines.append(f"Free memory is {free_memory}.")
        if temperature:
            lines.append(f"Hub internal temperature is {temperature}.")
        if database_size:
            lines.append(f"Database size is {database_size}.")
        if uptime:
            lines.append(f"Uptime is {uptime}.")

        note = (
            "CPU is read directly from Hubitat's local /hub/cpuInfo endpoint; memory, "
            "temperature, database and uptime come from Kingpanther MCP."
            if cpu.get("available")
            else (
                "Kingpanther MCP does not expose CPU load. The add-on also tried Hubitat's "
                "local /hub/cpuInfo endpoint, but it was unavailable. "
                + str(cpu.get("error") or "")
            ).strip()
        )
        display = display_payload(
            "hub-resources",
            "Hub resources",
            subtitle=" · ".join(
                value
                for value in (
                    str(model),
                    f"Firmware {firmware}" if firmware else None,
                )
                if value
            ),
            metrics=metrics,
            note=note,
        )
        response = self._response(
            "\n".join(lines),
            "fallback-hub-resources",
            True,
            result,
        )
        response["display"] = display
        response["technical"] = json.dumps(
            {"hub_info": data, "cpu_probe": cpu},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
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
            if _normalise(attrs.get("switch")) == "on":
                on_count += 1
            inventory.append(
                {
                    "icon": "💡" if kind == "light" else "🔌",
                    "title": label,
                    "value": state,
                    "subtitle": room or "No room assigned",
                    "tone": "success" if state.lower() in {"on", "active", "open"} else None,
                }
            )

        inventory.sort(key=lambda item: (item["subtitle"].lower(), item["title"].lower()))
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
                {"label": "Total", "value": str(len(inventory)), "icon": "💡" if kind == "light" else "📱"},
                {"label": "On", "value": str(on_count), "icon": "⚡"},
                {"label": "Rooms", "value": str(len(rooms)), "icon": "🚪"},
            ],
            items=inventory,
            note="Live device states were read directly from Hubitat MCP currentStates.",
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

    async def _compare_rooms(
        self,
        *,
        attribute: str,
        first_room: str,
        second_room: str,
    ) -> dict[str, Any]:
        result = await self._live_devices()
        rows = self._device_rows(result.data)
        targets = [self._clean_room(first_room), self._clean_room(second_room)]
        unit = "%" if attribute == "humidity" else "°C"
        readings: dict[str, list[tuple[str, float]]] = {room: [] for room in targets}

        for item in rows:
            item_room = self._room_name(item)
            label = _label(item) or f"Device {_device_id(item)}"
            attrs = live_attributes(item)
            raw = attrs.get(attribute)
            try:
                value = float(str(raw).replace("%", "").replace("°C", "").strip())
            except Exception:
                continue
            for target in targets:
                if self._room_matches(target, item_room, label):
                    readings[target].append((label, value))

        metrics: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        averages: dict[str, float] = {}
        for room in targets:
            values = readings[room]
            if values:
                average = mean(value for _name, value in values)
                averages[room] = average
                metrics.append(
                    {
                        "label": room,
                        "value": f"{average:.1f}{unit}",
                        "icon": "💧" if attribute == "humidity" else "🌡️",
                    }
                )
                for name, value in sorted(values, key=lambda row: row[0].lower()):
                    items.append(
                        {
                            "icon": "💧" if attribute == "humidity" else "🌡️",
                            "title": name,
                            "value": f"{value:g}{unit}",
                            "subtitle": room,
                        }
                    )
            else:
                metrics.append(
                    {
                        "label": room,
                        "value": "No reading",
                        "icon": "❔",
                    }
                )

        if len(averages) == 2:
            first_value_avg = averages[targets[0]]
            second_value_avg = averages[targets[1]]
            difference = abs(first_value_avg - second_value_avg)
            warmer = targets[0] if first_value_avg > second_value_avg else targets[1]
            if attribute == "humidity":
                relation = "more humid"
            else:
                relation = "warmer"
            message = (
                f"{targets[0]} averages {first_value_avg:.1f}{unit}; "
                f"{targets[1]} averages {second_value_avg:.1f}{unit}. "
                f"{warmer} is {difference:.1f}{unit} {relation}."
            )
        else:
            missing = [room for room in targets if room not in averages]
            message = (
                f"I could not compare {attribute} accurately because no live reading was found "
                f"for {', '.join(missing)}."
            )

        display = display_payload(
            "room-environment-comparison",
            f"{attribute.title()} comparison",
            subtitle=f"{targets[0]} and {targets[1]}",
            metrics=metrics,
            items=items,
            note="Averages use every live matching sensor in each room.",
        )
        response = self._response(
            message,
            f"fallback-compare-{attribute}",
            len(averages) == 2,
            result,
        )
        response["display"] = display
        response["technical"] = safe_debug(
            {
                "attribute": attribute,
                "rooms": targets,
                "readings": readings,
            }
        )
        return response

    @staticmethod
    def _clean_room(value: str) -> str:
        text = re.sub(r"[?.!]+$", "", str(value or "").strip())
        return re.sub(r"\s+", " ", text).title()

    @staticmethod
    def _room_name(item: dict[str, Any]) -> str:
        value = item.get("room") or item.get("roomName")
        if isinstance(value, dict):
            value = value.get("name") or value.get("label")
        return str(value or "").strip()

    @staticmethod
    def _room_matches(target: str, room: str, label: str) -> bool:
        wanted = _normalise(target)
        return wanted == _normalise(room) or (
            not room and wanted in _normalise(label)
        )

    @staticmethod
    def _primary_state(attrs: dict[str, Any]) -> str:
        for key, suffix in (
            ("switch", ""),
            ("motion", ""),
            ("contact", ""),
            ("presence", ""),
            ("temperature", "°C"),
            ("humidity", "%"),
            ("battery", "%"),
        ):
            value = attrs.get(key)
            if value not in (None, ""):
                text = str(value)
                return text.title() if not suffix else f"{text}{suffix}"
        return "Available"


__all__ = ["FastFallbackRouter"]
