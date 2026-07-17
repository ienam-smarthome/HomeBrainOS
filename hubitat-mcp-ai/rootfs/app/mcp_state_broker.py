from __future__ import annotations

import asyncio
import json
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
    """Shared, short-lived cache and request coalescer for Hubitat MCP reads.

    The broker is a transparent proxy around :class:`HubitatMCPClient`. Existing
    fallback routes, the dashboard and the Ollama tool agent therefore share the
    same authoritative snapshots without each issuing a duplicate hub request.
    Device-control writes are never cached and invalidate affected snapshots
    before the caller performs its verification read.
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
    )
    GLOBAL_WRITE_PREFIXES = (
        "hub_set_mode",
        "hub_set_hsm",
        "hub_reboot",
        "hub_shutdown",
        "hub_restore",
        "hub_update_firmware",
    )

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
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "coalesced": 0,
            "bypassed": 0,
            "invalidations": 0,
            "upstream_calls": 0,
        }

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

    @property
    def configured(self) -> bool:
        return self.client.configured

    @property
    def server_info(self) -> dict[str, Any]:
        return self.client.server_info

    async def close(self) -> None:
        await self.client.close()

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
            try:
                result = await self.client.call_tool(name, arguments)
            finally:
                duration_ms = round((time.perf_counter() - started) * 1000)
                _trace_event(
                    {
                        "tool": name,
                        "cache": "bypass",
                        "duration_ms": duration_ms,
                        "argument_keys": sorted(arguments),
                    }
                )
            if not result.is_error:
                await self._invalidate_for_write(name)
            return result

        category, ttl_seconds = policy
        if ttl_seconds <= 0:
            started = time.perf_counter()
            self._stats["bypassed"] += 1
            self._stats["upstream_calls"] += 1
            result = await self.client.call_tool(name, arguments)
            _trace_event(
                {
                    "tool": name,
                    "cache": "disabled",
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                    "argument_keys": sorted(arguments),
                }
            )
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
                task = asyncio.create_task(
                    self._fetch_and_store(
                        key=key,
                        name=name,
                        arguments=arguments,
                        category=category,
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
        ttl_seconds: float,
    ) -> MCPToolResult:
        started = time.perf_counter()
        self._stats["upstream_calls"] += 1
        try:
            result = await self.client.call_tool(name, arguments)
            duration_ms = round((time.perf_counter() - started) * 1000)
            _trace_event(
                {
                    "tool": name,
                    "cache": "miss",
                    "duration_ms": duration_ms,
                    "argument_keys": sorted(arguments),
                }
            )
            if not result.is_error:
                now = time.monotonic()
                async with self._lock:
                    self._cache[key] = _CacheEntry(
                        value=result,
                        stored_at=now,
                        expires_at=now + ttl_seconds,
                        category=category,
                    )
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
            if count:
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
