from __future__ import annotations

import json
from typing import Any

from fast_fallback_room_inventory import FastFallbackRouter as RoomInventoryRouter
from hub_cpu_probe import probe_hub_cpu
from hub_metric_formatting import format_database_size
from mcp_client import MCPError
from presenter import first_mapping, first_value, present_hub_info


class FastFallbackRouter(RoomInventoryRouter):
    """Release-level corrections for Hubitat metrics and room inventory."""

    async def _hub_info(self) -> dict[str, Any]:
        result = await self.client.call_tool("hub_get_info", {})
        if result.is_error:
            raise MCPError(result.text or "hub_get_info failed")

        data = first_mapping(result.data)
        message, display = present_hub_info(result.data)
        local_ip = first_value(data, "localIP", "ip", "ipAddress")
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

        database_size = format_database_size(
            first_value(data, "databaseSizeMB", "databaseSizeKB", "databaseSizeKb")
        )
        metrics = list(display.get("metrics") or [])
        if cpu.get("available"):
            cpu_metric = {
                "label": "CPU load",
                "value": str(cpu.get("value") or "—"),
                "icon": "🧠",
            }
            insert_at = next(
                (
                    index + 1
                    for index, item in enumerate(metrics)
                    if str(item.get("label") or "").lower() == "firmware"
                ),
                1,
            )
            metrics.insert(insert_at, cpu_metric)
            message += f"\nHub CPU load is {cpu.get('value')}."
        else:
            metrics.append(
                {
                    "label": "CPU load",
                    "value": "Unavailable",
                    "icon": "🧠",
                }
            )

        display["metrics"] = metrics
        display["note"] = f"Database: {database_size}" if database_size else None
        if database_size:
            message += f"\nDatabase size is {database_size}."

        response = self._response(message, "fallback-hub-info", True, result)
        response["display"] = display
        response["technical"] = json.dumps(
            {"hub_info": data, "cpu_probe": cpu},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        return response

    async def _hub_resources(self) -> dict[str, Any]:
        response = await super()._hub_resources()
        technical = response.get("technical")
        try:
            details = json.loads(technical) if isinstance(technical, str) else {}
        except Exception:
            details = {}
        hub_info = details.get("hub_info") if isinstance(details, dict) else {}
        if not isinstance(hub_info, dict):
            hub_info = {}

        database_size = format_database_size(
            first_value(hub_info, "databaseSizeMB", "databaseSizeKB", "databaseSizeKb")
        )
        if not database_size:
            return response

        display = response.get("display") if isinstance(response.get("display"), dict) else {}
        for metric in display.get("metrics") or []:
            if str(metric.get("label") or "").lower() == "database":
                metric["value"] = database_size

        lines = [
            line
            for line in str(response.get("message") or "").splitlines()
            if not line.lower().startswith("database size is ")
        ]
        lines.append(f"Database size is {database_size}.")
        response["message"] = "\n".join(lines)
        return response


__all__ = ["FastFallbackRouter"]
