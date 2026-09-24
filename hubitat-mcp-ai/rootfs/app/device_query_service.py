from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from device_read_contract import (
    LIVE_CONTEXT_ATTRIBUTES,
    LIVE_CONTEXT_RESOURCE_URI,
    live_context_devices,
    live_context_is_complete,
)
from device_state_summary import (
    active_lights,
    active_non_light_switches,
    active_room_summary,
    capability_names,
    device_attributes,
    is_light_device,
)
from device_target_resolver import (
    CandidateResolution,
    device_commands,
    resolve_device_candidate,
    targeted_name_variants,
)
from mcp_client import HubitatMCPClient, MCPToolResult
from mcp_client import tool_succeeded as _shared_tool_succeeded
from request_metrics import active_request_identity, increment_active_metric


logger = logging.getLogger("HomeBrainOS.DeviceQuery")

DEVICE_FILTER_TOOL = "homebrain_filter_devices"
DEVICE_QUERY_TOOL = "homebrain_query_devices"
DEVICE_RESOLVE_TOOL = "homebrain_resolve_device"
DEVICE_INVENTORY_TOOL = "homebrain_device_inventory"
ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
HOME_SNAPSHOT_TOOL = "homebrain_home_snapshot"
WEATHER_SNAPSHOT_TOOL = "homebrain_weather_snapshot"

_TARGET_RESOLUTION_FIELDS = [
    "id", "name", "label", "room", "capabilities", "attributes", "commands",
]

_REQUEST_DEVICE_SNAPSHOT: ContextVar[
    tuple[object, MCPToolResult, list[dict[str, Any]]] | None
] = ContextVar("homebrain_request_device_snapshot", default=None)

# Request-local target reuse. A model commonly resolves a named device first and
# then calls another local tool (history/control/query) that resolves the same
# label again. Keep only successful target identities under the opaque active
# request identity so later service instances can reuse them without another
# Hubitat labelFilter read. The identity guard prevents cross-request leakage.
_REQUEST_DEVICE_RESOLUTIONS: ContextVar[
    tuple[object, dict[str, dict[str, Any]]] | None
] = ContextVar("homebrain_request_device_resolutions", default=None)

