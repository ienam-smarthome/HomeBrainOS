from __future__ import annotations

import asyncio
import time
from typing import Any


class DashboardSnapshot:
    """Small cached HomeBrain-style live summary for the web dashboard."""

    def __init__(
        self,
        fallback: Any,
        ttl_seconds: float = 30.0,
        device_index: Any | None = None,
    ) -> None:
        self.fallback = fallback
        self.device_index = device_index
        self.ttl_seconds = max(10.0, float(ttl_seconds))
        self._value: dict[str, Any] | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and self._value is not None and now < self._expires_at:
            return dict(self._value)

        async with self._lock:
            now = time.monotonic()
            if not force and self._value is not None and now < self._expires_at:
                return dict(self._value)
            try:
                if self.device_index is not None:
                    value = await self.device_index.dashboard_metrics(force=force)
                    value["source"] = "device-intelligence-index"
                else:
                    answer = await self.fallback.answer("What's happening at home?")
                    metrics = {
                        str(item.get("label") or "").strip().lower(): item.get("value")
                        for item in ((answer.get("display") or {}).get("metrics") or [])
                        if isinstance(item, dict)
                    }
                    value = {
                        "success": bool(answer.get("success", True)),
                        "lights_on": self._integer(metrics.get("lights on")),
                        "switches_on": self._integer(metrics.get("switches on")),
                        "motion_active": self._integer(metrics.get("motion active")),
                        "low_batteries": self._integer(metrics.get("low batteries")),
                        "updated_at": time.time(),
                        "source": "fallback-home-summary",
                    }
            except Exception as exc:
                value = {
                    "success": False,
                    "lights_on": None,
                    "switches_on": None,
                    "motion_active": None,
                    "low_batteries": None,
                    "error": str(exc),
                    "updated_at": time.time(),
                    "source": "unavailable",
                }
            self._value = value
            self._expires_at = time.monotonic() + self.ttl_seconds
            return dict(value)

    async def invalidate(self) -> None:
        async with self._lock:
            self._value = None
            self._expires_at = 0.0

    @staticmethod
    def _integer(value: Any) -> int | None:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return None


def install_dashboard_api(
    application: Any,
    ttl_seconds: float = 30.0,
    device_index: Any | None = None,
) -> DashboardSnapshot:
    snapshot = DashboardSnapshot(
        application.fallback,
        ttl_seconds=ttl_seconds,
        device_index=device_index,
    )

    @application.app.get("/api/dashboard", response_model=None)
    async def dashboard(force: bool = False):
        return await snapshot.get(force=force)

    return snapshot


__all__ = ["DashboardSnapshot", "install_dashboard_api"]
