from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any

from device_state_summary import (
    active_lights,
    active_non_light_switches,
    active_room_summary,
)
from mcp_client import HubitatMCPClient, MCPToolResult


logger = logging.getLogger("HomeBrainOS.DeviceQuery")

DEVICE_FILTER_TOOL = "homebrain_filter_devices"
ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"


class DeviceQueryService:
    """Provide deterministic, exhaustive answers over live device state."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence

    @staticmethod
    def _tool_succeeded(result: MCPToolResult) -> bool:
        if result.is_error:
            return False
        data = result.data
        if isinstance(data, dict):
            if data.get("success") is False:
                return False
            if data.get("error") and data.get("success") is not True:
                return False
        return True

    @staticmethod
    def _normalized_attribute(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @classmethod
    def _attribute_matches(
        cls, actual: Any, operator: str, expected: Any
    ) -> bool:
        if operator == "exists":
            return actual is not None
        if operator == "not_exists":
            return actual is None
        if actual is None:
            return False
        if operator in {"lt", "lte", "gt", "gte"}:
            left, right = float(actual), float(expected)
            return {
                "lt": left < right,
                "lte": left <= right,
                "gt": left > right,
                "gte": left >= right,
            }[operator]
        if operator == "contains":
            return str(expected).casefold() in str(actual).casefold()
        try:
            left_value: Any = float(actual)
            right_value: Any = float(expected)
        except (TypeError, ValueError):
            left_value = str(actual).casefold()
            right_value = str(expected).casefold()
        return left_value == right_value if operator == "eq" else left_value != right_value

    @staticmethod
    def _device_attributes(device: dict[str, Any]) -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        raw = device.get("attributes")
        if isinstance(raw, dict):
            attributes.update(raw)
        elif isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("attribute")
                if name:
                    attributes[str(name)] = item.get("currentValue", item.get("value"))
        current_states = device.get("currentStates")
        if isinstance(current_states, dict):
            attributes.update(current_states)
        return attributes

    @staticmethod
    def _merge_device_identity(
        devices: list[dict[str, Any]],
        identities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        identity_by_id = {
            str(item.get("id") or item.get("deviceId")): item
            for item in identities
            if isinstance(item, dict) and (item.get("id") or item.get("deviceId"))
        }
        merged: list[dict[str, Any]] = []
        for device in devices:
            device_id = str(device.get("id") or device.get("deviceId") or "")
            identity = identity_by_id.get(device_id, {})
            combined = dict(identity)
            combined.update(device)
            if not combined.get("room") and identity.get("roomName"):
                combined["room"] = identity["roomName"]
            if not combined.get("roomName") and identity.get("room"):
                combined["roomName"] = identity["room"]
            merged.append(combined)
        return merged

    async def _live_devices(
        self,
        *,
        enrich_identity: bool,
    ) -> tuple[MCPToolResult, list[dict[str, Any]]]:
        source_arguments = {"tool": "hub_list_devices", "args": {}}
        started = time.monotonic()
        source = await self.mcp.call_tool("hub_read_devices", source_arguments)
        devices = [
            item
            for item in (HubitatMCPClient._find_device_list(source.data) or [])
            if isinstance(item, dict)
        ]
        if enrich_identity:
            try:
                identities = list(await self.mcp.get_cached_devices() or [])
            except Exception as exc:
                logger.warning("Could not enrich live device states with identity: %s", exc)
                identities = []
            devices = self._merge_device_identity(devices, identities)
        self._record_evidence(
            "hub_read_devices",
            source_arguments,
            success=self._tool_succeeded(source),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} source device records",
            evidence_kind="authoritative_state_snapshot",
        )
        return source, devices

    @staticmethod
    def _read_failure(
        tool_name: str,
        arguments: dict[str, Any],
        source: MCPToolResult,
    ) -> MCPToolResult:
        return MCPToolResult(
            tool_name,
            arguments,
            {},
            source.text,
            {"error": source.text or "Live device read failed"},
            is_error=True,
        )

    async def filter_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        attribute = str(arguments.get("attribute") or "").strip()
        operator = str(arguments.get("operator") or "").strip().lower()
        expected = arguments.get("value")
        valid = {
            "eq", "ne", "lt", "lte", "gt", "gte",
            "contains", "exists", "not_exists",
        }
        if not attribute or operator not in valid:
            return MCPToolResult(
                DEVICE_FILTER_TOOL, arguments, {}, "Invalid filter arguments",
                {"error": "attribute and a valid operator are required"},
                is_error=True,
            )
        if operator not in {"exists", "not_exists"} and "value" not in arguments:
            return MCPToolResult(
                DEVICE_FILTER_TOOL, arguments, {}, "Comparison value required",
                {"error": "value is required for this operator"},
                is_error=True,
            )

        source, devices = await self._live_devices(enrich_identity=False)
        if not self._tool_succeeded(source):
            return self._read_failure(DEVICE_FILTER_TOOL, arguments, source)

        wanted = self._normalized_attribute(attribute)
        matches: list[dict[str, Any]] = []
        comparison_errors = 0
        for device in devices:
            attributes = self._device_attributes(device)
            actual = next(
                (
                    value for key, value in attributes.items()
                    if self._normalized_attribute(str(key)) == wanted
                ),
                None,
            )
            if actual is None:
                actual = next(
                    (
                        value for key, value in device.items()
                        if self._normalized_attribute(str(key)) == wanted
                    ),
                    None,
                )
            try:
                matched = self._attribute_matches(actual, operator, expected)
            except (TypeError, ValueError):
                comparison_errors += 1
                continue
            if matched:
                matches.append({
                    "id": device.get("id") or device.get("deviceId"),
                    "label": device.get("label") or device.get("name"),
                    "room": device.get("room") or device.get("roomName"),
                    "attribute": attribute,
                    "value": actual,
                })
        data = {
            "attribute": attribute,
            "operator": operator,
            "comparison_value": expected,
            "matches": matches,
            "count": len(matches),
            "total_scanned": len(devices),
            "comparison_errors": comparison_errors,
            "complete": True,
        }
        return MCPToolResult(
            DEVICE_FILTER_TOOL, arguments, {}, json.dumps(data), data
        )

    async def active_lights(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(ACTIVE_LIGHTS_TOOL, arguments, source)
        lights = active_lights(devices)
        data = {
            "lights": lights,
            "count": len(lights),
            "definition": "light/bulb capability with switch=on",
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(
            ACTIVE_LIGHTS_TOOL, arguments, {}, json.dumps(data), data
        )

    async def active_rooms(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(ACTIVE_ROOMS_TOOL, arguments, source)
        rooms = active_room_summary(devices)
        data = {
            "active_rooms": rooms,
            "count": len(rooms),
            "definition": "motion=active OR light switch=on",
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(
            ACTIVE_ROOMS_TOOL, arguments, {}, json.dumps(data), data
        )

    async def active_switches(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(ACTIVE_SWITCHES_TOOL, arguments, source)
        switches = active_non_light_switches(devices)
        data = {
            "switches": switches,
            "count": len(switches),
            "definition": "switch=on excluding light/bulb capabilities",
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(
            ACTIVE_SWITCHES_TOOL, arguments, {}, json.dumps(data), data
        )
