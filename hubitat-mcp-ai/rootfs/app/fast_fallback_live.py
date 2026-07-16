from __future__ import annotations

from typing import Any

from fast_fallback_weather import FastFallbackRouter as WeatherFastFallbackRouter
from fallback_router import _device_id, _label, _normalise
from mcp_client import MCPError, MCPToolResult
from presenter import display_payload


def live_attributes(item: dict[str, Any]) -> dict[str, Any]:
    """Merge Hubitat summary currentStates and detailed attribute lists."""
    merged: dict[str, Any] = {}

    for key in ("currentStates", "state", "states", "attributes"):
        value = item.get(key)
        if isinstance(value, dict):
            merged.update(value)
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("attribute") or entry.get("key")
            if not name:
                continue
            current = entry.get("currentValue")
            if current in (None, ""):
                current = entry.get("value")
            if current in (None, ""):
                current = entry.get("currentState")
            merged[str(name)] = current

    for key in (
        "switch",
        "level",
        "motion",
        "contact",
        "temperature",
        "humidity",
        "battery",
        "presence",
        "healthStatus",
        "status",
    ):
        if item.get(key) not in (None, ""):
            merged[key] = item[key]

    return merged


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return None


def _looks_like_light(item: dict[str, Any]) -> bool:
    text = _normalise(
        " ".join(
            str(item.get(key) or "")
            for key in (
                "label",
                "name",
                "displayName",
                "category",
                "type",
                "deviceType",
            )
        )
    )
    return any(
        term in text
        for term in (
            "light",
            "lamp",
            "bulb",
            "dimmer",
            "rgb",
            "colour",
            "color",
        )
    )


class FastFallbackRouter(WeatherFastFallbackRouter):
    """Fast MCP routes using Hubitat's authoritative summary currentStates."""

    async def _live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        arguments: dict[str, Any] = {
            "detailed": False,
            "format": "summary",
            "fields": [
                "id",
                "name",
                "label",
                "room",
                "currentStates",
            ],
        }
        if capability_filter:
            arguments["capabilityFilter"] = capability_filter

        result = await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            arguments,
        )
        if result.is_error:
            raise MCPError(result.text or "Live device-state lookup failed")
        return result

    async def _list_on_devices(self, kind: str) -> dict[str, Any]:
        result = await self._live_devices("Switch")
        names: list[str] = []
        switch_rows = 0
        on_rows = 0

        for item in self._device_rows(result.data):
            attrs = live_attributes(item)
            state = _normalise(attrs.get("switch"))
            if state not in {"on", "off"}:
                continue
            switch_rows += 1
            if state != "on":
                continue
            on_rows += 1

            is_light = _looks_like_light(item)
            if kind == "light" and not is_light:
                continue
            if kind == "switch" and is_light:
                continue
            names.append(_label(item) or str(_device_id(item)))

        names = sorted(dict.fromkeys(names), key=str.lower)
        label = "Lights" if kind == "light" else "Switches"
        if names:
            message = (
                f"{len(names)} {kind}{'' if len(names) == 1 else 's'} on: "
                + ", ".join(names)
                + "."
            )
        elif switch_rows == 0:
            message = (
                "The MCP device response did not include any live switch states. "
                "Check that the light devices are selected in MCP Rule Server."
            )
        else:
            message = f"No {kind}s are currently reporting as on."

        display = display_payload(
            f"{kind}s-on",
            f"{label} on",
            subtitle=f"{len(names)} currently on",
            metrics=[
                {"label": "Matching devices", "value": str(len(names)), "icon": "💡" if kind == "light" else "🔌"},
                {"label": "Switch states read", "value": str(switch_rows), "icon": "📡"},
                {"label": "All switches on", "value": str(on_rows), "icon": "⚡"},
            ],
            items=[
                {
                    "icon": "💡" if kind == "light" else "🔌",
                    "title": name,
                    "value": "On",
                    "tone": "success",
                }
                for name in names
            ],
            note=(
                "Live values come from Hubitat hub_list_devices currentStates."
                if switch_rows
                else "No currentStates were returned for Switch-capability devices."
            ),
        )
        return self._decorate(
            self._response(message, f"fallback-{kind}s-on", True, result),
            display,
            result,
        )

    async def _low_batteries(self) -> dict[str, Any]:
        result = await self._live_devices("Battery")
        rows: list[tuple[str, float]] = []
        for item in self._device_rows(result.data):
            battery = _number(live_attributes(item).get("battery"))
            if battery is not None and battery <= 20:
                rows.append((_label(item) or str(_device_id(item)), battery))
        rows.sort(key=lambda row: (row[1], row[0].lower()))

        message = (
            "Low battery devices:\n"
            + "\n".join(f"- {name}: {value:g}%" for name, value in rows)
            if rows
            else "No devices at or below 20% were found in the live MCP states."
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

    async def _home_status(self) -> dict[str, Any]:
        result = await self._live_devices()
        lights_on: list[str] = []
        switches_on: list[str] = []
        motion_active: list[str] = []
        low_batteries: list[tuple[str, float]] = []

        for item in self._device_rows(result.data):
            attrs = live_attributes(item)
            label = _label(item) or str(_device_id(item))
            if _normalise(attrs.get("switch")) == "on":
                if _looks_like_light(item):
                    lights_on.append(label)
                else:
                    switches_on.append(label)
            if _normalise(attrs.get("motion")) == "active":
                motion_active.append(label)
            battery = _number(attrs.get("battery"))
            if battery is not None and battery <= 20:
                low_batteries.append((label, battery))

        lights_on = sorted(dict.fromkeys(lights_on), key=str.lower)
        switches_on = sorted(dict.fromkeys(switches_on), key=str.lower)
        motion_active = sorted(dict.fromkeys(motion_active), key=str.lower)
        low_batteries.sort(key=lambda row: (row[1], row[0].lower()))

        lines = [
            f"{len(lights_on)} lights on" + (": " + ", ".join(lights_on) if lights_on else "."),
            f"{len(switches_on)} other switches on" + (": " + ", ".join(switches_on) if switches_on else "."),
            f"Motion active on {len(motion_active)} devices" + (": " + ", ".join(motion_active) if motion_active else "."),
            "Low batteries: "
            + (", ".join(f"{name} {value:g}%" for name, value in low_batteries) if low_batteries else "none at or below 20%")
            + ".",
        ]
        display = display_payload(
            "home-status",
            "What's happening",
            subtitle="Live Hubitat MCP device states",
            metrics=[
                {"label": "Lights on", "value": str(len(lights_on)), "icon": "💡"},
                {"label": "Switches on", "value": str(len(switches_on)), "icon": "🔌"},
                {"label": "Motion active", "value": str(len(motion_active)), "icon": "🏃"},
                {"label": "Low batteries", "value": str(len(low_batteries)), "icon": "🪫"},
            ],
            items=[
                *[
                    {"icon": "💡", "title": name, "value": "On", "tone": "success"}
                    for name in lights_on
                ],
                *[
                    {"icon": "🔌", "title": name, "value": "On", "tone": "success"}
                    for name in switches_on
                ],
                *[
                    {"icon": "🏃", "title": name, "value": "Active"}
                    for name in motion_active
                ],
                *[
                    {
                        "icon": "🪫",
                        "title": name,
                        "value": f"{value:g}%",
                        "tone": "danger" if value <= 15 else "warning",
                    }
                    for name, value in low_batteries
                ],
            ],
        )
        return self._decorate(
            self._response("\n".join(lines), "fallback-home-status", True, result),
            display,
            result,
        )
