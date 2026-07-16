from __future__ import annotations

import asyncio
import time
from typing import Any


class DashboardSnapshot:
    """Small cached HomeBrain-style live summary for the web dashboard."""

    def __init__(self, fallback: Any, ttl_seconds: float = 30.0) -> None:
        self.fallback = fallback
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
                }
            self._value = value
            self._expires_at = time.monotonic() + self.ttl_seconds
            return dict(value)

    @staticmethod
    def _integer(value: Any) -> int | None:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return None


def install_dashboard_api(application: Any, ttl_seconds: float = 30.0) -> DashboardSnapshot:
    snapshot = DashboardSnapshot(application.fallback, ttl_seconds=ttl_seconds)

    @application.app.get("/api/dashboard", response_model=None)
    async def dashboard(force: bool = False):
        return await snapshot.get(force=force)

    return snapshot


__all__ = ["DashboardSnapshot", "install_dashboard_api"]