_CONTEXT_ATTRIBUTE_BY_NORMALIZED = {
    re.sub(r"[^a-z0-9]", "", name.casefold()): name
    for name in LIVE_CONTEXT_ATTRIBUTES
}
# These identity/structure fields are always part of hubitat://context and do
# not require a detailed full-inventory read. Keeping this separate from
# LIVE_CONTEXT_ATTRIBUTES matters: room/label/capabilities are metadata, not
# live state attributes requested from Hubitat.
_CONTEXT_STRUCTURAL_FIELDS = frozenset({
    "id", "deviceid", "name", "label", "room", "roomname", "capabilities",
})


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
        return _shared_tool_succeeded(result)

    @staticmethod
    def _resolution_cache_key(value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

    @classmethod
    def _cached_resolution_target(
        cls,
        requested: str,
        *,
        required_command: str = "",
        required_fields: set[str] | frozenset[str] | None = None,
        required_capabilities: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        request_identity = active_request_identity()
        cached = _REQUEST_DEVICE_RESOLUTIONS.get()
        if (
            request_identity is None
            or cached is None
            or cached[0] is not request_identity
        ):
            return None
        target = cached[1].get(cls._resolution_cache_key(requested))
        if not isinstance(target, dict):
            return None
        if required_command and required_command.casefold() not in device_commands(target):
            return None
        required = {str(field) for field in (required_fields or set()) if str(field)}
        wanted_capabilities = {
            re.sub(r"[^a-z0-9]", "", str(value).casefold())
            for value in (required_capabilities or set())
            if str(value).strip()
        }
        if wanted_capabilities:
            advertised = {
                re.sub(r"[^a-z0-9]", "", str(value).casefold())
                for value in cls._capability_names(target)
            }
            if advertised & wanted_capabilities:
                # A positive advertised capability is enough to authorize the
                # corresponding typed history read. Current attribute state can
                # legitimately be absent from the compact context snapshot.
                required.discard("attributes")
        if required and not required.issubset(target.keys()):
            increment_active_metric("resolution_cache_metadata_miss")
            return None
        return dict(target)

    @classmethod
    def _cache_resolution_target(
        cls,
        requested: str,
        target: dict[str, Any],
    ) -> None:
        request_identity = active_request_identity()
        if request_identity is None:
            return
        cached = _REQUEST_DEVICE_RESOLUTIONS.get()
        values = (
            dict(cached[1])
            if cached is not None and cached[0] is request_identity
            else {}
        )
        for alias in (
            requested,
            target.get("label"),
            target.get("name"),
            target.get("id"),
            target.get("deviceId"),
        ):
            key = cls._resolution_cache_key(alias)
            if key:
                values[key] = dict(target)
        _REQUEST_DEVICE_RESOLUTIONS.set((request_identity, values))

    @staticmethod
    def _normalized_attribute(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @classmethod
    def _attribute_matches(cls, actual: Any, operator: str, expected: Any) -> bool:
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
        cls,
        device: dict[str, Any],
        attribute: str,
        *,
        allow_generic_value_fallback: bool = False,
    ) -> tuple[str | None, Any]:
        wanted_names = cls._ATTRIBUTE_ALIASES.get(
            cls._normalized_attribute(attribute), (attribute,)
        )
        wanted = {cls._normalized_attribute(name) for name in wanted_names}
        combined = {**device, **cls._device_attributes(device)}
        for key, value in combined.items():
            if cls._normalized_attribute(str(key)) in wanted and value is not None:
                return str(key), value
        if allow_generic_value_fallback:
            value_str = combined.get("valueStr")
            if isinstance(value_str, str) and value_str.strip():
                return "valueStr", value_str
            if combined.get("value") is not None:
                return "value", combined["value"]
        return None, None

    @classmethod
    def _room_controller_candidates(
        cls,
        devices: list[dict[str, Any]],
        room_value: Any,
    ) -> list[dict[str, Any]]:
        """Rank button-capable candidates by room metadata and control semantics.

        Exact Hubitat room assignment always outranks label affinity. Within the
        same basis, dimmer/remote/switch-style controller labels rank ahead of a
        generic button label so a bounded causal pass is more likely to inspect
        the controller most directly associated with lighting.
        """

        wanted_room = " ".join(str(room_value or "").strip().casefold().split())
        if not wanted_room:
            return []

        ranked: list[tuple[int, int, str, dict[str, Any]]] = []
        seen_ids: set[str] = set()

        for device in devices:
            capabilities = sorted(cls._capability_names(device))
            normalized_caps = {
                re.sub(r"[^a-z0-9]", "", value.casefold())
                for value in capabilities
            }
            if not any("button" in value for value in normalized_caps):
                continue

            device_id = str(device.get("id") or device.get("deviceId") or "").strip()
            label = str(device.get("label") or device.get("name") or "").strip()
            room = str(device.get("room") or device.get("roomName") or "").strip()
            normalized_room = " ".join(room.casefold().split())
            normalized_label = " ".join(label.casefold().split())

            if normalized_room == wanted_room:
                basis = "room"
                basis_rank = 0
            elif wanted_room in normalized_label:
                basis = "label-affinity"
                basis_rank = 1
            else:
                continue

            dedupe = device_id or normalized_label
            if not dedupe or dedupe in seen_ids:
                continue
            seen_ids.add(dedupe)

            if "dimmer" in normalized_label:
                role_rank = 0
            elif any(
                token in normalized_label
                for token in ("remote", "switch", "scene controller")
            ):
                role_rank = 1
            elif "button" in normalized_label:
                role_rank = 2
            else:
                role_rank = 3

            item = {
                "id": device.get("id") or device.get("deviceId"),
                "label": label or None,
                "room": room or None,
                "capabilities": capabilities,
                "matchBasis": basis,
            }
            ranked.append((basis_rank, role_rank, normalized_label, item))

        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        return [item[3] for item in ranked[:12]]

    @classmethod
    def _room_trigger_sensor_candidates(
        cls,
        devices: list[dict[str, Any]],
        room_value: Any,
    ) -> list[dict[str, Any]]:
        """Rank capability-grounded occupancy sensors for causal correlation.

        Exact room assignment wins over label affinity. PresenceSensor outranks a
        motion-only device within the same basis. Derived/virtual/soft sensors are
        still valid candidates, but lose a final tiebreak to a physical-looking
        sensor with the same capability basis.
        """

        wanted_room = " ".join(str(room_value or "").strip().casefold().split())
        if not wanted_room:
            return []

        ranked: list[tuple[int, int, int, str, dict[str, Any]]] = []
        seen: set[str] = set()
        for device in devices:
            capabilities = sorted(cls._capability_names(device))
            normalized = {
                re.sub(r"[^a-z0-9]", "", value.casefold())
                for value in capabilities
            }
            has_presence = "presencesensor" in normalized
            has_motion = "motionsensor" in normalized
            if not (has_presence or has_motion):
                continue

            attribute = "presence" if has_presence else "motion"
            capability_rank = 0 if has_presence else 1

            label = str(device.get("label") or device.get("name") or "").strip()
            room = str(device.get("room") or device.get("roomName") or "").strip()
            normalized_room = " ".join(room.casefold().split())
            normalized_label = " ".join(label.casefold().split())
            if normalized_room == wanted_room:
                basis_rank = 0
                basis = "room"
            elif wanted_room and wanted_room in normalized_label:
                basis_rank = 1
                basis = "label-affinity"
            else:
                continue

            device_id = str(device.get("id") or device.get("deviceId") or "").strip()
            key = device_id or normalized_label
            if not key or key in seen:
                continue
            seen.add(key)

            derived_rank = (
                1
                if any(
                    token in normalized_label
                    for token in ("soft sensor", "virtual", "derived")
                )
                else 0
            )
            ranked.append((
                basis_rank,
                capability_rank,
                derived_rank,
                normalized_label,
                {
                    "id": device.get("id") or device.get("deviceId"),
                    "label": label or None,
                    "room": room or None,
                    "capabilities": capabilities,
                    "matchBasis": basis,
                    "suggestedHistoryAttributes": [attribute],
                },
            ))

        ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return [item[4] for item in ranked[:8]]

    @staticmethod
    def _controller_event_source_hints(
        matches: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return bounded same-room controller candidates from capabilities.

        These are only hints for later evidence selection. They do not assert
        that a controller caused anything and they do not trigger history reads.
        """

        hints: list[dict[str, Any]] = []
        for item in matches:
            capabilities = [
                str(value).strip()
                for value in (item.get("capabilities") or [])
                if str(value).strip()
            ]
            normalized = {
                re.sub(r"[^a-z0-9]", "", value.casefold())
                for value in capabilities
            }
            if not any("button" in value for value in normalized):
                continue

            suggested: list[str] = []
            if any("pushablebutton" in value or value == "button" for value in normalized):
                suggested.append("pushed")
            if any("holdablebutton" in value for value in normalized):
                suggested.append("held")
            if any("releasablebutton" in value for value in normalized):
                suggested.append("released")
            if any(
                "doubletapablebutton" in value
                or "doubletappablebutton" in value
                or "doubletapbutton" in value
                for value in normalized
            ):
                suggested.append("doubleTapped")
            if not suggested:
                suggested.append("pushed")

            hints.append({
                "id": item.get("id"),
                "label": item.get("label"),
                "room": item.get("room"),
                "matchBasis": item.get("matchBasis"),
                "capabilities": capabilities,
                "suggestedHistoryAttributes": list(dict.fromkeys(suggested)),
            })
            if len(hints) >= 8:
                break
        return hints

    @staticmethod
    def _capability_names(device: dict[str, Any]) -> set[str]:
        return capability_names(device)

    @classmethod
    def _matches_device_kind(cls, device: dict[str, Any], kind: str) -> bool:
        kind = kind.casefold()
        if kind in {"", "any"}:
            return True
        label = str(device.get("label") or device.get("name") or "").casefold()
        room = str(device.get("room") or device.get("roomName") or "").casefold()
        capabilities = cls._capability_names(device)
        is_light = is_light_device(device)
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
        if kind == "motion":
            return bool(capabilities & {"motionsensor"}) or "motion" in label
        if kind == "sensor":
            return not bool(capabilities & {"switch", "outlet"}) and not is_light
        return True

    _METER_LABEL_TOKENS = ("meter", "energy monitor", "power monitor")
    _METER_EXCLUDED_LABEL_TOKENS = ("plug", "socket", "outlet", "switch")

    @classmethod
    def _whole_house_meter_candidate(
        cls, devices: list[dict[str, Any]], device_kind: str, attribute: str
    ) -> dict[str, Any] | None:
        if cls._normalized_attribute(attribute) != "power":
            return None
        for device in devices:
            if not cls._matches_device_kind(device, device_kind):
                continue
            label = str(device.get("label") or device.get("name") or "").casefold()
            if not any(token in label for token in cls._METER_LABEL_TOKENS):
                continue
            if any(token in label for token in cls._METER_EXCLUDED_LABEL_TOKENS):
                continue
            source_attribute, raw_value = cls._attribute_value(
                device, attribute, allow_generic_value_fallback=True
            )
            if raw_value is None:
                continue
            return {
                "id": device.get("id") or device.get("deviceId"),
                "label": device.get("label") or device.get("name"),
                "room": device.get("room") or device.get("roomName"),
                "source_attribute": source_attribute,
                "raw_value": raw_value,
            }
        return None

    @staticmethod
    def _is_ambient_room_reading(device: dict[str, Any], attribute: str) -> bool:
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
    def _unit_for(
        device: dict[str, Any], attribute: str, source_attribute: str | None = None
    ) -> str | None:
        wanted_names = {
            str(name).casefold()
            for name in (source_attribute, attribute)
            if name
        }
        for raw in (
            device.get("attributes"), device.get("states"), device.get("currentStates"),
        ):
            if not isinstance(raw, list):
                continue
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("attribute")
                if name is None or str(name).casefold() not in wanted_names:
                    continue
                unit = item.get("unit")
                if unit not in (None, ""):
                    return str(unit)
        return {
            "battery": "%",
            "humidity": "%",
            "power": "W",
            "temperature": "°C",
        }.get(attribute.casefold())

    @staticmethod
    def _merge_device_identity(
        devices: list[dict[str, Any]], identities: list[dict[str, Any]]
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

    @classmethod
    def _context_attribute_name(cls, attribute: str) -> str | None:
        """Return a context-resource attribute only for an exact structural match.

        Attribute aliases such as ``batteryLevel`` are intentionally not mapped to
        ``battery`` here: the upstream context resource asks the hub for the named
        default attributes and cannot prove that a differently named driver state is
        equivalent. Unsupported attributes stay on the complete detailed read path.
        """

        return _CONTEXT_ATTRIBUTE_BY_NORMALIZED.get(cls._normalized_attribute(attribute))

    async def _bulk_live_devices(
        self,
        required_attributes: set[str],
        *,
        enrich_fallback_identity: bool = False,
    ) -> tuple[MCPToolResult, list[dict[str, Any]]]:
        """Use Hubitat's single-bulk-read context resource when it covers the need.

        This path is based on structured state requirements, never prompt wording.
        Any unsupported attribute, unavailable resource, partial inventory, truncation,
        or generation invalidation falls back to the established complete inventory.
        Aggregate consumers that need capability/room identity can request enrichment
        on that fallback, preserving the pre-context correctness contract without
        making the successful bulk-context path pay for a detailed manifest refresh.
        """

        wanted = {str(value) for value in required_attributes if str(value)}
        supported = {name.casefold() for name in LIVE_CONTEXT_ATTRIBUTES}
        if any(value.casefold() not in supported for value in wanted):
            return await self._live_devices(enrich_identity=enrich_fallback_identity)
        if not isinstance(self.mcp, HubitatMCPClient):
            return await self._live_devices(enrich_identity=enrich_fallback_identity)

        started = time.monotonic()
        try:
            context = await self.mcp.get_live_context()
        except Exception as exc:
            logger.warning("Bulk live context unavailable; using full inventory: %s", exc)
            return await self._live_devices(enrich_identity=enrich_fallback_identity)
        if not live_context_is_complete(context):
            logger.warning("Bulk live context was partial; using full inventory")
            return await self._live_devices(enrich_identity=enrich_fallback_identity)

        devices = live_context_devices(context)
        source_arguments = {
            "resource": LIVE_CONTEXT_RESOURCE_URI,
            "strategy": "bulk-live-context",
            "required_attributes": sorted(wanted, key=str.casefold),
        }
        data = {"devices": devices, "resource": LIVE_CONTEXT_RESOURCE_URI}
        source = MCPToolResult(
            "hub_read_devices",
            source_arguments,
            {},
            json.dumps(data, ensure_ascii=False),
            data,
        )
        self._record_evidence(
            "hub_read_devices",
            source_arguments,
            success=True,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} bulk live-context device records",
            evidence_kind="authoritative_state_snapshot",
        )
        return source, devices

    async def _live_devices(
        self, *, enrich_identity: bool
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
        evidence_arguments = (
            dict(source.arguments)
            if isinstance(source.arguments, dict) and source.arguments
            else source_arguments
        )
        self._record_evidence(
            "hub_read_devices",
            evidence_arguments,
            success=self._tool_succeeded(source),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} source device records",
            evidence_kind="authoritative_state_snapshot",
        )
        return source, devices

    async def _active_room_devices(self) -> tuple[MCPToolResult, list[dict[str, Any]]]:
        """Read the structural live-state set required by active-room logic."""

        return await self._bulk_live_devices(
            {"motion", "switch"}, enrich_fallback_identity=True
        )

    @staticmethod
    def _read_failure(
        tool_name: str, arguments: dict[str, Any], source: MCPToolResult
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
                DEVICE_FILTER_TOOL,
                arguments,
                {},
                "Invalid filter arguments",
                {"error": "attribute and a valid operator are required"},
                is_error=True,
            )
        if operator not in {"exists", "not_exists"} and "value" not in arguments:
            return MCPToolResult(
                DEVICE_FILTER_TOOL,
                arguments,
                {},
                "Comparison value required",
                {"error": "value is required for this operator"},
                is_error=True,
            )

        normalized_attribute = self._normalized_attribute(attribute)
        context_attribute = self._context_attribute_name(attribute)
        if context_attribute is not None:
            source, devices = await self._bulk_live_devices({context_attribute})
        elif normalized_attribute in _CONTEXT_STRUCTURAL_FIELDS:
            # hubitat://context already carries stable identity, room and
            # capabilities for every device. Structural filters therefore do not
            # need the much slower detailed hub_list_devices inventory.
            source, devices = await self._bulk_live_devices(set())
        else:
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
                    value
                    for key, value in attributes.items()
                    if self._normalized_attribute(str(key)) == wanted
                ),
                None,
            )
            if actual is None:
                actual = next(
                    (
                        value
                        for key, value in device.items()
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
                label = device.get("label") or device.get("name")
                capabilities = sorted(self._capability_names(device))
                matches.append(
                    {
                        "id": device.get("id") or device.get("deviceId"),
                        "label": label,
                        "room": device.get("room") or device.get("roomName"),
                        "capabilities": capabilities,
                        "attribute": attribute,
                        "value": actual,
                    }
                )
                # A complete filter result already establishes stable device
                # identity. Seed the same request-local resolution cache used by
                # the named resolver so a later history read on one of these
                # exact labels can go straight to deviceId instead of paying for
                # another targeted labelFilter call. Required-command checks still
                # fail closed when this compact identity lacks command metadata.
                if label:
                    self._cache_resolution_target(str(label), device)
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
        if normalized_attribute == "room" and operator in {"eq", "contains"}:
            # Room discovery is a semantic operation. Preserve bounded event-source
            # hints for later deterministic causal planning; these are candidates,
            # not causal claims.
            controller_candidates = self._room_controller_candidates(devices, expected)
            controller_hints = self._controller_event_source_hints(controller_candidates)
            trigger_sensor_hints = self._room_trigger_sensor_candidates(devices, expected)
            if controller_hints or trigger_sensor_hints:
                data["eventSourceHints"] = {
                    "controllerCandidates": controller_hints,
                    "triggerSensorCandidates": trigger_sensor_hints,
                    "note": (
                        "Controller candidates advertise button capabilities. Trigger "
                        "sensor candidates advertise MotionSensor/PresenceSensor. Use "
                        "capability-grounded histories and signed transition timing; "
                        "these hints alone do not establish causation."
                    ),
                }
        return MCPToolResult(DEVICE_FILTER_TOOL, arguments, {}, json.dumps(data), data)

    @staticmethod
    def _targeted_name_variants(value: str) -> list[str]:
        return targeted_name_variants(value)

    _KIND_HINT_WORDS = {
        "light": (" light", "lamp", "bulb"),
        "switch": (" switch",),
        "socket": ("socket", "plug", "outlet"),
        "motion": ("motion",),
    }

    @classmethod
    def _infer_kind_hint(cls, requested: str) -> str:
        text = f" {requested.strip().casefold()} "
        for kind, words in cls._KIND_HINT_WORDS.items():
            if any(word in text for word in words):
                return kind
        return ""

    @staticmethod
    def _strip_leading_article(value: str) -> str:
        text = value.strip().casefold()
        for article in ("the ", "a ", "an "):
            if text.startswith(article):
                return text[len(article):]
        return text

    async def resolve_device(
        self,
        arguments: dict[str, Any],
        *,
        required_fields: set[str] | frozenset[str] | None = None,
        required_capabilities: set[str] | frozenset[str] | None = None,
    ) -> MCPToolResult:
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

        required_command = str(arguments.get("required_command") or "").strip()
        cached_target = self._cached_resolution_target(
            requested,
            required_command=required_command,
            required_fields=required_fields,
            required_capabilities=required_capabilities,
        )
        if cached_target is not None:
            increment_active_metric("resolution_cache_hit")
            label = cached_target.get("label") or cached_target.get("name")
            device_id = cached_target.get("id") or cached_target.get("deviceId")
            data = {
                "requested": requested,
                "matched": True,
                "target": cached_target,
                "deviceId": device_id,
                "label": label,
                "confidence": 1.0,
                "reason": "request-local resolved device cache",
                "alternatives": [],
                "attempts": [{"source": "request_cache", "count": 1}],
                "complete": True,
                "requestCacheHit": True,
            }
            return MCPToolResult(
                DEVICE_RESOLVE_TOOL,
                arguments,
                {},
                json.dumps(data),
                data,
            )

        attribute_key = self._normalized_attribute(
            self._strip_leading_article(requested)
        )
        bare_attribute = attribute_key in self._ATTRIBUTE_ALIASES
        if bare_attribute:
            source, candidates = await self._live_devices(enrich_identity=True)
            attempt_source = "complete_inventory"
        else:
            source_arguments = {
                "tool": "hub_list_devices",
                "args": {
                    "labelFilter": requested,
                    "fields": list(_TARGET_RESOLUTION_FIELDS),
                },
            }
            started = time.monotonic()
            source = await self.mcp.call_tool("hub_read_devices", source_arguments)
            candidates = [
                item
                for item in (HubitatMCPClient._find_device_list(source.data) or [])
                if isinstance(item, dict)
            ]
            self._record_evidence(
                "hub_read_devices",
                source_arguments,
                success=self._tool_succeeded(source),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{len(candidates)} targeted device candidates",
                supports_live_claim=False,
                evidence_kind="targeted_device_lookup",
            )
            attempt_source = "label_filter"
        if not self._tool_succeeded(source):
            return self._read_failure(DEVICE_RESOLVE_TOOL, arguments, source)

        kind_hint = self._infer_kind_hint(requested)
        scoped_candidates = candidates
        if kind_hint:
            kind_filtered = [
                device
                for device in candidates
                if self._matches_device_kind(device, kind_hint)
            ]
            if kind_filtered:
                scoped_candidates = kind_filtered

        if required_command:
            capable = [
                device
                for device in scoped_candidates
                if required_command.casefold() in device_commands(device)
            ]
            if capable:
                scoped_candidates = capable

        resolution = resolve_device_candidate(requested, scoped_candidates)
        exact_match_reasons = {
            "exact normalized name",
            "exact semantic room and device name",
            "exact semantic name with device-kind token omitted",
        }
        if (
            resolution.reason not in exact_match_reasons
            and attribute_key in self._ATTRIBUTE_ALIASES
        ):
            reporters = [
                device
                for device in scoped_candidates
                if self._attribute_value(device, attribute_key)[0] is not None
            ]
            if len(reporters) > 1:
                alternative_labels = tuple(
                    str(device.get("label") or device.get("name") or "").strip()
                    for device in reporters
                )
                resolution = CandidateResolution(
                    target=None,
                    matched_name=None,
                    confidence=resolution.confidence,
                    alternatives=alternative_labels,
                    reason=(
                        f"{requested!r} is a bare attribute reported by "
                        f"{len(reporters)} devices; the candidates are "
                        f"{', '.join(alternative_labels)}."
                    ),
                )

        # A legacy labelFilter is intentionally narrow and can return zero
        # rows for a harmless misspelling even when the complete structural
        # identity cache contains one unmistakable device. History/causal reads
        # must not terminate on that transport quirk. Fall back to the bounded
        # authoritative identity world and run the same conservative resolver;
        # its confidence/margin rules still refuse ambiguous names.
        identity_fallback_used = False
        if (
            resolution.target is None
            and not bare_attribute
            and not resolution.alternatives
        ):
            identities: list[dict[str, Any]] = []
            peek = getattr(self.mcp, "peek_device_identities", None)
            if callable(peek):
                try:
                    identities = [
                        dict(item)
                        for item in (peek() or [])
                        if isinstance(item, dict)
                    ]
                except Exception:
                    identities = []
            if not identities:
                identity_reader = getattr(self.mcp, "get_device_identities", None)
                if callable(identity_reader):
                    try:
                        identities = [
                            dict(item)
                            for item in (await identity_reader() or [])
                            if isinstance(item, dict)
                        ]
                    except Exception:
                        identities = []

            fallback_candidates = identities
            if kind_hint:
                typed = [
                    device
                    for device in fallback_candidates
                    if self._matches_device_kind(device, kind_hint)
                ]
                if typed:
                    fallback_candidates = typed
            if required_command:
                fallback_candidates = [
                    device
                    for device in fallback_candidates
                    if required_command.casefold() in device_commands(device)
                ]
            wanted_capabilities = {
                re.sub(r"[^a-z0-9]", "", str(value).casefold())
                for value in (required_capabilities or set())
                if str(value).strip()
            }
            if wanted_capabilities:
                capable = []
                for device in fallback_candidates:
                    advertised = {
                        re.sub(r"[^a-z0-9]", "", str(value).casefold())
                        for value in self._capability_names(device)
                    }
                    if advertised & wanted_capabilities:
                        capable.append(device)
                if capable:
                    fallback_candidates = capable

            if fallback_candidates:
                fallback_resolution = resolve_device_candidate(
                    requested,
                    fallback_candidates,
                )
                if fallback_resolution.target is not None:
                    resolution = fallback_resolution
                    identity_fallback_used = True

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
            "attempts": [
                {"source": attempt_source, "count": len(candidates)},
                *(
                    [{
                        "source": "authoritative_identity_fuzzy",
                        "count": len(fallback_candidates),
                    }]
                    if identity_fallback_used
                    else []
                ),
            ],
            "complete": bare_attribute or target is not None,
            "requestCacheHit": False,
        }
        if isinstance(target, dict):
            self._cache_resolution_target(requested, target)
        return MCPToolResult(DEVICE_RESOLVE_TOOL, arguments, {}, json.dumps(data), data)

    async def query_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
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
                DEVICE_QUERY_TOOL,
                arguments,
                {},
                "Invalid query arguments",
                {
                    "error": (
                        "attribute and operation maximum, minimum, top, sort, "
                        "or count are required"
                    )
                },
                is_error=True,
            )

        # Numeric aggregate questions only need the requested live attribute plus
        # compact identity. When hubitat://context can supply that attribute, use
        # the same complete bulk snapshot path as the home summary instead of
        # paying for a full detailed hub_list_devices inventory. Unsupported or
        # partial context resources still fall back to the established complete
        # inventory path, preserving correctness.
        context_attribute = self._context_attribute_name(attribute)
        if context_attribute is not None:
            source, devices = await self._bulk_live_devices(
                {context_attribute}, enrich_fallback_identity=True
            )
        else:
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
            rows.append(
                {
                    "id": device.get("id") or device.get("deviceId"),
                    "label": device.get("label") or device.get("name"),
                    "room": device.get("room") or device.get("roomName"),
                    "attribute": attribute,
                    "source_attribute": source_attribute,
                    "value": int(numeric) if numeric.is_integer() else numeric,
                    "unit": self._unit_for(device, attribute, source_attribute),
                }
            )

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
        meter_candidate = self._whole_house_meter_candidate(devices, device_kind, attribute)
        if meter_candidate is not None:
            data["whole_house_meter_candidate"] = meter_candidate
            data["whole_house_meter_hint"] = (
                f"'{meter_candidate['label']}' looks like a dedicated whole-house "
                f"meter device (reads via '{meter_candidate['source_attribute']}' = "
                f"{meter_candidate['raw_value']!r}), separate from the {len(rows)} "
                "discrete device(s) counted above."
            )
        if not rows:
            fallback_candidates = sum(
                1
                for device in devices
                if self._matches_device_kind(device, device_kind)
                and self._attribute_value(
                    device, attribute, allow_generic_value_fallback=True
                )[0]
                in {"valueStr", "value"}
            )
            if fallback_candidates:
                data["hint"] = (
                    f"No device reported an attribute literally named '{attribute}', "
                    f"but {fallback_candidates} matching device(s) report a reading "
                    "via 'valueStr' or 'value' instead."
                )
        return MCPToolResult(DEVICE_QUERY_TOOL, arguments, {}, json.dumps(data), data)

    async def active_lights(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._bulk_live_devices(
            {"switch"}, enrich_fallback_identity=True
        )
        if not self._tool_succeeded(source):
            return self._read_failure(ACTIVE_LIGHTS_TOOL, arguments, source)
        lights = active_lights(devices)
        data = {
            "lights": lights,
            "count": len(lights),
            "definition": "light/bulb capability with switch=on",
            "total_scanned": len(devices),
            "complete": True,
            "read_scope": "bulk live context",
        }
        return MCPToolResult(ACTIVE_LIGHTS_TOOL, arguments, {}, json.dumps(data), data)

    async def weather_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
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
            candidates.append(
                {
                    "id": device.get("id") or device.get("deviceId"),
                    "label": label,
                    "room": room or None,
                    "attributes": self._device_attributes(device),
                }
            )

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

    async def device_inventory(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Return the complete structural device inventory without state pagination."""

        try:
            identities = await self.mcp.get_device_identities()
        except Exception as exc:
            data = {
                "success": False,
                "error": f"Device inventory unavailable: {exc}",
                "count": 0,
                "rooms": [],
                "complete": False,
            }
            return MCPToolResult(
                DEVICE_INVENTORY_TOOL,
                arguments,
                {},
                json.dumps(data),
                data,
                is_error=True,
            )

        unique: dict[str, dict[str, Any]] = {}
        for index, device in enumerate(identities or []):
            if not isinstance(device, dict):
                continue
            device_id = str(
                device.get("id")
                or device.get("deviceId")
                or ""
            ).strip()
            label = str(
                device.get("label")
                or device.get("name")
                or (f"Device {device_id}" if device_id else f"Device {index + 1}")
            ).strip()
            if not label:
                continue
            room = str(
                device.get("room")
                or device.get("roomName")
                or ""
            ).strip() or "Unassigned"
            key = device_id or f"label:{label.casefold()}"
            unique[key] = {
                "id": device_id or None,
                "label": label,
                "room": room,
            }

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in unique.values():
            grouped.setdefault(str(item["room"]), []).append({
                "id": item["id"],
                "label": item["label"],
            })

        rooms = []
        room_names = sorted(
            grouped,
            key=lambda value: (value == "Unassigned", value.casefold()),
        )
        for room in room_names:
            devices = sorted(
                grouped[room],
                key=lambda item: str(item.get("label") or "").casefold(),
            )
            rooms.append({
                "room": room,
                "count": len(devices),
                "devices": devices,
            })

        requested_group = str(arguments.get("group") or "").strip()
        matched_group: dict[str, Any] | None = None
        alternatives: list[dict[str, Any]] = []
        if requested_group:
            normalize = lambda value: re.sub(
                r"[^a-z0-9]+", "",
                str(value or "").casefold(),
            )
            wanted = normalize(requested_group)
            exact = [
                room
                for room in rooms
                if normalize(room.get("room")) == wanted
            ]
            if len(exact) == 1:
                matched_group = exact[0]
            elif not exact and wanted:
                fuzzy = [
                    room
                    for room in rooms
                    if (
                        wanted in normalize(room.get("room"))
                        or normalize(room.get("room")) in wanted
                    )
                ]
                if len(fuzzy) == 1:
                    matched_group = fuzzy[0]
                elif len(fuzzy) > 1:
                    alternatives = fuzzy

        data = {
            "count": len(unique),
            "rooms": rooms,
            "room_count": len(rooms),
            "complete": True,
            "read_scope": "authoritative device identity",
            "mode": "group" if requested_group else "summary",
            "requested_group": requested_group or None,
            "matched_group": matched_group,
            "alternatives": alternatives,
        }
        return MCPToolResult(
            DEVICE_INVENTORY_TOOL,
            arguments,
            {},
            json.dumps(data, ensure_ascii=False),
            data,
        )

    async def active_rooms(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._active_room_devices()
        if not self._tool_succeeded(source):
            return self._read_failure(ACTIVE_ROOMS_TOOL, arguments, source)
        rooms = active_room_summary(devices)
        data = {
            "active_rooms": rooms,
            "count": len(rooms),
            "definition": "motion=active OR light switch=on",
            "total_scanned": len(devices),
            "complete": True,
            "read_scope": "bulk live context",
        }
        return MCPToolResult(ACTIVE_ROOMS_TOOL, arguments, {}, json.dumps(data), data)

    async def active_switches(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._bulk_live_devices(
            {"switch"}, enrich_fallback_identity=True
        )
        if not self._tool_succeeded(source):
            return self._read_failure(ACTIVE_SWITCHES_TOOL, arguments, source)
        switches = active_non_light_switches(devices)
        data = {
            "switches": switches,
            "count": len(switches),
            "definition": "switch=on excluding light/bulb capabilities",
            "total_scanned": len(devices),
            "complete": True,
            "read_scope": "bulk live context",
        }
        return MCPToolResult(ACTIVE_SWITCHES_TOOL, arguments, {}, json.dumps(data), data)

    async def home_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._bulk_live_devices(
            {"presence", "motion", "switch", "contact", "lock", "battery"},
            enrich_fallback_identity=True,
        )
        if not self._tool_succeeded(source):
            return self._read_failure(HOME_SNAPSHOT_TOOL, arguments, source)

        context_source = (
            isinstance(source.arguments, dict)
            and source.arguments.get("resource") == LIVE_CONTEXT_RESOURCE_URI
        )
        presence: list[dict[str, Any]] = []
        tracked_presence: list[dict[str, Any]] = []
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
            is_home = presence_value in {"present", "home", "arrived", "true", "active"}
            presence_reporter = (
                "presencesensor" in capabilities or attrs.get("presence") is not None
            )
            person_presence = presence_reporter and not bool(
                capabilities & {"motionsensor", "occupancysensor", "switch", "actuator", "outlet"}
            )
            if person_presence and is_home:
                presence.append({**identity, "presence": attrs.get("presence")})
            if person_presence:
                tracked_presence.append(
                    {
                        **identity,
                        "presence": attrs.get("presence") or "unknown",
                        "home": is_home,
                    }
                )
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

            # The upstream bulk context resource intentionally does not carry rich
            # health/alert fields. Never turn that omission into a false "no alerts"
            # claim. When the complete-inventory fallback is used, retain the existing
            # exhaustive alert scan; otherwise mark alert coverage explicitly partial.
            if not context_source:
                health = str(
                    attrs.get("healthStatus")
                    or attrs.get("networkStatus")
                    or attrs.get("rtt")
                    or ""
                ).casefold()
                if health in {"offline", "unavailable", "timeout", "failed"}:
                    alerts.append({**identity, "status": health, "source": "connectivity"})
                hub_alerts = attrs.get("hubAlerts")
                if hub_alerts not in (None, "", "[]", []):
                    alerts.append({**identity, "status": hub_alerts, "source": "hub_alert"})

        lights = active_lights(devices)
        switches = active_non_light_switches(devices)
        rooms = active_room_summary(devices)
        sort_key = lambda item: str(item.get("label") or "").casefold()
        alerts_complete = not context_source
        data = {
            "presence": sorted(presence, key=sort_key),
            "tracked_presence": sorted(tracked_presence, key=sort_key),
            "active_motion": sorted(motion, key=sort_key),
            "lights_on": lights,
            "switches_on": switches,
            "active_rooms": rooms,
            "open_contacts": sorted(contacts, key=sort_key),
            "unlocked_locks": sorted(locks, key=sort_key),
            "low_batteries": sorted(low_batteries, key=sort_key),
            "alerts": sorted(alerts, key=sort_key),
            "alerts_complete": alerts_complete,
            "alerts_source": (
                "complete inventory" if alerts_complete else "not available from bulk live context"
            ),
            "counts": {
                "presence": len(presence),
                "active_motion": len(motion),
                "lights_on": len(lights),
                "switches_on": len(switches),
                "active_rooms": len(rooms),
                "open_contacts": len(contacts),
                "unlocked_locks": len(locks),
                "low_batteries": len(low_batteries),
                "alerts": len(alerts) if alerts_complete else None,
            },
            "total_scanned": len(devices),
            "complete": True,
            "read_scope": "bulk live context" if context_source else "complete inventory",
        }
        return MCPToolResult(HOME_SNAPSHOT_TOOL, arguments, {}, json.dumps(data), data)
