"""Authoritative Hub Information Driver snapshots.

The service owns Hub Info device discovery, refresh commands, bounded polling,
identity/state reconciliation, units, and the structured result contract. It
does not decide when the tool is visible, whether its result supports a live
claim, or how the final answer is presented.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from device_state_summary import device_attributes
from device_target_resolver import normalized_name
from mcp_client import HubitatMCPClient, MCPToolResult
from tool_executor import ToolExecutor
from tool_registry import LOCAL_HUB_INFO_TOOL


logger = logging.getLogger("HomeBrainOS.HubInfoService")


class HubInfoService:
    """Read one refreshed Hub Information Driver snapshot."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.mcp = mcp_client
        self._sleep = sleep

    @staticmethod
    def device_attributes(device: dict[str, Any]) -> dict[str, Any]:
        return device_attributes(device)

    @staticmethod
    def device_attribute_units(device: dict[str, Any]) -> dict[str, str]:
        attributes = (
            device.get("attributes")
            or device.get("currentStates")
            or device.get("states")
            or {}
        )
        if not isinstance(attributes, list):
            return {}
        return {
            str(item.get("name")): str(item.get("unit")).strip()
            for item in attributes
            if isinstance(item, dict)
            and item.get("name")
            and item.get("unit") not in {None, ""}
        }

    @staticmethod
    def inferred_memory_unit(value: Any) -> str | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number >= 100_000:
            return "KB"
        if number >= 16:
            return "MB"
        return "GB"

    @staticmethod
    def hub_info_device(
        devices: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        matches = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            label = str(
                device.get("label")
                or device.get("displayName")
                or device.get("name")
                or ""
            )
            if normalized_name(label).startswith("hubinfo"):
                matches.append(device)
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def find_device_record(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        if (
            value.get("id") is not None
            or value.get("deviceId") is not None
        ) and any(
            key in value
            for key in (
                "attributes",
                "currentStates",
                "states",
                "capabilities",
                "commands",
                "label",
                "displayName",
            )
        ):
            return value
        for key in ("device", "result", "data", "output", "content"):
            if key in value:
                candidate = cls.find_device_record(value[key])
                if candidate is not None:
                    return candidate
        return None

    @classmethod
    def merge_device_identity(
        cls,
        live_devices: list[dict[str, Any]],
        identity_devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        identities = {
            str(device.get("id") or device.get("deviceId")): device
            for device in identity_devices
            if isinstance(device, dict)
            and (device.get("id") is not None or device.get("deviceId") is not None)
        }
        merged: list[dict[str, Any]] = []
        for live in live_devices:
            device_id = str(live.get("id") or live.get("deviceId") or "")
            identity = identities.get(device_id, {})
            identity_attributes = cls.device_attributes(identity)
            live_attributes = cls.device_attributes(live)
            device = {**identity, **live}
            if identity_attributes or live_attributes:
                device["attributes"] = {
                    **identity_attributes,
                    **live_attributes,
                }
            merged.append(device)
        return merged

    @staticmethod
    def _error(
        arguments: dict[str, Any],
        text: str,
        error: str,
    ) -> MCPToolResult:
        return MCPToolResult(
            LOCAL_HUB_INFO_TOOL,
            arguments,
            {},
            text,
            {"success": False, "error": error},
            is_error=True,
        )

    async def snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Refresh and return the requested firmware/resource scope."""

        scope = str(arguments.get("scope") or "").strip().lower()
        if scope not in {"firmware", "resources", "full"}:
            return self._error(
                arguments,
                "Invalid Hub Info scope",
                "scope must be firmware, resources, or full",
            )
        try:
            cached = await self.mcp.get_cached_devices()
        except Exception as exc:
            cached = []
            logger.warning("Could not load Hub Info identity manifest: %s", exc)
        hub_device = self.hub_info_device(list(cached or []))
        if hub_device is None:
            source = await self.mcp.call_tool(
                "hub_read_devices",
                {"tool": "hub_list_devices", "args": {"labelFilter": "Hub Info"}},
            )
            hub_device = self.hub_info_device([
                item
                for item in (HubitatMCPClient._find_device_list(source.data) or [])
                if isinstance(item, dict)
            ])
        if hub_device is None:
            return self._error(
                arguments,
                "Hub Info device not found",
                (
                    "A unique Hub Info device could not be found. Install or "
                    "rename the Hub Information Driver device."
                ),
            )
        device_id = str(hub_device.get("id") or hub_device.get("deviceId") or "")
        label = str(
            hub_device.get("label")
            or hub_device.get("displayName")
            or hub_device.get("name")
            or "Hub Info"
        )
        if not device_id:
            return self._error(
                arguments,
                "Hub Info device has no device ID",
                "Hub Info device has no device ID",
            )
        cached_attributes = self.device_attributes(hub_device)
        baseline_firmware = (
            cached_attributes.get("hubUpdateStatus"),
            cached_attributes.get("hubUpdateVersion"),
        )
        commands = []
        if scope in {"resources", "full"}:
            commands.append("refresh")
        if scope in {"firmware", "full"}:
            commands.append("updateCheck")
        for command in commands:
            result = await self.mcp.call_tool(
                "hub_manage_devices",
                {
                    "tool": "hub_call_device_command",
                    "args": {"deviceId": device_id, "command": command},
                },
            )
            if not ToolExecutor.succeeded(result):
                return self._error(
                    arguments,
                    result.text,
                    (
                        f"Hub Info command {command!r} failed: "
                        f"{result.text or 'unknown error'}"
                    ),
                )
        live_device: dict[str, Any] | None = None
        poll_attempts = 10 if scope in {"firmware", "full"} else 6
        for attempt in range(poll_attempts):
            source = await self.mcp.call_tool(
                "hub_read_devices",
                {
                    "tool": "hub_get_device",
                    "args": {"deviceId": device_id},
                },
            )
            candidates = [
                item
                for item in (HubitatMCPClient._find_device_list(source.data) or [])
                if isinstance(item, dict)
            ]
            if not candidates:
                candidate = self.find_device_record(source.data)
                if candidate is not None:
                    candidates = [candidate]
            live_device = self.hub_info_device(candidates)
            if live_device is None and len(candidates) == 1:
                live_device = candidates[0]
            if live_device is not None:
                live_device = self.merge_device_identity(
                    [live_device],
                    [hub_device],
                )[0]
                attributes = self.device_attributes(live_device)
                refreshed_firmware = (
                    attributes.get("hubUpdateStatus"),
                    attributes.get("hubUpdateVersion"),
                )
                firmware_settled = (
                    refreshed_firmware != baseline_firmware
                    or attempt == poll_attempts - 1
                )
                if (
                    scope not in {"firmware", "full"}
                    or (
                        all(value is not None for value in refreshed_firmware)
                        and firmware_settled
                    )
                ):
                    break
            if attempt < poll_attempts - 1:
                await self._sleep(0.5)
        if live_device is None:
            return self._error(
                arguments,
                "Hub Info attributes unavailable after refresh",
                "Hub Info attributes were unavailable after refresh",
            )
        values = {**live_device, **self.device_attributes(live_device)}
        attribute_units = self.device_attribute_units(live_device)

        def value(*names: str) -> Any:
            return next(
                (
                    values.get(name)
                    for name in names
                    if values.get(name) is not None and values.get(name) != ""
                ),
                None,
            )

        installed = value("firmwareVersionString", "firmwareVersion")
        available = value("hubUpdateVersion")
        update_status = value("hubUpdateStatus")
        update_available = (
            "available" in str(update_status or "").casefold()
            or (bool(installed) and bool(available) and str(installed) != str(available))
        )
        free_memory = value("freeMemory")
        temperature = value("temperatureC", "temperature", "temperatureF")
        data = {
            "success": True,
            "source": label,
            "device_id": device_id,
            "scope": scope,
            "installed_firmware": installed,
            "update_status": update_status,
            "available_firmware": available,
            "update_available": update_available,
            "hub_model": value("hubModel"),
            "cpu_5_min": value("cpu5Min"),
            "cpu_percent": value("cpuPct"),
            "cpu_15_min": value("cpu15Min"),
            "cpu_15_percent": value("cpu15Pct"),
            "free_memory": free_memory,
            "free_memory_unit": (
                attribute_units.get("freeMemory")
                or self.inferred_memory_unit(free_memory)
            ),
            "free_memory_15_min": value("freeMem15"),
            "jvm_free": value("jvmFree"),
            "jvm_size": value("jvmSize"),
            "java_direct": value("javaDirect"),
            "temperature": temperature,
            "temperature_unit": (
                attribute_units.get("temperatureC")
                or attribute_units.get("temperature")
                or ("°C" if temperature is not None else None)
            ),
            "uptime": value("formattedUptime", "uptime"),
            "database_size": value("dbSize"),
            "database_size_unit": attribute_units.get("dbSize") or "MB",
            "ip_address": value("localIP", "ipAddress"),
            "zigbee_healthy": value("zbHealthy"),
            "zwave_healthy": value("zwHealthy"),
            "hub_alerts": value("hubAlerts"),
            "matter_status": value("matterStatus"),
            "last_poll": value("lastPollTime"),
        }
        return MCPToolResult(
            LOCAL_HUB_INFO_TOOL,
            arguments,
            {},
            json.dumps(data),
            data,
        )


__all__ = ["HubInfoService"]
