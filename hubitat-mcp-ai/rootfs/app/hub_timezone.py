"""Authoritative Hubitat timezone resolution for calendar-aware history reads.

Semantic phrases such as ``last night`` must use the Hubitat location timezone,
not the Home Assistant add-on container timezone. The MCP Rule Server exposes the
hub's IANA timezone through ``hub_get_info.timeZone``. This module validates and
caches that value briefly, returns an aware ``now`` in the hub timezone, and
falls back explicitly to the runtime timezone when the upstream timezone cannot
be read.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp_client import HubitatMCPClient, tool_succeeded


HUB_INFO_TOOL = "hub_get_info"
DEFAULT_CACHE_SECONDS = 300.0


class HubTimezoneResolver:
    """Resolve and briefly cache the Hubitat location's IANA timezone."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        record_evidence: Callable[..., None],
        *,
        cache_seconds: float = DEFAULT_CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.mcp = mcp_client
        self._record_evidence = record_evidence
        self._cache_seconds = max(0.0, float(cache_seconds))
        self._clock = clock
        self._cached_name: str | None = None
        self._cached_at = 0.0

    @classmethod
    def _timezone_name(cls, value: Any) -> str | None:
        """Find a valid IANA timezone in the common MCP result envelopes."""

        if not isinstance(value, dict):
            return None
        for key in ("timeZone", "timezone", "time_zone"):
            candidate = str(value.get(key) or "").strip()
            if not candidate:
                continue
            try:
                ZoneInfo(candidate)
            except (ZoneInfoNotFoundError, ValueError):
                continue
            return candidate
        for key in ("result", "data", "output"):
            nested = value.get(key)
            candidate = cls._timezone_name(nested)
            if candidate:
                return candidate
        return None

    def _cached_zone(self) -> ZoneInfo | None:
        if not self._cached_name:
            return None
        if self._clock() - self._cached_at >= self._cache_seconds:
            return None
        try:
            return ZoneInfo(self._cached_name)
        except (ZoneInfoNotFoundError, ValueError):
            self._cached_name = None
            self._cached_at = 0.0
            return None

    async def now_in_hub_timezone(
        self,
        now_factory: Callable[[], datetime],
    ) -> tuple[datetime, str | None, str]:
        """Return ``now`` in the authoritative hub timezone when available.

        The third return value is a privacy-safe source label exposed in the
        history evidence. No hub name, IP address, coordinates, or zip code from
        ``hub_get_info`` is retained or copied into evidence.
        """

        runtime_now = now_factory()
        cached = self._cached_zone()
        if cached is not None:
            return runtime_now.astimezone(cached), self._cached_name, "hub_get_info_cache"

        started = self._clock()
        source = None
        error: Exception | None = None
        try:
            source = await self.mcp.call_tool(HUB_INFO_TOOL, {})
        except Exception as exc:  # compatibility with older MCP servers/tests
            error = exc

        elapsed_ms = round((self._clock() - started) * 1000)
        name = (
            self._timezone_name(source.data)
            if source is not None and tool_succeeded(source)
            else None
        )
        if name:
            self._cached_name = name
            self._cached_at = self._clock()
            self._record_evidence(
                HUB_INFO_TOOL,
                {},
                success=True,
                elapsed_ms=elapsed_ms,
                summary=f"Hub timezone {name}",
                supports_live_claim=False,
                evidence_kind="authoritative_hub_timezone",
            )
            return runtime_now.astimezone(ZoneInfo(name)), name, "hub_get_info"

        # Timezone absence is not allowed to make the entire history read fail.
        # Keep the fallback explicit in evidence so technical output never
        # suggests the semantic calendar boundary was authoritative when it was
        # actually derived from the container/runtime timezone.
        fallback_name = getattr(runtime_now.tzinfo, "key", None) or str(runtime_now.tzinfo or "") or None
        summary = "Hub timezone unavailable; using runtime timezone"
        if error is not None:
            summary += f" ({type(error).__name__})"
        self._record_evidence(
            HUB_INFO_TOOL,
            {},
            success=source is not None and tool_succeeded(source),
            elapsed_ms=elapsed_ms,
            summary=summary,
            supports_live_claim=False,
            evidence_kind="authoritative_hub_timezone",
        )
        return runtime_now.astimezone(), fallback_name, "runtime_fallback"


def required_history_hours_absolute(window_start: datetime, *, now: datetime) -> int:
    """HoursBack needed to reach one absolute hour before a window boundary.

    Converting both endpoints to UTC before subtraction keeps this correct across
    DST transitions. Python wall-clock subtraction for datetimes carrying the same
    ZoneInfo object can otherwise under-count the autumn fallback by one hour.
    """

    if window_start.tzinfo is None or now.tzinfo is None:
        age_hours = max(0.0, (now - window_start).total_seconds() / 3600.0)
    else:
        age_hours = max(
            0.0,
            (
                now.astimezone(timezone.utc)
                - window_start.astimezone(timezone.utc)
            ).total_seconds()
            / 3600.0,
        )
    return max(1, min(168, int(math.ceil(age_hours)) + 1))


__all__ = [
    "HUB_INFO_TOOL",
    "HubTimezoneResolver",
    "required_history_hours_absolute",
]
