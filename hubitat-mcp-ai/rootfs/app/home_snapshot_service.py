"""Fast, complete whole-home snapshots built from two structural state planes.

Common household state comes from Hubitat's one-bulk-read ``hubitat://context``
resource. Health/attention state is read separately through ``hub_list_devices``
``format='context'`` with an explicit health-attribute projection. If either
context contract cannot prove complete coverage, the service falls back to the
established full inventory rather than weakening an exhaustive whole-home claim.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from device_read_contract import LIVE_CONTEXT_RESOURCE_URI
from device_state_summary import (
    active_lights,
    active_non_light_switches,
    active_room_summary,
    capability_names,
    device_attributes,
)
from mcp_client import HubitatMCPClient, MCPToolResult, tool_succeeded


HOME_SNAPSHOT_TOOL = "homebrain_home_snapshot"
HOME_STATE_ATTRIBUTES = frozenset(
    {"presence", "motion", "switch", "contact", "lock", "battery"}
)
HEALTH_ATTRIBUTES = ("healthStatus", "networkStatus", "rtt", "hubAlerts")
_HEALTH_PAGE_LIMIT = 200
_HEALTH_LINE = re.compile(
    r"^-\s+(?P<label>.*?)\s+\((?P<id>\d+),\s*(?P<room>[^)]*)\)"
)
_HEALTH_VALUE = re.compile(
    r"(?:^|,\s*)(healthStatus|networkStatus|rtt|hubAlerts)=(.*?)"
    r"(?=,\s*(?:healthStatus|networkStatus|rtt|hubAlerts)=|$)"
)

BulkReader = Callable[..., Awaitable[tuple[MCPToolResult, list[dict[str, Any]]]]]


class HomeSnapshotService:
    """Compose common live state and complete health state without a rich manifest."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
        *,
        bulk_live_devices: BulkReader,
        full_live_devices: BulkReader,
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence
        self._bulk_live_devices = bulk_live_devices
        self._full_live_devices = full_live_devices

    @staticmethod
    def _identity(device: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": device.get("id") or device.get("deviceId"),
            "label": device.get("label") or device.get("name"),
            "room": device.get("room") or device.get("roomName"),
        }

    @staticmethod
    def _is_person_tracker(device: dict[str, Any]) -> bool:
        """Distinguish personal presence trackers from fixed occupancy devices.

        PresenceSensor alone is not enough to call a device a person: mmWave and
        bridge-imported occupancy sensors can expose PresenceSensor too. A device
        that also advertises a fixed-environment/control capability remains an
        occupancy/device presence source instead of appearing in the people list.
        This is capability-driven and does not depend on labels such as FP2/Life360.
        """

        caps = capability_names(device)
        if "presencesensor" not in caps:
            return False
        fixed_device_caps = {
            "motionsensor",
            "occupancysensor",
            "contactsensor",
            "switch",
            "actuator",
            "outlet",
            "lock",
        }
        return not bool(caps & fixed_device_caps)

    @staticmethod
    def _page_data(result: MCPToolResult) -> dict[str, Any]:
        return result.data if isinstance(result.data, dict) else {}

    @classmethod
    def _parse_health_summary(
        cls,
        summary: Any,
    ) -> tuple[list[dict[str, Any]], bool]:
        if not isinstance(summary, str):
            return [], False
        devices: list[dict[str, Any]] = []
        complete = True
        for raw_line in summary.splitlines():
            line = raw_line.strip()
            if not line.startswith("-"):
                continue
            if "(state unavailable)" in line:
                complete = False
            match = _HEALTH_LINE.match(line)
            if match is None:
                complete = False
                continue
            attributes: dict[str, Any] = {}
            if "; " in line:
                state_text = line.split("; ", 1)[1]
                state_text = re.sub(
                    r"\s+\((?:state|capabilities) unavailable\)\s*$",
                    "",
                    state_text,
                )
                for attr_match in _HEALTH_VALUE.finditer(state_text):
                    attributes[attr_match.group(1)] = attr_match.group(2).strip()
            devices.append(
                {
                    "id": match.group("id"),
                    "label": match.group("label"),
                    "room": (
                        None
                        if match.group("room").strip().casefold() in {"", "no room"}
                        else match.group("room").strip()
                    ),
                    "currentStates": attributes,
                }
            )
        return devices, complete

    async def _projected_health_devices(
        self,
    ) -> tuple[MCPToolResult | None, list[dict[str, Any]], bool]:
        """Read health attributes for the whole visible population without detail mode."""

        all_devices: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        offset = 0
        expected_total: int | None = None
        pages = 0
        started = time.monotonic()
        last_result: MCPToolResult | None = None
        last_arguments: dict[str, Any] = {}

        while pages < 20:
            arguments = {
                "tool": "hub_list_devices",
                "args": {
                    "format": "context",
                    "attributeNames": list(HEALTH_ATTRIBUTES),
                    "limit": _HEALTH_PAGE_LIMIT,
                    "offset": offset,
                },
            }
            last_arguments = arguments
            result = await self.mcp.call_tool("hub_read_devices", arguments)
            last_result = result
            if not tool_succeeded(result):
                return result, [], False
            data = self._page_data(result)
            if (
                data.get("partial") is True
                or data.get("idsComplete") is False
                or data.get("truncated") is True
            ):
                return result, [], False
            try:
                page_count = int(data.get("count"))
                page_total = int(data.get("total"))
            except (TypeError, ValueError):
                return result, [], False
            if expected_total is None:
                expected_total = page_total
            elif expected_total != page_total:
                return result, [], False

            parsed, page_complete = self._parse_health_summary(data.get("summary"))
            if not page_complete or len(parsed) != page_count:
                return result, [], False
            for device in parsed:
                device_id = str(device.get("id") or "")
                if not device_id or device_id in seen_ids:
                    return result, [], False
                seen_ids.add(device_id)
                all_devices.append(device)

            pages += 1
            has_more = data.get("hasMore") is True
            if not has_more:
                complete = expected_total == len(all_devices)
                self._record_evidence(
                    "hub_read_devices",
                    last_arguments,
                    success=complete,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=(
                        f"{len(all_devices)} projected health-context device records "
                        f"across {pages} page(s)"
                    ),
                    evidence_kind="authoritative_state_snapshot",
                )
                return result, all_devices, complete

            try:
                next_offset = int(data.get("nextOffset"))
            except (TypeError, ValueError):
                return result, [], False
            if next_offset <= offset:
                return result, [], False
            offset = next_offset

        return last_result, [], False

    @staticmethod
    def _alerts(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for device in devices:
            attrs = device_attributes(device)
            identity = HomeSnapshotService._identity(device)
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
                alerts.append(
                    {**identity, "status": hub_alerts, "source": "hub_alert"}
                )
        return alerts

    @staticmethod
    def _read_failure(
        arguments: dict[str, Any], source: MCPToolResult | None
    ) -> MCPToolResult:
        text = source.text if source is not None else "Live device read failed"
        return MCPToolResult(
            HOME_SNAPSHOT_TOOL,
            arguments,
            {},
            text,
            {"error": text or "Live device read failed"},
            is_error=True,
        )

    async def snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        source, devices = await self._bulk_live_devices(
            set(HOME_STATE_ATTRIBUTES), enrich_fallback_identity=True
        )
        if not tool_succeeded(source):
            return self._read_failure(arguments, source)

        used_live_context = (
            isinstance(source.arguments, dict)
            and source.arguments.get("resource") == LIVE_CONTEXT_RESOURCE_URI
        )
        health_devices = devices
        read_scope = "complete inventory fallback"

        if used_live_context:
            health_source, projected_health, health_complete = (
                await self._projected_health_devices()
            )
            if health_complete:
                health_devices = projected_health
                read_scope = "bulk live context + projected health context"
            else:
                # A whole-home summary must never translate unknown health coverage
                # into "no alerts". Fall back to the established complete inventory.
                fallback_source, fallback_devices = await self._full_live_devices(
                    enrich_identity=True
                )
                if not tool_succeeded(fallback_source):
                    return self._read_failure(arguments, health_source or fallback_source)
                source = fallback_source
                devices = fallback_devices
                health_devices = fallback_devices
                read_scope = "complete inventory fallback"

        presence: list[dict[str, Any]] = []
        tracked_presence: list[dict[str, Any]] = []
        occupancy_presence: list[dict[str, Any]] = []
        motion: list[dict[str, Any]] = []
        contacts: list[dict[str, Any]] = []
        locks: list[dict[str, Any]] = []
        low_batteries: list[dict[str, Any]] = []

        for device in devices:
            attrs = device_attributes(device)
            identity = self._identity(device)
            presence_value = str(attrs.get("presence") or "").casefold()
            is_home = presence_value in {
                "present", "home", "arrived", "true", "active"
            }
            is_person = self._is_person_tracker(device)
            if is_person:
                tracked_presence.append(
                    {
                        **identity,
                        "presence": attrs.get("presence") or "unknown",
                        "home": is_home,
                    }
                )
                if is_home:
                    presence.append({**identity, "presence": attrs.get("presence")})
            elif attrs.get("presence") is not None:
                occupancy_presence.append(
                    {
                        **identity,
                        "presence": attrs.get("presence"),
                        "active": is_home,
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
                    int(battery_number)
                    if battery_number.is_integer()
                    else battery_number
                )
                low_batteries.append({**identity, "battery": rendered_battery})

        alerts = self._alerts(health_devices)
        lights = active_lights(devices)
        switches = active_non_light_switches(devices)
        rooms = active_room_summary(devices)
        sort_key = lambda item: str(item.get("label") or "").casefold()
        data = {
            "presence": sorted(presence, key=sort_key),
            "tracked_presence": sorted(tracked_presence, key=sort_key),
            "occupancy_presence": sorted(occupancy_presence, key=sort_key),
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
                "tracked_presence": len(tracked_presence),
                "occupancy_presence": len(occupancy_presence),
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
            "live_state_complete": True,
            "alerts_complete": True,
            "read_scope": read_scope,
            "complete": True,
        }
        return MCPToolResult(
            HOME_SNAPSHOT_TOOL,
            arguments,
            {},
            json.dumps(data, ensure_ascii=False),
            data,
        )


__all__ = ["HomeSnapshotService", "HOME_STATE_ATTRIBUTES", "HEALTH_ATTRIBUTES"]
