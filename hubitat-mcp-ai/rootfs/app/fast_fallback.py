from __future__ import annotations

from typing import Any

from fallback_router import (
    HomeBrainFallbackRouter,
    _attributes,
    _device_id,
    _label,
    _normalise,
)
from mcp_client import MCPError, MCPToolResult
from presenter import (
    display_payload,
    present_hub_info,
    present_rooms,
    present_rules,
    present_weather,
    safe_debug,
)


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return None


class FastFallbackRouter(HomeBrainFallbackRouter):
    """Fast deterministic MCP routes with human-friendly structured output."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if any(term in q for term in ("list rooms", "what rooms", "hubitat rooms")):
            return await self._rooms()
        if "rule" in q and any(
            term in q for term in ("list", "show", "active", "automation")
        ):
            return await self._rules()
        if any(
            term in q
            for term in ("need attention", "needs attention", "attention", "problems")
        ):
            return await self._attention()
        return await super().answer(query)

    async def _execute_catalog_tool(
        self,
        direct_tool: str,
        gateway_tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        arguments = arguments if isinstance(arguments, dict) else {}
        available = {tool.name for tool in await self.client.list_tools()}

        if direct_tool in available:
            return await self.client.call_tool(direct_tool, arguments)

        if gateway_tool not in available:
            raise MCPError(
                f"The MCP server exposes neither {direct_tool} nor {gateway_tool}."
            )

        result = await self.client.call_tool(
            gateway_tool,
            {"tool": direct_tool, "args": arguments},
        )
        data = result.data
        if isinstance(data, dict) and str(data.get("mode") or "").lower() == "catalog":
            raise MCPError(
                f"{gateway_tool} returned its catalogue instead of executing "
                f"{direct_tool}."
            )
        return result

    @staticmethod
    def _decorate(
        response: dict[str, Any],
        display: dict[str, Any],
        result: MCPToolResult | None = None,
    ) -> dict[str, Any]:
        response["display"] = display
        if result is not None:
            response["technical"] = safe_debug(result.data)
        return response

    async def _hub_info(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")
        message, display = present_hub_info(result.data)
        return self._decorate(
            self._response(message, "fallback-hub-info", True, result),
            display,
            result,
        )

    async def _rooms(self) -> dict[str, Any]:
        result = await self._execute_catalog_tool(
            "hub_list_rooms",
            "hub_read_rooms",
            {},
        )
        if result.is_error:
            raise MCPError(result.text or "Room lookup failed")
        message, display = present_rooms(result.data)
        return self._decorate(
            self._response(message, "fallback-rooms", True, result),
            display,
            result,
        )

    async def _rules(self) -> dict[str, Any]:
        result = await self._execute_catalog_tool(
            "hub_list_rules",
            "hub_read_rules",
            {},
        )
        if result.is_error:
            raise MCPError(result.text or "Rule lookup failed")
        message, display = present_rules(result.data)
        return self._decorate(
            self._response(message, "fallback-rules", True, result),
            display,
            result,
        )

    async def _low_batteries(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        rows: list[tuple[str, float]] = []
        for item in self._device_rows(result.data):
            attrs = _attributes(item)
            battery = item.get("battery", attrs.get("battery"))
            number = _number(battery)
            if number is not None and number <= 20:
                rows.append((_label(item) or f"Device {_device_id(item)}", number))
        rows.sort(key=lambda row: (row[1], row[0].lower()))

        if not rows:
            message = "No devices at or below 20% were found in the MCP device data."
        else:
            message = "Low battery devices:\n" + "\n".join(
                f"- {name}: {value:g}%" for name, value in rows
            )

        display = display_payload(
            "batteries",
            "Low batteries",
            subtitle=(
                f"{len(rows)} device{'' if len(rows) == 1 else 's'} at or below 20%"
                if rows
                else "No batteries at or below 20%"
            ),
            items=[
                {
                    "icon": "🪫",
                    "title": name,
                    "value": f"{value:g}%",
                    "subtitle": "Replace soon" if value <= 15 else "Low battery",
                    "tone": "danger" if value <= 15 else "warning",
                }
                for name, value in rows
            ],
        )
        return self._decorate(
            self._response(message, "fallback-low-batteries", True, result),
            display,
            result,
        )

    async def _list_on_devices(self, kind: str) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        names: list[str] = []
        for item in self._device_rows(result.data):
            text = _normalise(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("category", "type", "deviceType", "label", "name")
                )
            )
            if kind == "light" and not any(
                term in text for term in ("light", "bulb", "lamp")
            ):
                continue
            attrs = _attributes(item)
            state = _normalise(item.get("switch", attrs.get("switch")))
            if state == "on":
                names.append(_label(item) or str(_device_id(item)))

        label = "Lights" if kind == "light" else "Switches"
        if names:
            message = (
                f"{len(names)} {kind}{'' if len(names) == 1 else 's'} on: "
                + ", ".join(names)
                + "."
            )
        else:
            message = f"No {kind}s are currently reporting as on."

        display = display_payload(
            f"{kind}s-on",
            f"{label} on",
            subtitle=f"{len(names)} currently on",
            items=[
                {
                    "icon": "💡" if kind == "light" else "🔌",
                    "title": name,
                    "value": "On",
                    "tone": "success",
                }
                for name in names
            ],
        )
        return self._decorate(
            self._response(message, f"fallback-{kind}s-on", True, result),
            display,
            result,
        )

    async def _find_weather(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True, label_filter="weather")
        if result.is_error:
            raise MCPError(result.text or "Weather lookup failed")
        message, display = present_weather(result.data)
        return self._decorate(
            self._response(message, "fallback-weather", True, result),
            display,
            result,
        )

    async def _attention(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        problems: list[dict[str, Any]] = []

        for item in self._device_rows(result.data):
            attrs = _attributes(item)
            label = _label(item) or str(_device_id(item))
            battery = _number(item.get("battery", attrs.get("battery")))
            if battery is not None and battery <= 20:
                problems.append(
                    {
                        "icon": "🪫",
                        "title": label,
                        "value": f"{battery:g}%",
                        "subtitle": "Low battery",
                        "tone": "danger" if battery <= 15 else "warning",
                        "priority": battery,
                    }
                )

            health = _normalise(
                item.get(
                    "healthStatus",
                    item.get(
                        "status",
                        attrs.get("healthStatus", attrs.get("status")),
                    ),
                )
            )
            if health in {
                "offline",
                "unavailable",
                "not present",
                "dead",
                "failed",
            }:
                problems.append(
                    {
                        "icon": "📡",
                        "title": label,
                        "value": "Offline",
                        "subtitle": "Device is not responding",
                        "tone": "danger",
                        "priority": -1,
                    }
                )

        problems.sort(
            key=lambda item: (item.get("priority", 100), item["title"].lower())
        )
        if problems:
            message = "Devices needing attention:\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in problems
            )
        else:
            message = "No low-battery or offline devices were found."

        display = display_payload(
            "attention",
            "Needs attention",
            subtitle=f"{len(problems)} issue{'' if len(problems) == 1 else 's'} found",
            items=[
                {key: value for key, value in item.items() if key != "priority"}
                for item in problems
            ],
        )
        return self._decorate(
            self._response(message, "fallback-attention", True, result),
            display,
            result,
        )

    async def _home_status(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True)
        rows = self._device_rows(result.data)

        lights_on: list[str] = []
        switches_on: list[str] = []
        motion_active: list[str] = []
        low_batteries: list[tuple[str, float]] = []

        for item in rows:
            attrs = _attributes(item)
            label = _label(item) or str(_device_id(item))
            text = _normalise(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("category", "type", "deviceType", "label", "name")
                )
            )
            switch = _normalise(item.get("switch", attrs.get("switch")))
            if switch == "on":
                if any(term in text for term in ("light", "bulb", "lamp")):
                    lights_on.append(label)
                else:
                    switches_on.append(label)

            motion = _normalise(item.get("motion", attrs.get("motion")))
            if motion == "active":
                motion_active.append(label)

            battery_number = _number(item.get("battery", attrs.get("battery")))
            if battery_number is not None and battery_number <= 20:
                low_batteries.append((label, battery_number))

        low_batteries.sort(key=lambda row: (row[1], row[0].lower()))
        lines = [
            (
                f"{len(lights_on)} light{'' if len(lights_on) == 1 else 's'} on"
                + (": " + ", ".join(lights_on) if lights_on else ".")
            ),
            (
                f"{len(switches_on)} other switch"
                f"{'' if len(switches_on) == 1 else 'es'} on"
                + (": " + ", ".join(switches_on) if switches_on else ".")
            ),
            (
                f"Motion active on {len(motion_active)} device"
                f"{'' if len(motion_active) == 1 else 's'}"
                + (": " + ", ".join(motion_active) if motion_active else ".")
            ),
            (
                "Low batteries: "
                + (
                    ", ".join(
                        f"{name} {value:g}%" for name, value in low_batteries
                    )
                    if low_batteries
                    else "none at or below 20%"
                )
                + "."
            ),
        ]

        metrics = [
            {"label": "Lights on", "value": str(len(lights_on)), "icon": "💡"},
            {
                "label": "Switches on",
                "value": str(len(switches_on)),
                "icon": "🔌",
            },
            {
                "label": "Motion active",
                "value": str(len(motion_active)),
                "icon": "🏃",
            },
            {
                "label": "Low batteries",
                "value": str(len(low_batteries)),
                "icon": "🪫",
            },
        ]
        items = []
        for name in lights_on:
            items.append(
                {"icon": "💡", "title": name, "value": "On", "tone": "success"}
            )
        for name in motion_active:
            items.append(
                {
                    "icon": "🏃",
                    "title": name,
                    "value": "Motion",
                    "tone": "warning",
                }
            )
        for name, value in low_batteries:
            items.append(
                {
                    "icon": "🪫",
                    "title": name,
                    "value": f"{value:g}%",
                    "tone": "danger" if value <= 15 else "warning",
                }
            )

        display = display_payload(
            "home-status",
            "What's happening",
            subtitle=f"{len(rows)} MCP devices checked",
            metrics=metrics,
            items=items,
            note="Only active or attention items are listed.",
        )
        return self._decorate(
            self._response(
                "\n".join(lines),
                "fallback-fast-home-status",
                True,
                result,
            ),
            display,
            result,
        )
