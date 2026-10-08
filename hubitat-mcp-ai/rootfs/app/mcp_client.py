from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from device_read_contract import (
    LIVE_CONTEXT_RESOURCE_URI,
    device_read_plan,
    live_context_is_complete,
    normalize_hub_list_devices_arguments,
    projected_state_shape_is_usable,
)
from mcp_retry_metrics import record_mcp_retry_attempt
from request_metrics import (
    add_active_metric_ms,
    increment_active_metric,
    observe_active_metric_max,
)

logger = logging.getLogger(__name__)


class MCPError(RuntimeError):
    pass


@dataclass(slots=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] = field(default_factory=dict)

    def as_function_tool(self) -> dict[str, Any]:
        schema = self.input_schema if isinstance(self.input_schema, dict) else {}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or self.name,
                "parameters": schema or {"type": "object", "properties": {}},
            },
        }


@dataclass(slots=True)
class MCPToolResult:
    name: str
    arguments: dict[str, Any]
    raw: dict[str, Any]
    text: str
    data: Any
    is_error: bool = False


def _is_false_flag(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, str) and value.strip().casefold() == "false"


def tool_succeeded(result: MCPToolResult) -> bool:
    if result.is_error:
        return False
    data = result.data
    if isinstance(data, dict):
        if _is_false_flag(data.get("success")) or data.get("error"):
            return False
        for key in ("result", "data", "output"):
            nested = data.get(key)
            if isinstance(nested, dict) and (
                _is_false_flag(nested.get("success")) or nested.get("error")
            ):
                return False
    return True


