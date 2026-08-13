"""Deterministic adapter for bounded Hubitat device-event history reads.

The upstream MCP server exposes event history through ``hub_list_device_events``
inside the read-only device gateway.  This service keeps that wire contract out
of model-authored JSON: it resolves one named device with the shared targeted
resolver, applies conservative bounds, and normalises the newest-first event
rows for the local presenter.

Event rows prove that a state transition was reported.  They do not, by
themselves, prove which automation or person caused it, so this module never
adds causal conclusions.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from device_query_service import DeviceQueryService
from mcp_client import HubitatMCPClient, MCPToolResult
from mcp_client import tool_succeeded as _shared_tool_succeeded


DEVICE_HISTORY_TOOL = "homebrain_device_history"
LOCATION_EVENTS_TOOL = "homebrain_location_events"
DEVICE_GATEWAY = "hub_read_devices"
EVENT_OPERATION = "hub_list_device_events"


class DeviceHistoryService:
    """Resolve a device and read a bounded authoritative event window."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence

    @staticmethod
    def _integer(
        value: Any,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return min(maximum, max(minimum, parsed))

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        """Unwrap the common MCP result envelopes without guessing row fields."""

        current = value
        for _ in range(4):
            if not isinstance(current, dict):
                return {}
            if isinstance(current.get("events"), list):
                return current
            nested = next(
                (
                    current[key]
                    for key in ("result", "data", "output")
                    if isinstance(current.get(key), dict)
                ),
                None,
            )
            if nested is None:
                return current
            current = nested
        return current if isinstance(current, dict) else {}

    @staticmethod
    def _events(value: Any, *, limit: int) -> list[dict[str, Any]]:
        payload = DeviceHistoryService._payload(value)
        rows = payload.get("events")
        if not isinstance(rows, list):
            return []
        events: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            events.append({
                "name": row.get("name") or row.get("attribute"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "description": (
                    row.get("description") or row.get("descriptionText")
                ),
                "date": row.get("date") or row.get("timestamp"),
                "isStateChange": row.get("isStateChange"),
            })
            if len(events) >= limit:
                break
        return events

    async def location_events(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Read the hub's own location-scoped event stream (mode changes,
        sunrise/sunset, HSM, hub variables) -- confirmed live to be the
        exact same rows the hub's own Logs > Location events page shows.

        This is the same ``hub_list_device_events`` operation ``history()``
        uses for a single device's events, but called with both
        ``deviceId`` and ``appId`` omitted, which is the documented
        upstream contract for location events rather than a device- or
        app-scoped read. No device resolution is needed since this isn't
        about any one device.
        """

        hours_back = self._integer(
            arguments.get("hours_back"),
            default=24,
            minimum=1,
            maximum=168,
        )
        limit = self._integer(
            arguments.get("limit"),
            default=20,
            minimum=1,
            maximum=50,
        )
        event_args: dict[str, Any] = {"hoursBack": hours_back, "limit": limit}
        source_arguments = {"tool": EVENT_OPERATION, "args": event_args}
        started = time.monotonic()
        try:
            source = await self.mcp.call_tool(DEVICE_GATEWAY, source_arguments)
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            self._record_evidence(
                DEVICE_GATEWAY,
                source_arguments,
                success=False,
                elapsed_ms=elapsed_ms,
                summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                supports_live_claim=True,
                evidence_kind="authoritative_location_event_history",
            )
            data = {"success": False, "error": str(exc)[:500]}
            return MCPToolResult(
                LOCATION_EVENTS_TOOL,
                arguments,
                {},
                json.dumps(data),
                data,
                is_error=True,
            )

        # Delegates to the shared helper rather than repeating a strict
        # `is False` check here -- Hubitat/this codebase's own tool
        # results also transmit boolean-ish flags as the string "false",
        # which a strict identity check would silently miss (see
        # tool_succeeded()'s own docstring for the fuller history of this
        # bug class).
        success = _shared_tool_succeeded(source)
        events = self._events(source.data, limit=limit) if success else []
        self._record_evidence(
            DEVICE_GATEWAY,
            source_arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(events)} location events",
            supports_live_claim=True,
            evidence_kind="authoritative_location_event_history",
        )
        if not success:
            data = {
                "success": False,
                "error": source.text or "Hubitat location-event read failed",
            }
            return MCPToolResult(
                LOCATION_EVENTS_TOOL,
                arguments,
                source.raw,
                json.dumps(data),
                data,
                is_error=True,
            )

        data = {
            "success": True,
            "hoursBack": hours_back,
            "count": len(events),
            "events": events,
            "newestFirst": True,
        }
        return MCPToolResult(
            LOCATION_EVENTS_TOOL,
            arguments,
            source.raw,
            json.dumps(data, ensure_ascii=False, default=str),
            data,
        )

    async def history(self, arguments: dict[str, Any]) -> MCPToolResult:
        requested = str(arguments.get("name") or "").strip()
        if not requested:
            return MCPToolResult(
                DEVICE_HISTORY_TOOL,
                arguments,
                {},
                "Device name required",
                {"error": "name is required"},
                is_error=True,
            )

        attribute = str(arguments.get("attribute") or "").strip()
        # Live-observed bug (2026-08-13): "When did the front door last
        # open?" and its "before that" follow-up both answered "No contact
        # events were reported...in the last 24 hours" -- even though real
        # contact events existed, just further back than 24 hours. The
        # model had asked for a single attribute (exactly what the tool's
        # own description tells it to do for a "last X" point question) but
        # never explicitly widened the window, so it silently inherited the
        # generic 24-hour default meant for open-ended "what happened"
        # questions. A "last <state>" question has no natural window at
        # all -- it wants the most recent matching event whenever it
        # occurred -- so when the caller has scoped to one attribute and
        # left hours_back unset, default to the full seven-day bound
        # instead of one day. This costs nothing: the result is still
        # capped by ``limit`` (small for point questions per the tool's own
        # guidance), so a genuinely recent event is reported exactly as
        # before -- only the false "no events" negative goes away.
        default_hours_back = 168 if attribute else 24
        hours_back = self._integer(
            arguments.get("hours_back"),
            default=default_hours_back,
            minimum=1,
            maximum=168,
        )
        limit = self._integer(
            arguments.get("limit"),
            default=20,
            minimum=1,
            maximum=50,
        )

        resolver = DeviceQueryService(self.mcp, self._record_evidence)
        resolution = await resolver.resolve_device({"name": requested})
        resolution_data = (
            resolution.data if isinstance(resolution.data, dict) else {}
        )
        target = (
            resolution_data.get("target")
            if isinstance(resolution_data.get("target"), dict)
            else None
        )
        if target is None:
            alternatives = [
                str(item)
                for item in resolution_data.get("alternatives") or []
                if str(item).strip()
            ]
            data = {
                "success": False,
                "requested": requested,
                "error": "device could not be resolved uniquely",
                "alternatives": alternatives[:3],
            }
            return MCPToolResult(
                DEVICE_HISTORY_TOOL,
                arguments,
                {},
                json.dumps(data),
                data,
                is_error=True,
            )

        device_id = target.get("id") or target.get("deviceId")
        label = str(target.get("label") or target.get("name") or requested)
        if device_id in {None, ""}:
            data = {
                "success": False,
                "requested": requested,
                "label": label,
                "error": "resolved device has no stable Hubitat ID",
            }
            return MCPToolResult(
                DEVICE_HISTORY_TOOL,
                arguments,
                {},
                json.dumps(data),
                data,
                is_error=True,
            )

        event_args: dict[str, Any] = {
            "deviceId": str(device_id),
            "hoursBack": hours_back,
            "limit": limit,
        }
        if attribute:
            event_args["attribute"] = attribute
        source_arguments = {
            "tool": EVENT_OPERATION,
            "args": event_args,
        }
        started = time.monotonic()
        try:
            source = await self.mcp.call_tool(DEVICE_GATEWAY, source_arguments)
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            self._record_evidence(
                DEVICE_GATEWAY,
                source_arguments,
                success=False,
                elapsed_ms=elapsed_ms,
                summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                supports_live_claim=True,
                evidence_kind="authoritative_device_event_history",
            )
            data = {
                "success": False,
                "requested": requested,
                "deviceId": str(device_id),
                "label": label,
                "error": str(exc)[:500],
            }
            return MCPToolResult(
                DEVICE_HISTORY_TOOL,
                arguments,
                {},
                json.dumps(data),
                data,
                is_error=True,
            )

        # Delegates to the shared helper rather than repeating a strict
        # `is False` check here -- Hubitat/this codebase's own tool
        # results also transmit boolean-ish flags as the string "false",
        # which a strict identity check would silently miss (see
        # tool_succeeded()'s own docstring for the fuller history of this
        # bug class).
        success = _shared_tool_succeeded(source)
        events = self._events(source.data, limit=limit) if success else []
        self._record_evidence(
            DEVICE_GATEWAY,
            source_arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(events)} device events for {label!r}",
            supports_live_claim=True,
            evidence_kind="authoritative_device_event_history",
        )
        if not success:
            data = {
                "success": False,
                "requested": requested,
                "deviceId": str(device_id),
                "label": label,
                "error": source.text or "Hubitat event-history read failed",
            }
            return MCPToolResult(
                DEVICE_HISTORY_TOOL,
                arguments,
                source.raw,
                json.dumps(data),
                data,
                is_error=True,
            )

        data = {
            "success": True,
            "requested": requested,
            "deviceId": str(device_id),
            "label": label,
            "hoursBack": hours_back,
            "attribute": attribute or None,
            "count": len(events),
            "events": events,
            "newestFirst": True,
            "causationAvailable": False,
        }
        return MCPToolResult(
            DEVICE_HISTORY_TOOL,
            arguments,
            source.raw,
            json.dumps(data, ensure_ascii=False, default=str),
            data,
        )


__all__ = [
    "DEVICE_GATEWAY",
    "DEVICE_HISTORY_TOOL",
    "EVENT_OPERATION",
    "LOCATION_EVENTS_TOOL",
    "DeviceHistoryService",
]
