from __future__ import annotations

import asyncio
from typing import Any

from fallback_router import _device_id, _label, _normalise
from fast_fallback_groups import FastFallbackRouter as GroupFastFallbackRouter
from fast_fallback_live import live_attributes
from mcp_client import MCPError
from presenter import (
    compact_number,
    display_payload,
    first_mapping,
    first_value,
    format_memory_kb,
)


_DEVICE_HEALTH_TERMS = (
    "device health",
    "offline or stale",
    "offline and stale",
    "offline devices",
    "stale devices",
    "devices offline",
    "devices stale",
    "not responding",
    "unresponsive devices",
)

_HUB_RESOURCE_TERMS = (
    "hub resources",
    "hub resource",
    "hub cpu",
    "cpu load",
    "processor load",
    "free memory",
    "hub memory",
    "hub temperature",
    "database size",
    "hub uptime",
)


class FastFallbackRouter(GroupFastFallbackRouter):
    """Group-aware fallback with focused device-health and hub-resource routes."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if any(term in q for term in _HUB_RESOURCE_TERMS):
            return await self._hub_resources()
        if any(term in q for term in _DEVICE_HEALTH_TERMS):
            return await self._device_health()
        return await super().answer(query)

    async def _hub_resources(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        data = first_mapping(result.data)
        model = first_value(data, "name", "hubName", "model") or "Hubitat hub"
        firmware = first_value(data, "firmwareVersion", "currentVersion")
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
        cpu_raw = first_value(
            data,
            "cpuLoad",
            "cpuLoadPercent",
            "cpuPercent",
            "processorLoad",
        )
        cpu = compact_number(cpu_raw, "%") if cpu_raw not in (None, "") else None

        lines: list[str] = []
        if cpu:
            lines.append(f"Hub CPU load is {cpu}.")
        else:
            lines.append(
                "The Hubitat MCP Rule Server does not expose CPU load through hub_get_info."
            )
        if free_memory:
            lines.append(f"Hub free memory is {free_memory}.")
        if temperature:
            lines.append(f"Internal temperature is {temperature}.")
        if database_size:
            lines.append(f"Database size is {database_size}.")
        if uptime:
            lines.append(f"Uptime is {uptime}.")

        metrics = [
            {
                "label": "CPU load",
                "value": cpu or "Not exposed",
                "icon": "🧠",
            }
        ]
        for label, value, icon in (
            ("Free memory", free_memory, "💾"),
            ("Temperature", temperature, "🌡️"),
            ("Database", database_size, "🗄️"),
            ("Uptime", uptime, "⏱️"),
        ):
            if value not in (None, ""):
                metrics.append({"label": label, "value": str(value), "icon": icon})

        subtitle = " · ".join(
            value
            for value in (
                str(model),
                f"Firmware {firmware}" if firmware else None,
            )
            if value
        )
        display = display_payload(
            "hub-resources",
            "Hub resources",
            subtitle=subtitle,
            metrics=metrics,
            note=(
                "Kingpanther MCP currently exposes free memory, temperature, database size "
                "and uptime, but not the Hubitat CPU percentage."
                if not cpu
                else "Live values were read from Kingpanther's hub_get_info tool."
            ),
        )
        return self._decorate(
            self._response(
                "\n".join(lines),
                "fallback-hub-resources",
                True,
                result,
            ),
            display,
            result,
        )

    async def _device_health(self) -> dict[str, Any]:
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

        outcomes = await asyncio.gather(
            self._safe_result("stale", stale_call),
            self._safe_result("health", health_call),
        )
        results = {name: result for name, result, _error in outcomes}
        errors = {name: error for name, _result, error in outcomes if error}

        rows: dict[str, dict[str, Any]] = {}

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
                rows[_normalise(label)] = {
                    "icon": "📡",
                    "title": label,
                    "value": "Offline",
                    "subtitle": "Hubitat Health Check reports this device is not responding",
                    "tone": "danger",
                    "kind": "offline",
                }

        stale_result = results.get("stale")
        if stale_result is not None:
            for device in self._device_rows(stale_result.data):
                if device.get("disabled") is True:
                    continue
                label = _label(device) or f"Device {_device_id(device)}"
                key = _normalise(label)
                if key in rows:
                    continue
                last_activity = device.get("lastActivity") or "No activity recorded"
                rows[key] = {
                    "icon": "🕒",
                    "title": label,
                    "value": f"Stale {self.attention_stale_hours:g}h+",
                    "subtitle": f"Last activity: {last_activity}",
                    "tone": "warning",
                    "kind": "stale",
                }

        items = sorted(
            rows.values(),
            key=lambda item: (
                0 if item["kind"] == "offline" else 1,
                item["title"].lower(),
            ),
        )
        offline_count = sum(item["kind"] == "offline" for item in items)
        stale_count = sum(item["kind"] == "stale" for item in items)

        if items:
            message = "Devices that are offline or stale:\n" + "\n".join(
                f"- {item['title']}: {item['value']} ({item['subtitle']})"
                for item in items
            )
        elif errors:
            message = (
                "The device-health scan was incomplete, so I cannot confirm that all devices "
                "are healthy. Failed checks: " + ", ".join(sorted(errors)) + "."
            )
        else:
            message = (
                f"No offline devices or devices stale for {self.attention_stale_hours:g} hours "
                "or longer were found."
            )

        display_items = [
            {key: value for key, value in item.items() if key != "kind"}
            for item in items
        ]
        if errors:
            display_items.append(
                {
                    "icon": "⚠️",
                    "title": "Device-health scan incomplete",
                    "value": "Check failed",
                    "subtitle": "Could not read: " + ", ".join(sorted(errors)),
                    "tone": "warning",
                }
            )

        display = display_payload(
            "device-health",
            "Device health",
            subtitle=(
                f"{len(items)} device{'' if len(items) == 1 else 's'} need attention"
                if items
                else "No offline or stale devices found"
                if not errors
                else "Scan incomplete"
            ),
            metrics=[
                {"label": "Offline", "value": str(offline_count), "icon": "📡"},
                {"label": "Stale", "value": str(stale_count), "icon": "🕒"},
                {"label": "Threshold", "value": f"{self.attention_stale_hours:g}h", "icon": "⏱️"},
            ],
            items=display_items,
            note=(
                "Disabled devices are excluded from the stale-device list."
                + (f" Incomplete checks: {', '.join(sorted(errors))}." if errors else "")
            ),
        )
        technical_result = next(
            (result for result in results.values() if result is not None),
            None,
        )
        return self._decorate(
            self._response(message, "fallback-device-health", not errors, technical_result),
            display,
            technical_result,
        )
