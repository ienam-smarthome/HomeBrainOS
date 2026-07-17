from __future__ import annotations

import asyncio
import json
import re
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from mcp_client import HubitatMCPClient, MCPToolResult


_current_trace: ContextVar[dict[str, Any] | None] = ContextVar(
    "hmcp_current_trace",
    default=None,
)


def begin_mcp_trace(trace: dict[str, Any]) -> Token:
    return _current_trace.set(trace)


def end_mcp_trace(token: Token) -> None:
    _current_trace.reset(token)


def _trace_event(event: dict[str, Any]) -> None:
    trace = _current_trace.get()
    if trace is not None:
        trace.setdefault("mcp_events", []).append(event)


@dataclass(slots=True)
class _CacheEntry:
    value: MCPToolResult
    stored_at: float
    expires_at: float
    category: str


class MCPStateBroker:
    """Shared cache, request coalescer and gateway-aware MCP proxy.

    Kingpanther's current MCP server publishes a compact list of core tools and
    category gateways. The descriptions of those gateways enumerate the hidden
    tools they contain. This broker transparently translates a valid hidden tool
    request such as ``hub_get_logs`` into the correct gateway call, while keeping
    writes uncached and preserving the original tool name in traces and results.
    """

    DEVICE_READ_TOOLS = {"hub_list_devices", "hub_read_devices"}
    CATALOG_READ_TOOLS = {
        "hub_list_rooms",
        "hub_read_rooms",
        "hub_list_rules",
        "hub_read_rules",
    }
    HUB_READ_TOOLS = {"hub_get_info", "hub_get_metrics"}

    DEVICE_WRITE_TOOLS = {
        "hub_call_device_command",
        "hub_control_device",
        "hub_set_device_state",
    }
    RULE_WRITE_PREFIXES = (
        "hub_create_rule",
        "hub_update_rule",
        "hub_delete_rule",
        "hub_pause_rule",
        "hub_resume_rule",
        "hub_run_rule",
        "hub_set_rule",
        "hub_call_rule",
    )
    GLOBAL_WRITE_PREFIXES = (
        "hub_set_mode",
        "hub_set_hsm",
        "hub_reboot",
        "hub_shutdown",
        "hub_restore",
        "hub_update_firmware",
    )
    GATEWAY_PREFIXES = ("hub_read_", "hub_manage_")

    def __init__(
        self,
        client: HubitatMCPClient,
        *,
        device_ttl_seconds: float = 12.0,
        catalog_ttl_seconds: float = 60.0,
        hub_ttl_seconds: float = 20.0,
    ) -> None:
        self.client = client
        self.device_ttl_seconds = max(0.0, float(device_ttl_seconds))
        self.catalog_ttl_seconds = max(0.0, float(catalog_ttl_seconds))
        self.hub_ttl_seconds = max(0.0, float(hub_ttl_seconds))
        self._cache: dict[str, _CacheEntry] = {}
        self._inflight: dict[str, asyncio.Task[MCPToolResult]] = {}
        self._generation = {"devices": 0, "catalog": 0, "hub": 0}
        self._lock = asyncio.Lock()
        self._gateway_map: dict[str, str] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "coalesced": 0,
            "bypassed": 0,
            "invalidations": 0,
            "upstream_calls": 0,
            "discarded_stale_fetches": 0,
            "gateway_translations": 0,
        }

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

    @property
    def configured(self) -> bool:
        return self.client.configured

    @property
    def server_info(self) -> dict[str, Any]:
        return self.client.server_info

    async def initialize(self, force: bool = False) -> None:
        if force:
            await self.clear()
            self._gateway_map.clear()
        await self.client.initialize(force=force)

    async def close(self) -> None:
        await self.client.close()

    async def gateway_map(self, refresh: bool = False) -> dict[str, str]:
        """Return hidden tool → preferred gateway mappings from tools/list."""
        if self._gateway_map and not refresh:
            return dict(self._gateway_map)

        tools = await self.client.list_tools(refresh=refresh)
        visible = {tool.name for tool in tools}
        candidates: dict[str, list[str]] = {}
        for tool in tools:
            if not tool.name.startswith(self.GATEWAY_PREFIXES):
                continue
            names = set(re.findall(r"\bhub_[a-z0-9_]+\b", tool.description or ""))
            names.discard(tool.name)
            for hidden in names:
                if hidden in visible:
                    continue
                candidates.setdefault(hidden, []).append(tool.name)

        resolved: dict[str, str] = {}
        for hidden, gateways in candidates.items():
            gateways.sort(key=lambda gateway: self._gateway_priority(hidden, gateway))
            resolved[hidden] = gateways[0]
        self._gateway_map = resolved
        return dict(resolved)

    @staticmethod
    def _gateway_priority(hidden: str, gateway: str) -> tuple[int, str]:
        read_name = hidden.startswith(("hub_get_", "hub_list_", "hub_read_"))
        if read_name and gateway.startswith("hub_read_"):
            return 0, gateway
        if gateway.startswith("hub_manage_"):
            return 1, gateway
        return 2, gateway

    async def _translate_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, dict[str, Any], str | None]:
        tools = await self.client.list_tools()
        visible = {tool.name for tool in tools}
        if name in visible or not name.startswith("hub_"):
            return name, arguments, None

        gateway = (await self.gateway_map()).get(name)
        if not gateway:
            return name, arguments, None
        self._stats["gateway_translations"] += 1
        return gateway, {"tool": name, "args": arguments}, gateway

    async def _upstream_call(
        self,
        requested_name: str,
        arguments: dict[str, Any],
    ) -> tuple[MCPToolResult, str | None]:
        upstream_name, upstream_args, gateway = await self._translate_tool_call(
            requested_name,
            arguments,
        )
        result = await self.client.call_tool(upstream_name, upstream_args)
        if gateway:
            raw = dict(result.raw) if isinstance(result.raw, dict) else {"raw": result.raw}
            raw["gateway"] = gateway
            raw["requestedTool"] = requested_name
            result = MCPToolResult(
                name=requested_name,
                arguments=arguments,
                raw=raw,
                text=result.text,
                data=result.data,
                is_error=result.is_error,
            )
        return result, gateway

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        arguments = arguments if isinstance(arguments, dict) else {}
        policy = self._cache_policy(name)
        if policy is None:
            started = time.perf_counter()
            self._stats["bypassed"] += 1
            self._stats["upstream_calls"] += 1
            gateway: str | None = None
            try:
                result, gateway = await self._upstream_call(name, arguments)
            finally:
                duration_ms = round((time.perf_counter() - started) * 1000)
                event = {
                    "tool": name,
                    "cache": "bypass",
                    "duration_ms": duration_ms,
                    "argument_keys": sorted(arguments),
                }
                if gateway:
                    event["gateway"] = gateway
                _trace_event(event)
            if not result.is_error:
                await self._invalidate_for_write(name)
            return result

        category, ttl_seconds = policy
        if ttl_seconds <= 0:
            started = time.perf_counter()
            self._stats["bypassed"] += 1
            self._stats["upstream_calls"] += 1
            result, gateway = await self._upstream_call(name, arguments)
            event = {
                "tool": name,
                "cache": "disabled",
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "argument_keys": sorted(arguments),
            }
            if gateway:
                event["gateway"] = gateway
            _trace_event(event)
            return result

        key = self._cache_key(name, arguments)
        now = time.monotonic()
        async with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now < entry.expires_at:
                self._stats["hits"] += 1
                _trace_event(
                    {
                        "tool": name,
                        "cache": "hit",
                        "duration_ms": 0,
                        "age_ms": round((now - entry.stored_at) * 1000),
                        "argument_keys": sorted(arguments),
                    }
                )
                return entry.value

            task = self._inflight.get(key)
            if task is not None:
                self._stats["coalesced"] += 1
                _trace_event(
                    {
                        "tool": name,
                        "cache": "coalesced",
                        "duration_ms": 0,
                        "argument_keys": sorted(arguments),
                    }
                )
            else:
                self._stats["misses"] += 1
                generation = self._generation[category]
                task = asyncio.create_task(
                    self._fetch_and_store(
                        key=key,
                        name=name,
                        arguments=arguments,
                        category=category,
                        generation=generation,
                        ttl_seconds=ttl_seconds,
                    ),
                    name=f"hmcp-cache-{name}",
                )
                self._inflight[key] = task

        return await asyncio.shield(task)

    async def _fetch_and_store(
        self,
        *,
        key: str,
        name: str,
        arguments: dict[str, Any],
        category: str,
        generation: int,
        ttl_seconds: float,
    ) -> MCPToolResult:
        started = time.perf_counter()
        self._stats["upstream_calls"] += 1
        try:
            result, gateway = await self._upstream_call(name, arguments)
            duration_ms = round((time.perf_counter() - started) * 1000)
            event = {
                "tool": name,
                "cache": "miss",
                "duration_ms": duration_ms,
                "argument_keys": sorted(arguments),
            }
            if gateway:
                event["gateway"] = gateway
            _trace_event(event)
            if not result.is_error:
                now = time.monotonic()
                async with self._lock:
                    if self._generation[category] == generation:
                        self._cache[key] = _CacheEntry(
                            value=result,
                            stored_at=now,
                            expires_at=now + ttl_seconds,
                            category=category,
                        )
                    else:
                        self._stats["discarded_stale_fetches"] += 1
            return result
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    def _cache_policy(self, name: str) -> tuple[str, float] | None:
        if name in self.DEVICE_READ_TOOLS:
            return "devices", self.device_ttl_seconds
        if name in self.CATALOG_READ_TOOLS:
            return "catalog", self.catalog_ttl_seconds
        if name in self.HUB_READ_TOOLS:
            return "hub", self.hub_ttl_seconds
        return None

    async def _invalidate_for_write(self, name: str) -> None:
        if name in self.DEVICE_WRITE_TOOLS or name.startswith("hub_call_device_"):
            await self.invalidate("devices")
            return
        if name.startswith(self.RULE_WRITE_PREFIXES):
            await self.invalidate("catalog")
            return
        if name.startswith(self.GLOBAL_WRITE_PREFIXES):
            await self.invalidate("all")

    async def invalidate(self, category: str = "all") -> int:
        async with self._lock:
            categories = tuple(self._generation) if category == "all" else (category,)
            for item in categories:
                if item in self._generation:
                    self._generation[item] += 1

            if category == "all":
                count = len(self._cache)
                self._cache.clear()
            else:
                keys = [
                    key
                    for key, entry in self._cache.items()
                    if entry.category == category
                ]
                for key in keys:
                    self._cache.pop(key, None)
                count = len(keys)
            self._stats["invalidations"] += 1
        _trace_event(
            {
                "tool": "cache.invalidate",
                "cache": category,
                "duration_ms": 0,
                "entries": count,
            }
        )
        return count

    async def clear(self) -> int:
        return await self.invalidate("all")

    def stats(self) -> dict[str, Any]:
        now = time.monotonic()
        live_entries = [entry for entry in self._cache.values() if now < entry.expires_at]
        return {
            **self._stats,
            "entries": len(live_entries),
            "inflight": len(self._inflight),
            "gateway_mappings": len(self._gateway_map),
            "device_ttl_seconds": self.device_ttl_seconds,
            "catalog_ttl_seconds": self.catalog_ttl_seconds,
            "hub_ttl_seconds": self.hub_ttl_seconds,
        }

    @staticmethod
    def _cache_key(name: str, arguments: dict[str, Any]) -> str:
        encoded = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return f"{name}:{encoded}"


__all__ = [
    "MCPStateBroker",
    "begin_mcp_trace",
    "end_mcp_trace",
]
