from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from device_state_summary import (
    active_lights,
    active_non_light_switches,
    active_room_summary,
    device_attributes,
)
from device_target_resolver import resolve_device_candidate, targeted_name_variants
from mcp_client import HubitatMCPClient, MCPToolResult
from request_metrics import active_request_identity


logger = logging.getLogger("HomeBrainOS.DeviceQuery")

DEVICE_FILTER_TOOL = "homebrain_filter_devices"
DEVICE_QUERY_TOOL = "homebrain_query_devices"
DEVICE_RESOLVE_TOOL = "homebrain_resolve_device"
ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
HOME_SNAPSHOT_TOOL = "homebrain_home_snapshot"
WEATHER_SNAPSHOT_TOOL = "homebrain_weather_snapshot"

_REQUEST_DEVICE_SNAPSHOT: ContextVar[
    tuple[object, MCPToolResult, list[dict[str, Any]]] | None
] = ContextVar("homebrain_request_device_snapshot", default=None)


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
        return device_attributes(device)

    _ATTRIBUTE_ALIASES = {
        "battery": ("battery", "batteryLevel"),
        "humidity": ("humidity",),
        "power": ("power", "activePower", "powerMeter"),
        "temperature": ("temperature", "temperatureC"),
    }

    @classmethod
    def _attribute_value(
        cls, device: dict[str, Any], attribute: str
    ) -> tuple[str | None, Any]:
        wanted_names = cls._ATTRIBUTE_ALIASES.get(
            cls._normalized_attribute(attribute), (attribute,)
        )
        wanted = {cls._normalized_attribute(name) for name in wanted_names}
        combined = {**device, **cls._device_attributes(device)}
        for key, value in combined.items():
            if cls._normalized_attribute(str(key)) in wanted and value is not None:
                return str(key), value
        return None, None

    @staticmethod
    def _capability_names(device: dict[str, Any]) -> set[str]:
        values = device.get("capabilities") or []
        names: set[str] = set()
        if isinstance(values, dict):
            values = values.keys()
        for item in values if isinstance(values, (list, tuple, set, dict)) else []:
            if isinstance(item, dict):
                item = item.get("name") or item.get("capability")
            if item:
                names.add(str(item).casefold())
        return names

    @classmethod
    def _matches_device_kind(cls, device: dict[str, Any], kind: str) -> bool:
        kind = kind.casefold()
        if kind in {"", "any"}:
            return True
        label = str(device.get("label") or device.get("name") or "").casefold()
        room = str(device.get("room") or device.get("roomName") or "").casefold()
        capabilities = cls._capability_names(device)
        is_light = (
            bool(capabilities & {"light", "bulb", "colorcontrol", "colortemperature"})
            or any(word in label for word in (" light", "lamp", "bulb"))
        )
        is_socket = (
            "outlet" in capabilities
            or any(word in label for word in ("socket", "plug", "outlet"))
            or room == "sockets"
        )
        if kind == "light":
            return is_light
        if kind in {"socket", "outlet", "plug"}:
            return is_socket
        if kind == "switch":
            return "switch" in capabilities and not is_light
        if kind == "sensor":
            return not bool(capabilities & {"switch", "outlet"}) and not is_light
        return True

    @staticmethod
    def _is_ambient_room_reading(
        device: dict[str, Any],
        attribute: str,
    ) -> bool:
        """Reject equipment telemetry from room climate comparisons."""

        if attribute.casefold() not in {"temperature", "humidity"}:
            return True
        room = str(device.get("room") or device.get("roomName") or "").strip().casefold()
        label = str(device.get("label") or device.get("name") or "").strip().casefold()
        if room in {
            "appliances", "bridge", "energy", "internet", "multimedia", "sockets",
        }:
            return False
        return not (
            label.startswith("hub info")
            or any(word in label for word in ("fridge", "freezer", "refrigerator"))
        )

    @staticmethod
    def _numeric_value(value: Any) -> float:
        cleaned = re.sub(r"[^0-9.+-]", "", str(value))
        return float(cleaned)

    @staticmethod
    def _unit_for(attribute: str) -> str | None:
        return {
            "battery": "%",
            "humidity": "%",
            "power": "W",
            "temperature": "°C",
        }.get(attribute.casefold())

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
        request_identity = active_request_identity()
        cached = _REQUEST_DEVICE_SNAPSHOT.get()
        if (
            request_identity is not None
            and cached is not None
            and cached[0] is request_identity
        ):
            source = cached[1]
            devices = [dict(item) for item in cached[2]]
            if enrich_identity:
                try:
                    identities = list(await self.mcp.get_cached_devices() or [])
                except Exception as exc:
                    logger.warning("Could not enrich live device states with identity: %s", exc)
                    identities = []
                devices = self._merge_device_identity(devices, identities)
            return source, devices

        source_arguments = {"tool": "hub_list_devices", "args": {}}
        started = time.monotonic()
        source = await self.mcp.call_tool("hub_read_devices", source_arguments)
        raw_devices = [
            item
            for item in (HubitatMCPClient._find_device_list(source.data) or [])
            if isinstance(item, dict)
        ]
        if request_identity is not None:
            _REQUEST_DEVICE_SNAPSHOT.set(
                (request_identity, source, [dict(item) for item in raw_devices])
            )
        devices = [dict(item) for item in raw_devices]
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
        return MCPToolResult(DEVICE_FILTER_TOOL, arguments, {}, json.dumps(data), data)

    @staticmethod
    def _targeted_name_variants(value: str) -> list[str]:
        return targeted_name_variants(value)

    async def resolve_device(self, arguments: dict[str, Any]) -> MCPToolResult:
        requested = str(arguments.get("name") or "").strip()
        if not requested:
            return MCPToolResult(
                DEVICE_RESOLVE_TOOL,
                arguments,
                {},
                "Device name required",
                {"error": "name is required"},
                is_error=True,
            )

        source, candidates = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(DEVICE_RESOLVE_TOOL, arguments, source)

        resolution = resolve_device_candidate(requested, candidates)
        target = resolution.target
        data = {
            "requested": requested,
            "matched": target is not None,
            "target": target,
            "deviceId": (
                target.get("id") or target.get("deviceId")
                if isinstance(target, dict)
                else None
            ),
            "label": (
                target.get("label") or target.get("name")
                if isinstance(target, dict)
                else None
            ),
            "confidence": resolution.confidence,
            "reason": resolution.reason,
            "alternatives": list(resolution.alternatives),
            "attempts": [{"source": "complete_inventory", "count": len(candidates)}],
            "complete": True,
        }
        return MCPToolResult(DEVICE_RESOLVE_TOOL, arguments, {}, json.dumps(data), data)

    async def query_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Compute aggregates over live device attributes before LLM synthesis."""

        attribute = str(arguments.get("attribute") or "").strip()
        operation = str(arguments.get("operation") or "").strip().lower()
        device_kind = str(arguments.get("device_kind") or "any").strip().lower()
        group_by = str(arguments.get("group_by") or "none").strip().lower()
        try:
            limit = min(100, max(1, int(arguments.get("limit") or 10)))
        except (TypeError, ValueError):
            limit = 10
        if not attribute or operation not in {
            "maximum", "minimum", "top", "sort", "count",
        }:
            return MCPToolResult(
                DEVICE_QUERY_TOOL, arguments, {}, "Invalid query arguments",
                {
                    "error": (
                        "attribute and operation maximum, minimum, top, sort, "
                        "or count are required"
                    )
                },
                is_error=True,
            )

        source, devices = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(DEVICE_QUERY_TOOL, arguments, source)

        rows: list[dict[str, Any]] = []
        conversion_errors = 0
        for device in devices:
            if not self._matches_device_kind(device, device_kind):
                continue
            if group_by == "room" and not self._is_ambient_room_reading(device, attribute):
                continue
            source_attribute, raw_value = self._attribute_value(device, attribute)
            if raw_value is None:
                continue
            try:
                numeric = self._numeric_value(raw_value)
            except (TypeError, ValueError):
                conversion_errors += 1
                continue
            rows.append({
                "id": device.get("id") or device.get("deviceId"),
                "label": device.get("label") or device.get("name"),
                "room": device.get("room") or device.get("roomName"),
                "attribute": attribute,
                "source_attribute": source_attribute,
                "value": int(numeric) if numeric.is_integer() else numeric,
                "unit": self._unit_for(attribute),
            })

        reverse = operation != "minimum"
        rows.sort(
            key=lambda row: (
                float(row["value"]),
                str(row.get("label") or "").casefold(),
            ),
            reverse=reverse,
        )
        grouped: list[dict[str, Any]] = []
        if group_by == "room":
            by_room: dict[str, dict[str, Any]] = {}
            for row in rows:
                room = str(row.get("room") or "Unassigned")
                if room not in by_room:
                    by_room[room] = row
            grouped = [{"room": room, **row} for room, row in by_room.items()]
            grouped.sort(key=lambda row: float(row["value"]), reverse=reverse)

        if operation in {"maximum", "minimum"}:
            results = (grouped or rows)[:1]
        elif operation == "count":
            results = []
        else:
            results = (grouped or rows)[:limit]
        data = {
            "operation": operation,
            "attribute": attribute,
            "device_kind": device_kind,
            "group_by": group_by,
            "count": len(rows),
            "winner": results[0] if results else None,
            "results": results,
            "total_scanned": len(devices),
            "conversion_errors": conversion_errors,
            "complete": True,
        }
        return MCPToolResult(DEVICE_QUERY_TOOL, arguments, {}, json.dumps(data), data)

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
        return MCPToolResult(ACTIVE_LIGHTS_TOOL, arguments, {}, json.dumps(data), data)

    async def weather_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Return current attributes from the hub's weather device."""

        source, devices = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(WEATHER_SNAPSHOT_TOOL, arguments, source)

        candidates: list[dict[str, Any]] = []
        for device in devices:
            label = str(device.get("label") or device.get("name") or "").strip()
            room = str(device.get("room") or device.get("roomName") or "").strip()
            capabilities = self._capability_names(device)
            if not (
                "weather" in label.casefold()
                or "weather" in room.casefold()
                or "weather" in capabilities
            ):
                continue
            candidates.append({
                "id": device.get("id") or device.get("deviceId"),
                "label": label,
                "room": room or None,
                "attributes": self._device_attributes(device),
            })

        candidates.sort(
            key=lambda item: (
                "weather" not in str(item.get("label") or "").casefold(),
                str(item.get("label") or "").casefold(),
            )
        )
        data = {
            "weather_devices": candidates,
            "primary": candidates[0] if candidates else None,
            "count": len(candidates),
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(WEATHER_SNAPSHOT_TOOL, arguments, {}, json.dumps(data), data)

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
        return MCPToolResult(ACTIVE_ROOMS_TOOL, arguments, {}, json.dumps(data), data)

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
        return MCPToolResult(ACTIVE_SWITCHES_TOOL, arguments, {}, json.dumps(data), data)

    async def home_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Return one complete, internally consistent whole-home snapshot."""

        source, devices = await self._live_devices(enrich_identity=True)
        if not self._tool_succeeded(source):
            return self._read_failure(HOME_SNAPSHOT_TOOL, arguments, source)

        presence: list[dict[str, Any]] = []
        motion: list[dict[str, Any]] = []
        contacts: list[dict[str, Any]] = []
        locks: list[dict[str, Any]] = []
        low_batteries: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        for device in devices:
            attrs = device_attributes(device)
            label = device.get("label") or device.get("name")
            room = device.get("room") or device.get("roomName")
            identity = {
                "id": device.get("id") or device.get("deviceId"),
                "label": label,
                "room": room,
            }

            presence_value = str(attrs.get("presence") or "").casefold()
            capabilities = self._capability_names(device)
            if (
                presence_value in {"present", "home", "arrived", "true", "active"}
                and "switch" not in capabilities
                and not bool(capabilities & {"actuator", "outlet"})
            ):
                presence.append({**identity, "presence": attrs.get("presence")})
            if str(attrs.get("motion") or "").casefold() == "active":
                motion.append({**identity, "motion": "active"})
            if str(attrs.get("contact") or "").casefold() == "open":
                contacts.append({**identity, "contact": "open"})
            if str(attrs.get("lock") or "").casefold() == "unlocked":
                locks.append({**identity, "lock": "unlocked"})

            battery = attrs.get("battery")
            try:
                battery_number = float(str(battery).strip().rstrip("%"))
            except (TypeError, ValueError):
                battery_number = None
            if battery_number is not None and battery_number <= 20:
                rendered_battery: int | float = (
                    int(battery_number) if battery_number.is_integer() else battery_number
                )
                low_batteries.append({**identity, "battery": rendered_battery})

            health = str(
                attrs.get("healthStatus")
                or attrs.get("networkStatus")
                or attrs.get("rtt")
                or ""
            ).casefold()
            if health in {"offline", "unavailable", "timeout", "failed"}:
                alerts.append({**identity, "status": health})
            hub_alerts = attrs.get("hubAlerts")
            if hub_alerts not in (None, "", "[]", []):
                alerts.append({**identity, "status": hub_alerts})

        lights = active_lights(devices)
        switches = active_non_light_switches(devices)
        rooms = active_room_summary(devices)
        sort_key = lambda item: str(item.get("label") or "").casefold()
        data = {
            "presence": sorted(presence, key=sort_key),
            "active_motion": sorted(motion, key=sort_key),
            "lights_on": lights,
            "switches_on": switches,
            "active_rooms": rooms,
            "open_contacts": sorted(contacts, key=sort_key),
            "unlocked_locks": sorted(locks, key=sort_key),
            "low_batteries": sorted(low_batteries, key=sort_key),
            "alerts": sorted(alerts, key=sort_key),
            "counts": {
                "presence": len(presence),
                "active_motion": len(motion),
                "lights_on": len(lights),
                "switches_on": len(switches),
                "active_rooms": len(rooms),
                "open_contacts": len(contacts),
                "unlocked_locks": len(locks),
                "low_batteries": len(low_batteries),
                "alerts": len(alerts),
            },
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(HOME_SNAPSHOT_TOOL, arguments, {}, json.dumps(data), data)