class HubitatMCPClient:
    """Small Streamable-HTTP MCP client tailored to Hubitat's local endpoint."""

    _MAX_DEVICE_PAGES = 200

    def __init__(
        self,
        endpoint_url: str,
        access_token: str = "",
        timeout_seconds: float = 25,
        device_cache_seconds: float = 12,
        identity_cache_seconds: float = 120,
        max_concurrent_calls: int = 2,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.endpoint_url = self._with_token(endpoint_url.strip(), access_token.strip())
        self.timeout_seconds = max(3.0, float(timeout_seconds))
        self.device_cache_seconds = max(0.0, float(device_cache_seconds))
        self.identity_cache_seconds = max(0.0, float(identity_cache_seconds))
        self.max_concurrent_calls = max(1, min(8, int(max_concurrent_calls)))
        self.retry_attempts = max(1, min(5, int(retry_attempts)))
        self.retry_backoff_seconds = max(
            0.0, min(5.0, float(retry_backoff_seconds))
        )
        self._clock = clock
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "User-Agent": "Hubitat-MCP-AI/0.1",
            },
        )
        self._session_id: str | None = None
        self._request_id = 0
        self._initialized = False
        self._tools: dict[str, MCPTool] = {}
        # Session/tool-catalog mutations stay serialized. Ordinary MCP
        # operations use a separate bounded semaphore below so independent
        # reads and verified writes can overlap safely after initialization.
        self._lock = asyncio.Lock()
        self._snapshot_lock = asyncio.Lock()
        self._request_semaphore = asyncio.Semaphore(self.max_concurrent_calls)
        self._active_requests = 0
        self.server_info: dict[str, Any] = {}
        self._cached_devices: list[dict[str, Any]] = []
        self._devices_cached_at = 0.0
        self._live_device_snapshot_ttl_seconds = 2.0
        self._live_device_snapshot: tuple[float, int, MCPToolResult] | None = None
        self._live_context_ttl_seconds = 2.0
        self._live_context_snapshot: tuple[float, int, dict[str, Any]] | None = None
        self._live_context_inflight: tuple[
            int, asyncio.Task[dict[str, Any]]
        ] | None = None
        self._live_device_snapshot_generation = 0
        self._device_manifest_inflight: asyncio.Task[list[dict[str, Any]]] | None = None

    @staticmethod
    def _with_token(url: str, token: str) -> str:
        if not url:
            return ""
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if token and not query.get("access_token"):
            query["access_token"] = token
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @property
    def configured(self) -> bool:
        return self.endpoint_url.startswith(("http://", "https://"))

    async def close(self) -> None:
        await self._http.aclose()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"online": False, "error": "MCP endpoint is not configured"}
        try:
            await self.initialize()
            tools = await self.list_tools()
            return {
                "online": True,
                "tools": len(tools),
                "server": self.server_info,
                "session": bool(self._session_id),
            }
        except Exception as exc:
            return {"online": False, "error": str(exc)}

    async def initialize(self, force: bool = False) -> None:
        if self._initialized and not force:
            return
        if not self.configured:
            raise MCPError("Hubitat MCP endpoint is not configured")

        lock_started = time.monotonic()
        await self._lock.acquire()
        session_wait_ms = (time.monotonic() - lock_started) * 1000
        if session_wait_ms >= 1:
            add_active_metric_ms("mcp_session_lock_wait", session_wait_ms)
        try:
            if self._initialized and not force:
                return
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "Hubitat MCP AI",
                        "version": "0.1.0",
                    },
                },
            }
            response = await self._post(payload)
            result = self._rpc_result(response)
            self.server_info = result.get("serverInfo") or {}
            self._initialized = True

            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            try:
                await self._post(notification, allow_empty=True)
            except Exception:
                pass
        finally:
            self._lock.release()

    async def list_tools(self, refresh: bool = False) -> list[MCPTool]:
        await self.initialize()
        if self._tools and not refresh:
            return list(self._tools.values())

        lock_started = time.monotonic()
        await self._lock.acquire()
        session_wait_ms = (time.monotonic() - lock_started) * 1000
        if session_wait_ms >= 1:
            add_active_metric_ms("mcp_session_lock_wait", session_wait_ms)
        try:
            if self._tools and not refresh:
                return list(self._tools.values())
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            }
            response = await self._post(payload)
            result = self._rpc_result(response)
            tools = result.get("tools") or []
            parsed: dict[str, MCPTool] = {}
            for item in tools:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                tool = MCPTool(
                    name=str(item["name"]),
                    description=str(item.get("description") or ""),
                    input_schema=item.get("inputSchema") or {
                        "type": "object",
                        "properties": {},
                    },
                    output_schema=item.get("outputSchema") or {},
                    annotations=item.get("annotations") or {},
                )
                parsed[tool.name] = tool
            self._tools = parsed
            return list(parsed.values())
        finally:
            self._lock.release()

    async def get_tool(self, name: str) -> MCPTool | None:
        await self.list_tools()
        return self._tools.get(name)

    def peek_cached_devices(self) -> list[dict[str, Any]]:
        """Return the current detailed manifest without triggering a hub read."""

        return [dict(item) for item in self._cached_devices]

    def _identity_cache_fresh(self, cached_at: float) -> bool:
        if cached_at <= 0:
            return False
        return self._clock() - cached_at < self.identity_cache_seconds

    def peek_device_identities(self) -> list[dict[str, Any]]:
        """Return a fresh complete local identity snapshot without I/O.

        Identity/capability data is allowed to live longer than current-state
        data, but it must not remain authoritative forever. A stale structural
        snapshot can contain removed devices, old room membership, or renamed
        entities and therefore corrupt host-owned target grounding.

        Consider the detailed manifest and complete device/context snapshots,
        but only while each source is inside the dedicated identity TTL, and
        choose the freshest complete source. Returning an empty list for stale
        sources lets the caller perform one
        bounded refresh instead of silently grounding a mutation to old data.
        """

        candidates: list[tuple[float, list[dict[str, Any]]]] = []
        if self._cached_devices and self._identity_cache_fresh(self._devices_cached_at):
            candidates.append((
                self._devices_cached_at,
                [dict(item) for item in self._cached_devices],
            ))

        generation = self._live_device_snapshot_generation
        if self._live_device_snapshot is not None:
            cached_at, cached_generation, cached_result = self._live_device_snapshot
            if (
                cached_generation == generation
                and self._identity_cache_fresh(cached_at)
            ):
                devices = self._find_device_list(cached_result.data)
                if isinstance(devices, list) and devices:
                    candidates.append((
                        cached_at,
                        [dict(item) for item in devices if isinstance(item, dict)],
                    ))

        if self._live_context_snapshot is not None:
            cached_at, cached_generation, cached_context = self._live_context_snapshot
            if (
                cached_generation == generation
                and self._identity_cache_fresh(cached_at)
            ):
                devices = self._find_device_list(cached_context)
                if isinstance(devices, list) and devices:
                    candidates.append((
                        cached_at,
                        [dict(item) for item in devices if isinstance(item, dict)],
                    ))

        if not candidates:
            return []
        _cached_at, identities = max(candidates, key=lambda item: item[0])
        return identities

    def peek_cached_live_context_devices(self) -> list[dict[str, Any]]:
        """Return a fresh cached live-context device snapshot without I/O.

        This accessor exists for structural enrichment only. Callers may reuse
        room/capability/attribute *shape* while the snapshot is inside the
        identity TTL, but must not treat the returned state values as a current
        live-state read. Generation invalidation still clears the snapshot after
        writes.
        """

        snapshot = self._live_context_snapshot
        if snapshot is None:
            return []

        cached_at, cached_generation, cached_context = snapshot
        if (
            cached_generation != self._live_device_snapshot_generation
            or not self._identity_cache_fresh(cached_at)
        ):
            return []

        devices = self._find_device_list(cached_context)
        if not isinstance(devices, list):
            return []
        return [
            dict(item)
            for item in devices
            if isinstance(item, dict)
        ]

    async def get_cached_devices(self, refresh: bool = False) -> list[dict[str, Any]]:
        """Return a short-lived detailed device manifest and coalesce refreshes."""

        now = self._clock()
        if (
            not refresh
            and self._cached_devices
            and now - self._devices_cached_at < self.device_cache_seconds
        ):
            return list(self._cached_devices)

        inflight = self._device_manifest_inflight
        if inflight is not None and not inflight.done():
            wait_started = time.monotonic()
            try:
                devices = await asyncio.shield(inflight)
            finally:
                add_active_metric_ms(
                    "mcp_shared_wait", (time.monotonic() - wait_started) * 1000
                )
            return [dict(item) for item in devices]

        task = asyncio.create_task(
            self._refresh_cached_devices(),
            name="hubitat-device-manifest-refresh",
        )
        self._device_manifest_inflight = task
        try:
            devices = await asyncio.shield(task)
            return [dict(item) for item in devices]
        finally:
            if self._device_manifest_inflight is task:
                self._device_manifest_inflight = None

    async def get_audit_devices(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch fresh health evidence without command metadata or cache pollution.

        The detailed command-capable manifest remains untouched. Concurrent
        page reads are permitted only when the gateway explicitly reports a
        numeric total and advancing page offsets. Failed/incomplete reads fall
        back to the existing fully refreshed detailed manifest, never a stale
        identity cache or a partially returned audit result.
        """
        started = time.monotonic()
        generation = self._live_device_snapshot_generation
        pages_fetched = 0

        async def fallback(reason: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            devices = await self.get_cached_devices(refresh=True)
            return list(devices), {
                "source": "full_detailed_fallback",
                "reason": reason,
                "pages": pages_fetched,
                "read_elapsed_ms": round((time.monotonic() - started) * 1000),
                "complete": False,  # no separate proof of projection coverage
            }

        tools = {tool.name for tool in await self.list_tools()}
        if "hub_read_devices" not in tools:
            return await fallback("projected_gateway_unavailable")

        plan = device_read_plan(
            include_states=True,
            include_capabilities=True,
            include_last_activity=True,
        )
        page_size = 50

        async def page_at(offset: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
            nonlocal pages_fetched
            args = {
                "tool": "hub_list_devices",
                "args": plan.arguments(limit=page_size, offset=offset),
            }
            result = await self.call_tool("hub_read_devices", args)
            pages_fetched += 1
            if not tool_succeeded(result):
                raise MCPError("projected page request was rejected")
            page = self._find_device_page(result.data)
            devices = self._find_device_list(result.data)
            if devices is None or not all(isinstance(item, dict) for item in devices):
                raise MCPError("projected page lacks a device list")
            if not projected_state_shape_is_usable(devices, plan.state_field):
                raise MCPError("projected page lacks required device attributes")
            return page, devices

        try:
            first_page, first_devices = await page_at(0)
            if first_page is None:
                raise MCPError("projected list has no pagination metadata")
            value = first_page.get("total", first_page.get("totalDevices"))
            total = None
            if value is not None and not isinstance(value, bool):
                try:
                    total = int(value)
                except (ValueError, TypeError):
                    pass
            has_more = first_page.get("hasMore") is True
            if not has_more:
                if total is None and first_page.get("hasMore") is not False:
                    raise MCPError("page lacks terminal marker or a verified total")
                if total is not None and total != len(first_devices):
                    raise MCPError("one-page result disagrees with total")
                devices = first_devices
                mode = "one_page"
            else:
                next_offset = first_page.get("nextOffset")
                try:
                    offset = int(next_offset)
                except (ValueError, TypeError):
                    raise MCPError("missing advancing nextOffset")
                if offset <= 0:
                    raise MCPError("pagination did not advance")

                if total is not None and 0 < total <= self._MAX_DEVICE_PAGES * page_size:
                    # Only parallelise pages when the server supplies a total
                    # and the first page advances by exactly the requested size.
                    if offset != page_size or len(first_devices) != page_size:
                        raise MCPError("unexpected first-page boundary")
                    offsets = list(range(offset, total, page_size))
                    if len(offsets) + 1 > self._MAX_DEVICE_PAGES:
                        raise MCPError("pagination exceeds hard page cap")
                    bounded = asyncio.Semaphore(self.max_concurrent_calls)

                    async def fetch(offset: int):
                        async with bounded:
                            return await page_at(offset)

                    results = await asyncio.gather(
                        *(fetch(item) for item in offsets)
                    )
                    devices = list(first_devices)
                    for index, (page, rows) in enumerate(results):
                        requested_offset = offsets[index]
                        if page is None:
                            raise MCPError("page missing pagination metadata")
                        expected_count = min(page_size, total - requested_offset)
                        if len(rows) != expected_count:
                            raise MCPError("page size changed during audit")
                        if requested_offset + expected_count < total:
                            if page.get("hasMore") is not True:
                                raise MCPError("pagination ended before reported total")
                            if int(page.get("nextOffset") or 0) != requested_offset + page_size:
                                raise MCPError("unexpected next page offset")
                        elif page.get("hasMore") is True:
                            raise MCPError("pagination continued past reported total")
                        devices.extend(rows)
                    mode = "bounded_parallel_pages"
                else:
                    # No trustworthy total: follow the server's advancing
                    # offsets, sequentially, and reject incomplete cursors.
                    devices = list(first_devices)
                    current_offset = 0
                    page = first_page
                    while page.get("hasMore") is True:
                        if pages_fetched >= self._MAX_DEVICE_PAGES:
                            raise MCPError("pagination exceeded hard page cap")
                        requested = int(page.get("nextOffset") or 0)
                        if requested <= current_offset:
                            raise MCPError("pagination offset did not advance")
                        current_offset = requested
                        page, rows = await page_at(requested)
                        if page is None:
                            raise MCPError("page missing pagination metadata")
                        devices.extend(rows)
                    mode = "verified_serial_pages"

            identifiers = [
                str(item.get("id") or item.get("deviceId") or "")
                for item in devices
            ]
            if (
                not devices
                or any(not identifier for identifier in identifiers)
                or len(identifiers) != len(set(identifiers))
                or (total is not None and len(devices) != total)
                or generation != self._live_device_snapshot_generation
            ):
                raise MCPError("projected inventory identity/total verification failed")
            return list(devices), {
                "source": "fresh_projected_gateway",
                "mode": mode,
                "pages": pages_fetched,
                "devices": len(devices),
                "read_elapsed_ms": round((time.monotonic() - started) * 1000),
                "complete": True,
            }
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Fresh audit projection unavailable: %s", exc)
            return await fallback(type(exc).__name__)

    async def _refresh_cached_devices(self) -> list[dict[str, Any]]:
        generation = self._live_device_snapshot_generation
        tools = await self.list_tools()
        names = {tool.name for tool in tools}
        tool_name = next(
            (
                candidate
                for candidate in ("hub_list_devices", "get_devices", "list_devices")
                if candidate in names
            ),
            None,
        )
        arguments: dict[str, Any] = {}
        using_gateway = False
        if not tool_name and "hub_read_devices" in names:
            tool_name = "hub_read_devices"
            using_gateway = True
            plan = device_read_plan(
                include_states=True,
                include_capabilities=True,
                include_commands=True,
                include_last_activity=True,
            )
            arguments = {
                "tool": "hub_list_devices",
                "args": plan.arguments(limit=50, offset=0),
            }
        if not tool_name:
            return list(self._cached_devices)

        result = await self.call_tool(tool_name, arguments)
        value = self._find_device_list(result.data)
        if using_gateway:
            devices = list(value or [])
            page = self._find_device_page(result.data)
            current_offset = int(arguments["args"]["offset"])
            pages_fetched = 1
            while (
                page
                and page.get("hasMore") is True
                and page.get("nextOffset") is not None
                and pages_fetched < self._MAX_DEVICE_PAGES
            ):
                try:
                    next_offset = int(page["nextOffset"])
                except (TypeError, ValueError):
                    break
                if next_offset <= current_offset:
                    break
                current_offset = next_offset
                arguments["args"]["offset"] = current_offset
                result = await self.call_tool(tool_name, arguments)
                devices.extend(self._find_device_list(result.data) or [])
                page = self._find_device_page(result.data)
                pages_fetched += 1
            value = devices
        if isinstance(value, list):
            self._cached_devices = [item for item in value if isinstance(item, dict)]
            completed_at = self._clock()
            self._devices_cached_at = completed_at
            if (
                self._cached_devices
                and generation == self._live_device_snapshot_generation
            ):
                snapshot_result = self._device_snapshot_result(self._cached_devices)
                self._live_device_snapshot = (
                    completed_at,
                    generation,
                    snapshot_result,
                )
        return list(self._cached_devices)

    async def get_live_context(self, refresh: bool = False) -> dict[str, Any]:
        """Read the server's one-bulk-read live context resource.

        This is deliberately separate from the detailed device-manifest cache.
        The context resource carries the room/capability identity and common live
        states needed by aggregate reads, while the detailed manifest remains the
        source for commands, units, and richer metadata.
        """

        await self.initialize()
        generation = self._live_device_snapshot_generation
        if not refresh and self._live_context_snapshot is not None:
            cached_at, cached_generation, cached = self._live_context_snapshot
            if (
                cached_generation == generation
                and self._clock() - cached_at < self._live_context_ttl_seconds
            ):
                return deepcopy(cached)

        inflight = self._live_context_inflight
        if (
            inflight is not None
            and inflight[0] == generation
            and not inflight[1].done()
        ):
            wait_started = time.monotonic()
            try:
                value = await asyncio.shield(inflight[1])
            finally:
                add_active_metric_ms(
                    "mcp_shared_wait", (time.monotonic() - wait_started) * 1000
                )
            return deepcopy(value)

        task = asyncio.create_task(
            self._refresh_live_context(generation),
            name="hubitat-live-context-refresh",
        )
        self._live_context_inflight = (generation, task)
        try:
            value = await asyncio.shield(task)
            return deepcopy(value)
        finally:
            current = self._live_context_inflight
            if current is not None and current[1] is task:
                self._live_context_inflight = None

    async def _refresh_live_context(self, generation: int) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "resources/read",
            "params": {"uri": LIVE_CONTEXT_RESOURCE_URI},
        }
        response = await self._post_bounded(payload)
        result = self._rpc_result(response)

        contents = result.get("contents") or []
        text: str | None = None
        for item in contents if isinstance(contents, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("uri") == LIVE_CONTEXT_RESOURCE_URI and item.get("text") is not None:
                text = str(item.get("text"))
                break
        if text is None:
            raise MCPError("MCP live context resource returned no JSON content")
        try:
            value = json.loads(text)
        except Exception as exc:
            raise MCPError("MCP live context resource returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise MCPError("MCP live context resource was not a JSON object")
        if generation != self._live_device_snapshot_generation:
            raise MCPError("Live context was invalidated while it was being read")
        if live_context_is_complete(value):
            self._live_context_snapshot = (self._clock(), generation, deepcopy(value))
        return value

    async def get_device_identities(self) -> list[dict[str, Any]]:
        """Return fresh complete identity with the cheapest authoritative source.

        A warm structural cache avoids unnecessary hub traffic. Once that cache
        exceeds the identity TTL, refresh the one-shot bulk context first; it is
        much cheaper than the paginated detailed manifest and carries the room/
        capability identity needed for deterministic target grounding. Only when
        the bulk context is unavailable or incomplete do we refresh the detailed
        manifest. Stale identity is never silently promoted back to authoritative.
        """

        cached = self.peek_device_identities()
        if cached:
            increment_active_metric("identity_cache_hit")
            return cached

        increment_active_metric("identity_refresh")

        try:
            context = await self.get_live_context(refresh=True)
        except Exception as exc:
            logger.debug("Live context unavailable for identity refresh: %s", exc)
        else:
            if live_context_is_complete(context):
                devices = self._find_device_list(context)
                identities = [
                    dict(item) for item in (devices or []) if isinstance(item, dict)
                ]
                if identities:
                    return identities

        try:
            await self.get_cached_devices(refresh=True)
        except Exception as exc:
            logger.debug("Detailed manifest unavailable for identity refresh: %s", exc)
            return []

        # get_cached_devices() may legally preserve the previous manifest when
        # the server exposes no compatible detailed-list tool. Re-check the
        # timestamp rather than treating that stale fallback as authoritative.
        return self.peek_device_identities()

    @classmethod
    def _find_device_list(cls, value: Any) -> list[Any] | None:
        if isinstance(value, list):
            if not value or all(isinstance(item, dict) for item in value):
                return value
            return None
        if not isinstance(value, dict):
            return None
        for key in ("devices", "apps", "items", "results"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
        for key in ("result", "data", "output", "content"):
            if key in value:
                candidate = cls._find_device_list(value[key])
                if candidate is not None:
                    return candidate
        return None

    @classmethod
    def _find_device_page(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        if any(key in value for key in ("devices", "apps", "items", "results")):
            return value
        for key in ("result", "data", "output", "content"):
            if key in value:
                candidate = cls._find_device_page(value[key])
                if candidate is not None:
                    return candidate
        return None

    async def supported_arguments(
        self,
        tool_name: str,
        desired: dict[str, Any],
    ) -> dict[str, Any]:
        tool = await self.get_tool(tool_name)
        if not tool:
            return desired
        schema = tool.input_schema or {}
        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            return desired
        return {key: value for key, value in desired.items() if key in properties}

    @staticmethod
    def _is_live_device_snapshot_request(name: str, arguments: dict[str, Any]) -> bool:
        return (
            name == "hub_read_devices"
            and arguments.get("tool") == "hub_list_devices"
            and arguments.get("args") == {}
        )

    @staticmethod
    def _copy_tool_result(result: MCPToolResult) -> MCPToolResult:
        return MCPToolResult(
            name=result.name,
            arguments=deepcopy(result.arguments),
            raw=deepcopy(result.raw),
            text=result.text,
            data=deepcopy(result.data),
            is_error=result.is_error,
        )

    @staticmethod
    def _device_snapshot_result(devices: list[dict[str, Any]]) -> MCPToolResult:
        data = {"devices": deepcopy(devices)}
        return MCPToolResult(
            name="hub_read_devices",
            arguments={"tool": "hub_list_devices", "args": {}},
            raw={},
            text=json.dumps(data, ensure_ascii=False),
            data=data,
            is_error=False,
        )

    def invalidate_live_device_snapshot(self) -> None:
        self._live_device_snapshot_generation += 1
        self._live_device_snapshot = None
        self._live_context_snapshot = None

    async def _post_bounded(
        self,
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        """Send one ordinary MCP request through the bounded concurrency gate."""

        queue_started = time.monotonic()
        await self._request_semaphore.acquire()
        add_active_metric_ms(
            "mcp_queue_wait", (time.monotonic() - queue_started) * 1000
        )
        self._active_requests += 1
        observe_active_metric_max("mcp_concurrent_peak", self._active_requests)
        try:
            http_started = time.monotonic()
            try:
                return await self._post(payload, allow_empty=allow_empty)
            finally:
                add_active_metric_ms(
                    "mcp_http", (time.monotonic() - http_started) * 1000
                )
        finally:
            self._active_requests = max(0, self._active_requests - 1)
            self._request_semaphore.release()

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        await self.initialize()
        arguments = arguments if isinstance(arguments, dict) else {}
        expected_state_field = normalize_hub_list_devices_arguments(name, arguments)
        cacheable = self._is_live_device_snapshot_request(name, arguments)
        generation = self._live_device_snapshot_generation
        if cacheable and self._live_device_snapshot is not None:
            cached_at, cached_generation, cached_result = self._live_device_snapshot
            if (
                cached_generation == generation
                and self._clock() - cached_at < self._live_device_snapshot_ttl_seconds
            ):
                return self._copy_tool_result(cached_result)

        if cacheable:
            manifest_task = self._device_manifest_inflight
            if manifest_task is not None and not manifest_task.done():
                wait_generation = self._live_device_snapshot_generation
                wait_started = time.monotonic()
                try:
                    devices = await asyncio.shield(manifest_task)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    devices = []
                finally:
                    add_active_metric_ms(
                        "mcp_shared_wait", (time.monotonic() - wait_started) * 1000
                    )
                if (
                    devices
                    and wait_generation == self._live_device_snapshot_generation
                ):
                    shared_result = self._device_snapshot_result(devices)
                    self._live_device_snapshot = (
                        self._clock(),
                        wait_generation,
                        self._copy_tool_result(shared_result),
                    )
                    return shared_result

        if cacheable:
            shared_started = time.monotonic()
            await self._snapshot_lock.acquire()
            shared_wait_ms = (time.monotonic() - shared_started) * 1000
            if shared_wait_ms >= 1:
                add_active_metric_ms("mcp_shared_wait", shared_wait_ms)
            try:
                if self._live_device_snapshot is not None:
                    cached_at, cached_generation, cached_result = self._live_device_snapshot
                    if (
                        cached_generation == self._live_device_snapshot_generation
                        and self._clock() - cached_at < self._live_device_snapshot_ttl_seconds
                    ):
                        return self._copy_tool_result(cached_result)
                generation = self._live_device_snapshot_generation
                payload = {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "tools/call",
                    "params": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
                response = await self._post_bounded(payload)
                result = self._rpc_result(response)
            finally:
                self._snapshot_lock.release()
        else:
            generation = self._live_device_snapshot_generation
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments,
                },
            }
            response = await self._post_bounded(payload)
            result = self._rpc_result(response)

        content = result.get("content") or []
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
                elif item.get("text") is not None:
                    text_parts.append(str(item.get("text")))
            elif item is not None:
                text_parts.append(str(item))

        structured = result.get("structuredContent")
        if not text_parts and structured is not None:
            text_parts.append(json.dumps(structured, ensure_ascii=False))

        text = "\n".join(part for part in text_parts if part).strip()
        data = structured if structured is not None else self._decode_tool_text(text)
        is_error = bool(result.get("isError"))

        projected_devices = [
            item
            for item in (self._find_device_list(data) or [])
            if isinstance(item, dict)
        ]
        if (
            not is_error
            and expected_state_field is not None
            and projected_devices
            and not projected_state_shape_is_usable(
                projected_devices, expected_state_field
            )
        ):
            message = (
                "hub_list_devices response omitted the projected live-state field "
                f"'{expected_state_field}'"
            )
            mismatch_data = dict(data) if isinstance(data, dict) else {}
            mismatch_data["devices"] = projected_devices
            mismatch_data["error"] = message
            mismatch_data["projectionMismatch"] = True
            mismatch_data["expectedStateField"] = expected_state_field
            data = mismatch_data
            text = message
            is_error = True

        tool_result = MCPToolResult(
            name=name,
            arguments=arguments,
            raw=result,
            text=text,
            data=data,
            is_error=is_error,
        )
        if (
            cacheable
            and not is_error
            and generation == self._live_device_snapshot_generation
        ):
            self._live_device_snapshot = (
                self._clock(),
                generation,
                self._copy_tool_result(tool_result),
            )
        return tool_result

    async def _post(
        self,
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        headers: dict[str, Any] = {}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        attempt_limit = (
            self.retry_attempts if self._request_is_retryable(payload) else 1
        )
        response: httpx.Response | None = None
        for attempt in range(1, attempt_limit + 1):
            if attempt > 1:
                record_mcp_retry_attempt()
            try:
                response = await self._http.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                )
            except httpx.TransportError:
                if attempt >= attempt_limit:
                    raise
                delay = self.retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Transient MCP transport failure; retrying attempt %d/%d in %.2fs",
                    attempt + 1,
                    attempt_limit,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code < 500 or attempt >= attempt_limit:
                break
            delay = self.retry_backoff_seconds * (2 ** (attempt - 1))
            logger.warning(
                "MCP returned HTTP %d; retrying attempt %d/%d in %.2fs",
                response.status_code,
                attempt + 1,
                attempt_limit,
                delay,
            )
            await asyncio.sleep(delay)

        if response is None:
            raise MCPError("MCP request completed without a response")
        if response.headers.get("Mcp-Session-Id"):
            self._session_id = response.headers["Mcp-Session-Id"]

        if response.status_code >= 400:
            detail = response.text.strip()
            raise MCPError(
                f"MCP HTTP {response.status_code}: {detail[:500] or response.reason_phrase}"
            )
        if not response.content:
            if allow_empty:
                return {}
            raise MCPError("MCP returned an empty response")

        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            events = []
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        events.append(json.loads(raw))
                    except json.JSONDecodeError:
                        continue
            if not events:
                if allow_empty:
                    return {}
                raise MCPError("MCP SSE response contained no JSON event")
            return events[-1]

        try:
            value = response.json()
        except Exception as exc:
            raise MCPError(f"MCP returned invalid JSON: {response.text[:500]}") from exc
        if not isinstance(value, dict):
            raise MCPError("MCP JSON response was not an object")
        return value

    def _request_is_retryable(self, payload: dict[str, Any]) -> bool:
        if payload.get("method") != "tools/call":
            return True
        params = payload.get("params")
        if not isinstance(params, dict):
            return False
        name = str(params.get("name") or "")
        tool = self._tools.get(name)
        if tool and tool.annotations.get("readOnlyHint") is True:
            return True
        return name.startswith("hub_read_") or name in {
            "hub_get_info",
            "hub_search_tools",
        }

    @staticmethod
    def _rpc_result(response: dict[str, Any]) -> dict[str, Any]:
        if response.get("error"):
            error = response["error"]
            if isinstance(error, dict):
                message = error.get("message") or json.dumps(error, ensure_ascii=False)
            else:
                message = str(error)
            raise MCPError(message)
        result = response.get("result")
        if result is None:
            return {}
        if not isinstance(result, dict):
            return {"value": result}
        return result

    @staticmethod
    def _decode_tool_text(text: str) -> Any:
        value = text.strip()
        if not value:
            return None
        candidates = [value]
        fenced = re.search(r"```(?:json)?\s*(.*?)```", value, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            candidates.insert(0, fenced.group(1).strip())
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return value
