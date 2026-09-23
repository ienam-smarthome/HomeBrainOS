"""Deterministic adapter for bounded Hubitat device-event history reads.

The upstream MCP server exposes event history through ``hub_list_device_events``
inside the read-only device gateway. This service keeps that wire contract out
of model-authored JSON: it resolves one named device with the shared targeted
resolver, applies conservative bounds, and normalises the newest-first event
rows for the local presenter.

Event rows prove that a state transition was reported. They do not, by
themselves, prove which automation or person caused it, so this module never
adds causal conclusions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import html
import json
import re
import time
from typing import Any, Callable

from device_query_service import DeviceQueryService
from history_temporal_analysis import (
    analyze_state_intervals,
    analyze_state_intervals_in_window,
    boundary_event_evidence,
    window_event_evidence,
)
from history_time_windows import (
    active_history_window_request,
    required_history_hours,
    resolve_history_window,
)
from hub_timezone import HubTimezoneResolver, required_history_hours_absolute
from mcp_client import HubitatMCPClient, MCPToolResult
from mcp_client import tool_succeeded as _shared_tool_succeeded
from natural_datetime import normalize_iso_offset
from request_metrics import increment_active_metric


DEVICE_HISTORY_TOOL = "homebrain_device_history"
LOCATION_EVENTS_TOOL = "homebrain_location_events"
DEVICE_GATEWAY = "hub_read_devices"
EVENT_OPERATION = "hub_list_device_events"
_TARGET_RESOLUTION_FIELDS = [
    "id", "name", "label", "room", "capabilities", "attributes", "commands",
]

# Only reject well-known attributes when the resolved target positively exposes
# enough metadata to prove that the requested history dimension does not belong
# to that device. Unknown/custom driver attributes remain allowed.
_HISTORY_ATTRIBUTE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "motion": ("motionsensor",),
    "illuminance": ("illuminancemeasurement",),
    "contact": ("contactsensor",),
    "presence": ("presencesensor",),
    "switch": ("switch",),
    "temperature": ("temperaturemeasurement",),
    "humidity": ("relativehumiditymeasurement",),
    "power": ("powermeter",),
    "battery": ("battery",),
    "level": ("switchlevel",),
    "lock": ("lock",),
    "valve": ("valve",),
}


class DeviceHistoryService:
    """Resolve a device and read a bounded authoritative event window."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence
        self._now = now or (lambda: datetime.now().astimezone())
        self._hub_timezone = HubTimezoneResolver(
            self.mcp,
            self._record_evidence,
        )

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
    def _metadata_name(value: Any) -> str:
        if isinstance(value, dict):
            value = value.get("name") or value.get("attribute") or value.get("capability")
        return str(value or "").strip()

    @classmethod
    def _advertised_attribute_names(cls, target: dict[str, Any]) -> set[str]:
        raw = target.get("attributes")
        if isinstance(raw, dict):
            values = raw.keys()
        elif isinstance(raw, list):
            values = raw
        else:
            values = ()
        return {
            name.casefold()
            for item in values
            if (name := cls._metadata_name(item))
        }

    @classmethod
    def _advertised_capability_names(cls, target: dict[str, Any]) -> set[str]:
        raw = target.get("capabilities")
        values = raw if isinstance(raw, list) else ()
        names: set[str] = set()
        for item in values:
            name = cls._metadata_name(item)
            if not name:
                continue
            names.add(re.sub(r"[^a-z0-9]", "", name.casefold()))
        return names

    @classmethod
    def _unsupported_history_attribute(
        cls,
        target: dict[str, Any],
        attribute: str,
    ) -> dict[str, Any] | None:
        """Return proof that a well-known requested attribute is not advertised."""

        wanted = str(attribute or "").strip().casefold()
        required_capabilities = _HISTORY_ATTRIBUTE_CAPABILITIES.get(wanted)
        if not wanted or required_capabilities is None:
            return None

        attributes = cls._advertised_attribute_names(target)
        capabilities = cls._advertised_capability_names(target)
        if wanted in attributes:
            return None
        if any(capability in capabilities for capability in required_capabilities):
            return None

        # Capability lists are frequently incomplete for bridged/community
        # devices and cannot prove that an event attribute is impossible. Only
        # an explicit advertised attribute map gives us a safe negative scope:
        # T1, for example, exposes illuminance/temperature, so motion is a
        # provable mismatch; a legacy device exposing only capabilities remains
        # eligible for the established unfiltered-fetch + client-side filter.
        if not attributes:
            return None

        return {
            "unsupportedAttribute": attribute,
            "availableAttributes": sorted(attributes),
            "capabilities": sorted(
                cls._metadata_name(item)
                for item in (target.get("capabilities") or [])
                if cls._metadata_name(item)
            ),
        }

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
    def _producer(value: Any) -> dict[str, Any]:
        """Normalize Hubitat command-event producedBy HTML safely.

        The device-events endpoint exposes command rows with type=command and a
        producedBy field. Hubitat commonly returns that field as an anchor such
        as <a href='/installedapp/configure/583'>HomeKit Integration</a>.
        Keep the human label plus a bounded structural source id/type, never the
        raw HTML.
        """

        if isinstance(value, dict):
            raw_label = (
                value.get("label")
                or value.get("name")
                or value.get("displayName")
                or value.get("text")
            )
            raw_id = value.get("id") or value.get("appId") or value.get("deviceId")
            raw_type = value.get("type") or value.get("kind")
            result = {
                "label": str(raw_label or "").strip(),
                "id": str(raw_id or "").strip() or None,
                "type": str(raw_type or "").strip().casefold() or None,
            }
            return result if result["label"] else {}

        raw = str(value or "").strip()
        if not raw:
            return {}
        href_match = re.search(r"""href\s*=\s*['"]([^'"]+)['"]""", raw, re.I)
        label = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        href = href_match.group(1) if href_match else ""
        producer_type: str | None = None
        producer_id: str | None = None
        app_match = re.search(r"/installedapp/configure/(\d+)", href, re.I)
        device_match = re.search(r"/device/(?:edit|editDevice)/(\d+)", href, re.I)
        if app_match:
            producer_type = "app"
            producer_id = app_match.group(1)
        elif device_match:
            producer_type = "device"
            producer_id = device_match.group(1)
        return {
            "label": label,
            "id": producer_id,
            "type": producer_type,
        } if label else {}

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
            event = {
                "name": row.get("name") or row.get("attribute"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "description": (
                    row.get("description") or row.get("descriptionText")
                ),
                "date": row.get("date") or row.get("timestamp"),
                "isStateChange": row.get("isStateChange"),
            }
            # Preserve bounded provenance metadata from Hubitat's device event
            # endpoint. Command rows are especially valuable because producedBy
            # names the app/action that issued the command. These fields used to
            # be dropped before causal reasoning could see them.
            for key, aliases in {
                "source": ("source",),
                "type": ("type",),
                "triggered": ("triggered",),
                "physical": ("physical",),
                "digital": ("digital",),
                "deviceId": ("deviceId", "device_id"),
                "installedAppId": ("installedAppId", "installed_app_id", "appId"),
            }.items():
                for alias in aliases:
                    if alias in row and row.get(alias) not in {None, ""}:
                        event[key] = row.get(alias)
                        break
            producer = DeviceHistoryService._producer(
                row.get("producedBy")
                or row.get("produced_by")
                or row.get("producer")
            )
            if producer:
                event["producedBy"] = producer
            events.append(event)
            if len(events) >= limit:
                break
        return events

    @staticmethod
    def _event_datetime(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(normalize_iso_offset(text))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _source_complete_to_window_start(
        cls,
        events: list[dict[str, Any]],
        *,
        fetch_limit: int,
        window_start: datetime,
    ) -> bool:
        """Whether the returned newest-first page reaches the window boundary."""

        if len(events) < fetch_limit:
            return True
        timestamps = [
            parsed
            for parsed in (cls._event_datetime(item.get("date")) for item in events)
            if parsed is not None
        ]
        if not timestamps:
            return False
        return min(timestamps) <= window_start

    @staticmethod
    def _utc_offset_text(value: datetime) -> str | None:
        offset = value.strftime("%z")
        if not offset:
            return None
        return f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset

    async def _read_command_events(
        self,
        *,
        device_id: str,
        label: str,
        hours_back: int,
        actions: tuple[str, ...] = ("on", "off"),
    ) -> list[dict[str, Any]]:
        """Read command event rows with Hubitat producer metadata.

        Command history is a distinct event stream from switch state. Query the
        exact command names so high-churn power/RTT telemetry cannot crowd the
        causal rows out of a generic newest-first page. A zero-row result is not
        retried generically here; native-log provenance remains the established
        fallback when the upstream command filter is unavailable.
        """

        async def read_one(action: str) -> list[dict[str, Any]]:
            event_name = f"command-{action}"
            event_args = {
                "deviceId": str(device_id),
                "hoursBack": int(hours_back),
                "limit": 20,
                "attribute": event_name,
            }
            source_arguments = {"tool": EVENT_OPERATION, "args": event_args}
            started = time.monotonic()
            try:
                source = await self.mcp.call_tool(
                    DEVICE_GATEWAY,
                    source_arguments,
                )
            except Exception as exc:
                self._record_evidence(
                    DEVICE_GATEWAY,
                    source_arguments,
                    success=False,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                    supports_live_claim=True,
                    evidence_kind="authoritative_command_event_history",
                )
                return []

            success = _shared_tool_succeeded(source)
            rows = self._events(source.data, limit=20) if success else []
            rows = [
                row
                for row in rows
                if str(row.get("name") or "").casefold() == event_name
            ]
            self._record_evidence(
                DEVICE_GATEWAY,
                source_arguments,
                success=success,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{len(rows)} {event_name} events for {label!r}",
                supports_live_claim=True,
                evidence_kind="authoritative_command_event_history",
                details={
                    "label": label,
                    "eventName": event_name,
                    "events": rows[:12],
                    "eventCount": len(rows),
                } if success else None,
            )
            return rows

        increment_active_metric(
            "causal_command_producer_reads",
            len(actions),
        )
        batches = await asyncio.gather(
            *(read_one(action) for action in actions)
        )
        rows = [item for batch in batches for item in batch]
        rows.sort(
            key=lambda item: (
                self._event_datetime(item.get("date")).timestamp()
                if self._event_datetime(item.get("date")) is not None
                else float("-inf")
            ),
            reverse=True,
        )
        return rows


    @staticmethod
    def _fallback_resolution_name(requested: str) -> str | None:
        """Return one bounded broader lookup token for an exact-filter miss.

        This is not a natural-language intent parser. It only helps targeted
        device resolution recover from labels that omit a room/qualifier (for
        example a request such as ``bathroom fan`` when the actual labels are
        ``Fan Switch`` / ``Fan Boost``). The final non-numeric identifying token
        is used once and the result is surfaced as alternatives, never silently
        substituted as the requested device.
        """

        tokens = re.findall(r"[a-z0-9]+", str(requested or "").casefold())
        if len(tokens) < 2:
            return None
        for token in reversed(tokens):
            if token in {"the", "a", "an"} or token.isdigit() or len(token) < 3:
                continue
            if token != "".join(tokens):
                return token
        return None

    async def _fallback_candidates(self, fallback_name: str) -> list[str]:
        """Return up to three labels from one broader targeted Hubitat lookup.

        Deliberately do not run the fuzzy resolver over the broader token: a
        generic token such as ``fan`` can have several legitimate matches and the
        resolver may pick one semantically. This recovery path exists to expose
        those candidates for clarification, not to choose among them.
        """

        source_arguments = {
            "tool": "hub_list_devices",
            "args": {
                "labelFilter": fallback_name,
                "fields": list(_TARGET_RESOLUTION_FIELDS),
                "detailed": True,
            },
        }
        started = time.monotonic()
        try:
            source = await self.mcp.call_tool(DEVICE_GATEWAY, source_arguments)
        except Exception as exc:
            self._record_evidence(
                DEVICE_GATEWAY,
                source_arguments,
                success=False,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                supports_live_claim=False,
                evidence_kind="targeted_device_lookup",
            )
            return []
        success = _shared_tool_succeeded(source)
        candidates = (
            [
                item
                for item in (HubitatMCPClient._find_device_list(source.data) or [])
                if isinstance(item, dict)
            ]
            if success
            else []
        )
        self._record_evidence(
            DEVICE_GATEWAY,
            source_arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(candidates)} broader targeted device candidates",
            supports_live_claim=False,
            evidence_kind="targeted_device_lookup",
        )
        labels: list[str] = []
        for candidate in candidates:
            label = str(candidate.get("label") or candidate.get("name") or "").strip()
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= 3:
                break
        return labels

    async def location_events(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Read location/mode events, clipped to the active semantic window."""

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
        explicit_window = (
            arguments.get("time_window")
            if isinstance(arguments.get("time_window"), dict)
            else None
        )
        window_request = explicit_window or active_history_window_request()
        now = self._now()
        hub_timezone_name: str | None = None
        timezone_source = "runtime"
        time_window = None
        if window_request is not None:
            now, hub_timezone_name, timezone_source = (
                await self._hub_timezone.now_in_hub_timezone(self._now)
            )
            time_window = resolve_history_window(window_request, now=now)
            if time_window is not None:
                hours_back = max(
                    hours_back,
                    required_history_hours(time_window, now=now),
                    required_history_hours_absolute(time_window.start, now=now),
                )

        # Location history is a low-cardinality stream. During a semantic
        # investigation fetch the bounded local maximum before clipping so an
        # older in-window mode event cannot be pushed out by newer updates.
        fetch_limit = 50 if time_window is not None else limit
        event_args: dict[str, Any] = {
            "hoursBack": hours_back,
            "limit": fetch_limit,
        }
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

        success = _shared_tool_succeeded(source)
        source_events = (
            self._events(source.data, limit=fetch_limit)
            if success
            else []
        )
        filtered_events = source_events
        if time_window is not None:
            filtered_events = []
            for event in source_events:
                event_time = self._event_datetime(event.get("date"))
                if event_time is None:
                    continue
                if time_window.start <= event_time <= time_window.end:
                    filtered_events.append(event)
        events = filtered_events[:limit]

        window_label = time_window.label if time_window is not None else ""
        summary = f"{len(events)} location events"
        if window_label:
            summary += f" in {window_label}"
        self._record_evidence(
            DEVICE_GATEWAY,
            source_arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=summary,
            supports_live_claim=True,
            evidence_kind="authoritative_location_event_history",
            details=(
                {
                    "count": len(events),
                    "events": events,
                    "timeWindow": (
                        {
                            **time_window.as_dict(),
                            "timeZone": hub_timezone_name,
                            "timeZoneSource": timezone_source,
                        }
                        if time_window is not None
                        else None
                    ),
                }
                if success
                else None
            ),
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
            "sourceEventCount": len(source_events),
            "events": events,
            "newestFirst": True,
        }
        if time_window is not None:
            data["timeWindow"] = {
                **time_window.as_dict(),
                "timeZone": hub_timezone_name,
                "timeZoneSource": timezone_source,
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
        limit = self._integer(
            arguments.get("limit"),
            default=20,
            minimum=1,
            maximum=50,
        )
        explicit_small_limit = "limit" in arguments and limit <= 3
        default_hours_back = 168 if attribute and explicit_small_limit else 24
        hours_back = self._integer(
            arguments.get("hours_back"),
            default=default_hours_back,
            minimum=1,
            maximum=168,
        )

        explicit_window = (
            arguments.get("time_window")
            if isinstance(arguments.get("time_window"), dict)
            else None
        )
        window_request = explicit_window or active_history_window_request()
        now = self._now()
        hub_timezone_name: str | None = None
        timezone_source = "runtime"
        time_window = None

        # Resolve the device before paying for the authoritative timezone read.
        # An ambiguous/missing target cannot produce history anyway, so reading
        # hub_get_info first only adds latency to a clarification response.
        #
        # Deterministic host paths may already have a fresh authoritative
        # identity from HubitatMCPClient.get_device_identities(). In that narrow
        # case they can pass it as the private _resolved_target field and avoid
        # repeating a targeted hub_list_devices lookup. Model-authored schemas do
        # not expose this field, and ToolExecutor strips it from evidence receipts.
        normalized_attribute = str(attribute or "").strip().casefold()
        required_fields = (
            {"attributes", "capabilities"}
            if normalized_attribute in _HISTORY_ATTRIBUTE_CAPABILITIES
            else set()
        )
        required_capabilities = set(
            _HISTORY_ATTRIBUTE_CAPABILITIES.get(normalized_attribute, ())
        )
        resolved_target = arguments.get("_resolved_target")
        target = (
            dict(resolved_target)
            if isinstance(resolved_target, dict)
            else None
        )
        resolution_data: dict[str, Any] = {}
        if target is None:
            resolver = DeviceQueryService(self.mcp, self._record_evidence)
            resolution = await resolver.resolve_device(
                {"name": requested},
                required_fields=required_fields,
                required_capabilities=required_capabilities,
            )
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
            fallback_name = None
            # An exact label-filter miss can be too strict when the spoken name
            # contains a room/qualifier absent from the actual device label. Do
            # one smaller targeted lookup and surface all of its bounded choices;
            # never auto-select the broader match.
            if not alternatives:
                fallback_name = self._fallback_resolution_name(requested)
                if fallback_name:
                    alternatives.extend(await self._fallback_candidates(fallback_name))
            alternatives = list(dict.fromkeys(alternatives))[:3]
            error = "device is ambiguous" if alternatives else "device not found"
            data = {
                "success": False,
                "requested": requested,
                "error": error,
                "alternatives": alternatives,
                "resolutionReason": resolution_data.get("reason"),
                "fallbackLookup": fallback_name,
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

        unsupported = self._unsupported_history_attribute(target, attribute)
        if unsupported is not None:
            increment_active_metric("history_attribute_rejected")
            available = unsupported.get("availableAttributes") or []
            available_text = ", ".join(map(str, available[:12])) or "not exposed"
            data = {
                "success": False,
                "requested": requested,
                "deviceId": str(device_id) if device_id not in {None, ""} else None,
                "label": label,
                **unsupported,
                "error": (
                    f"{label!r} does not advertise history attribute {attribute!r}. "
                    f"Available attributes include: {available_text}. "
                    "Choose an attribute actually exposed by this device and retry; "
                    "do not use an unsupported attribute to infer absence."
                ),
            }
            return MCPToolResult(
                DEVICE_HISTORY_TOOL,
                arguments,
                {},
                json.dumps(data, ensure_ascii=False, default=str),
                data,
                is_error=True,
            )

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

        if window_request is not None:
            now, hub_timezone_name, timezone_source = (
                await self._hub_timezone.now_in_hub_timezone(self._now)
            )
        time_window = resolve_history_window(
            window_request,
            now=now,
        )
        if time_window is not None:
            # The upstream API has no start/end filter. Fetch enough history to
            # reach at least one hour before the semantic boundary, then clip
            # exactly in local deterministic arithmetic. The absolute-time
            # variant keeps this safe across DST fallback nights, where Python
            # wall-clock subtraction can otherwise under-count by one hour.
            hours_back = max(
                hours_back,
                required_history_hours(time_window, now=now),
                required_history_hours_absolute(time_window.start, now=now),
            )

        # Most driver-specific upstream attribute filters are not reliable
        # enough to trust as the sole source (a live-confirmed contact-filter
        # bug returned a clean empty list despite real contact events). Switch
        # history is the exception we intentionally exploit for causal subjects:
        # high-churn metering devices can push an older switch=on boundary out of
        # the newest 50 generic events entirely. Ask upstream for switch rows
        # first so the state boundary cannot be crowded out. If that scoped read
        # returns no rows, retry once unfiltered and keep the established local
        # filtering fallback.
        fetch_limit = 50 if attribute else limit
        attribute_cf = attribute.casefold() if attribute else ""
        upstream_scoped_attribute = "switch" if attribute_cf == "switch" else ""
        event_args: dict[str, Any] = {
            "deviceId": str(device_id),
            "hoursBack": hours_back,
            "limit": fetch_limit,
        }
        if upstream_scoped_attribute:
            event_args["attribute"] = upstream_scoped_attribute

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

        success = _shared_tool_succeeded(source)
        source_events = self._events(source.data, limit=fetch_limit) if success else []

        if success and upstream_scoped_attribute and not source_events:
            self._record_evidence(
                DEVICE_GATEWAY,
                source_arguments,
                success=True,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=(
                    f"0 upstream {upstream_scoped_attribute} events for {label!r}; "
                    "retrying unfiltered because driver-side filters can be incomplete"
                ),
                supports_live_claim=True,
                evidence_kind="authoritative_device_event_history",
            )
            fallback_args = {
                "deviceId": str(device_id),
                "hoursBack": hours_back,
                "limit": fetch_limit,
            }
            source_arguments = {"tool": EVENT_OPERATION, "args": fallback_args}
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
            success = _shared_tool_succeeded(source)
            source_events = (
                self._events(source.data, limit=fetch_limit)
                if success
                else []
            )

        filtered_events = source_events
        if attribute:
            filtered_events = [
                event
                for event in source_events
                if str(event.get("name") or "").casefold() == attribute_cf
            ]
        events = filtered_events[:limit]
        self._record_evidence(
            DEVICE_GATEWAY,
            source_arguments,
            success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(filtered_events)} device events for {label!r}",
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

        source_complete_to_start = False
        if time_window is not None:
            source_complete_to_start = self._source_complete_to_window_start(
                source_events,
                fetch_limit=fetch_limit,
                window_start=time_window.start,
            )

        temporal_analysis = None
        if attribute:
            if time_window is not None:
                temporal_analysis = analyze_state_intervals_in_window(
                    attribute,
                    filtered_events,
                    start=time_window.start,
                    end=time_window.end,
                    window_label=time_window.label,
                    source_complete_to_start=source_complete_to_start,
                    window_ongoing=time_window.ongoing,
                    source_integrity_verified=False,
                )
            else:
                temporal_analysis = analyze_state_intervals(attribute, events)

        command_events: list[dict[str, Any]] = []
        if (
            bool(arguments.get("_include_command_provenance"))
            and attribute_cf == "switch"
            and isinstance(temporal_analysis, dict)
        ):
            command_actions = (
                ("on",)
                if temporal_analysis.get("openActiveInterval") is True
                else ("on", "off")
            )
            command_events = await self._read_command_events(
                device_id=str(device_id),
                label=label,
                hours_back=hours_back,
                actions=command_actions,
            )

        # Preserve event rows close to deterministic interval boundaries from
        # the full fetched source page. Command rows are merged only for
        # boundary/window evidence so they can contribute direct producer
        # provenance without changing switch-state interval arithmetic.
        causal_source_events = [*source_events, *command_events]
        boundary_events = boundary_event_evidence(
            causal_source_events,
            temporal_analysis,
        )
        window_events = (
            window_event_evidence(
                causal_source_events,
                time_window.as_dict(),
            )
            if time_window is not None
            else []
        )
        causation_available = any(
            isinstance(event.get("producedBy"), dict)
            and str(event["producedBy"].get("label") or "").strip()
            for event in command_events
        )

        data = {
            "success": True,
            "requested": requested,
            "deviceId": str(device_id),
            "label": label,
            "room": target.get("room") or target.get("roomName"),
            "capabilities": [
                self._metadata_name(item)
                for item in (target.get("capabilities") or [])
                if self._metadata_name(item)
            ],
            "hoursBack": hours_back,
            "attribute": attribute or None,
            "count": len(events),
            "sourceEventCount": len(source_events),
            "analysisEventCount": len(filtered_events) if attribute else len(events),
            "events": events,
            "newestFirst": True,
            "causationAvailable": causation_available,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
        }
        if time_window is not None:
            data["timeWindow"] = {
                **time_window.as_dict(),
                "timeZone": hub_timezone_name,
                "timeZoneSource": timezone_source,
                "startUtcOffset": self._utc_offset_text(time_window.start),
                "endUtcOffset": self._utc_offset_text(time_window.end),
                "sourceCompleteToStart": source_complete_to_start,
                "sourcePageCompleteToStart": source_complete_to_start,
            }
        if temporal_analysis is not None:
            data["temporalAnalysis"] = temporal_analysis
        if command_events:
            data["commandEvents"] = command_events[:24]
            data["commandEventsTruncated"] = len(command_events) > 24
        if window_events:
            data["windowEvents"] = window_events
        if boundary_events:
            data["boundaryEvents"] = boundary_events
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
