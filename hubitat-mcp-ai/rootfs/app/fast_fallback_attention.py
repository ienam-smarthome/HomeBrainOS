from __future__ import annotations

import asyncio
from typing import Any, Awaitable

from fallback_router import _device_id, _label, _normalise
from fast_fallback_live import live_attributes
from fast_fallback_verified import FastFallbackRouter as VerifiedFastFallbackRouter
from mcp_client import MCPToolResult
from presenter import display_payload, first_mapping
from system_presenter_v2 import present_hub_info_v2


class FastFallbackRouter(VerifiedFastFallbackRouter):
    """Verified MCP fallback with one authoritative attention scan."""

    def __init__(self, client: Any, attention_stale_hours: float = 48) -> None:
        super().__init__(client)
        self.attention_stale_hours = max(1.0, float(attention_stale_hours))

    async def _safe_result(
        self,
        name: str,
        operation: Awaitable[MCPToolResult],
    ) -> tuple[str, MCPToolResult | None, str | None]:
        try:
            result = await operation
            if result.is_error:
                return name, result, result.text or f"{name} returned an error"
            return name, result, None
        except Exception as exc:
            return name, None, str(exc)

    async def _attention(self) -> dict[str, Any]:
        battery_call = self._live_devices("Battery")
        stale_call = self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "filter": f"stale:{self.attention_stale_hours:g}",
                "fields": [
                    "id",
                    "name",
                    "label",
                    "room",
                    "disabled",
                    "lastActivity",
                    "currentStates",
                ],
            },
        )
        health_call = self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": True,
                "format": "detailed",
                "capabilityFilter": "Health Check",
                "fields": ["id", "name", "label", "room", "attributes"],
            },
        )
        hub_call = self.client.call_tool(
            "hub_get_info",
            {"includeAppUpdate": True, "includeHealthAlerts": True},
        )

        outcomes = await asyncio.gather(
            self._safe_result("battery", battery_call),
            self._safe_result("stale", stale_call),
            self._safe_result("health", health_call),
            self._safe_result("hub", hub_call),
        )
        results = {name: result for name, result, _error in outcomes}
        errors = {name: error for name, _result, error in outcomes if error}

        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        counts = {
            "battery": 0,
            "device_health": 0,
            "hub": 0,
            "updates": 0,
        }

        def add_item(
            category: str,
            title: str,
            value: str,
            subtitle: str,
            *,
            icon: str,
            tone: str = "warning",
            priority: float = 50,
        ) -> None:
            key = (category, _normalise(title))
            if key in seen:
                return
            seen.add(key)
            items.append(
                {
                    "category": category,
                    "icon": icon,
                    "title": title,
                    "value": value,
                    "subtitle": subtitle,
                    "tone": tone,
                    "priority": priority,
                }
            )
            counts[category] += 1

        battery_result = results.get("battery")
        if battery_result is not None:
            for device in self._device_rows(battery_result.data):
                battery = self._number_value(live_attributes(device).get("battery"))
                if battery is None or battery > 20:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                add_item(
                    "battery",
                    label,
                    f"{battery:g}%",
                    "Replace soon" if battery <= 15 else "Low battery",
                    icon="🪫",
                    tone="danger" if battery <= 15 else "warning",
                    priority=battery,
                )

        offline_labels: set[str] = set()
        health_result = results.get("health")
        if health_result is not None:
            for device in self._device_rows(health_result.data):
                attrs = live_attributes(device)
                health = _normalise(
                    attrs.get("healthStatus")
                    or attrs.get("status")
                    or device.get("healthStatus")
                    or device.get("status")
                )
                if health not in {
                    "offline",
                    "unavailable",
                    "not present",
                    "dead",
                    "failed",
                }:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                offline_labels.add(_normalise(label))
                add_item(
                    "device_health",
                    label,
                    "Offline",
                    "Hubitat Health Check reports this device is not responding",
                    icon="📡",
                    tone="danger",
                    priority=0,
                )

        stale_result = results.get("stale")
        if stale_result is not None:
            for device in self._device_rows(stale_result.data):
                if device.get("disabled") is True:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                if _normalise(label) in offline_labels:
                    continue
                last_activity = device.get("lastActivity") or "No activity recorded"
                add_item(
                    "device_health",
                    label,
                    f"Stale {self.attention_stale_hours:g}h+",
                    f"Last activity: {last_activity}",
                    icon="🕒",
                    tone="warning",
                    priority=20,
                )

        hub_result = results.get("hub")
        if hub_result is not None:
            hub_data = first_mapping(hub_result.data)
            for field, title, icon in (
                ("memoryWarning", "Hub memory", "💾"),
                ("temperatureWarning", "Hub temperature", "🌡️"),
                ("databaseWarning", "Hub database", "🗄️"),
            ):
                warning = hub_data.get(field)
                if warning:
                    add_item(
                        "hub",
                        title,
                        "Warning",
                        str(warning),
                        icon=icon,
                        tone="danger",
                        priority=5,
                    )

            if hub_data.get("safeMode") is True:
                add_item(
                    "hub",
                    "Hub safe mode",
                    "On",
                    "The Hubitat hub is currently running in safe mode",
                    icon="🛡️",
                    tone="danger",
                    priority=1,
                )

            health_alerts = hub_data.get("healthAlerts")
            active_alerts = (
                health_alerts.get("active")
                if isinstance(health_alerts, dict)
                else []
            )
            if isinstance(active_alerts, list):
                for alert in active_alerts:
                    add_item(
                        "hub",
                        "Hub health alert",
                        str(alert),
                        "Hubitat reports an active platform health alert",
                        icon="⚠️",
                        tone="danger",
                        priority=4,
                    )

            _message, hub_display = present_hub_info_v2(hub_result.data)
            platform = hub_display.get("platform_update") or {}
            app_update = hub_display.get("app_update") or {}
            if platform.get("available") is True:
                add_item(
                    "updates",
                    "Hub platform update",
                    str(platform.get("available_version") or "Available"),
                    str(platform.get("message") or "A Hubitat platform update is available"),
                    icon="⬆️",
                    tone="warning",
                    priority=10,
                )
            elif platform.get("available") is None:
                add_item(
                    "updates",
                    "Hub update status",
                    "Unknown",
                    str(platform.get("message") or "Platform update status could not be read"),
                    icon="❔",
                    tone="warning",
                    priority=30,
                )

            if app_update.get("available") is True:
                add_item(
                    "updates",
                    "MCP Rule Server update",
                    str(app_update.get("latest") or "Available"),
                    str(app_update.get("message") or "An MCP Rule Server update is available"),
                    icon="📦",
                    tone="warning",
                    priority=11,
                )

        if errors:
            failed = ", ".join(sorted(errors))
            add_item(
                "hub",
                "Attention scan incomplete",
                "Check failed",
                f"Could not read: {failed}",
                icon="⚠️",
                tone="warning",
                priority=2,
            )

        items.sort(
            key=lambda item: (
                item.get("priority", 100),
                item.get("title", "").lower(),
            )
        )

        if items:
            message = "Items needing attention:\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in items
            )
        else:
            message = (
                "No low batteries, offline or stale devices, hub warnings, "
                "or available updates were found."
            )

        technical_result = next(
            (result for result in results.values() if result is not None),
            None,
        )
        display = display_payload(
            "attention",
            "Needs attention",
            subtitle=f"{len(items)} issue{'' if len(items) == 1 else 's'} found",
            metrics=[
                {"label": "Low batteries", "value": str(counts["battery"]), "icon": "🪫"},
                {"label": "Offline/stale", "value": str(counts["device_health"]), "icon": "📡"},
                {"label": "Hub warnings", "value": str(counts["hub"]), "icon": "⚠️"},
                {"label": "Updates", "value": str(counts["updates"]), "icon": "⬆️"},
            ],
            items=[
                {key: value for key, value in item.items() if key not in {"priority", "category"}}
                for item in items
            ],
            note=(
                f"Device staleness threshold: {self.attention_stale_hours:g} hours."
                + (f" Incomplete sources: {', '.join(sorted(errors))}." if errors else "")
            ),
        )
        return self._decorate(
            self._response(message, "fallback-attention", True, technical_result),
            display,
            technical_result,
        )

    @staticmethod
    def _number_value(value: Any) -> float | None:
        try:
            return float(str(value).replace("%", "").strip())
        except Exception:
            return None
