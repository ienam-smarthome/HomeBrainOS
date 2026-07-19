from __future__ import annotations

from typing import Any

from fallback_router import _normalise
from fast_fallback import FastFallbackRouter as BaseFastFallbackRouter
from mcp_client import MCPError
from weather_presenter_icons import present_weather


_WEATHER_TERMS = (
    "weather",
    "forecast",
    "rain",
    "raining",
    "umbrella",
    "precipitation",
    "temperature outside",
)


class FastFallbackRouter(BaseFastFallbackRouter):
    """Fast fallback with period-aware weather and rain answers."""

    async def answer(self, query: str) -> dict[str, Any]:
        q = _normalise(query)
        if any(term in q for term in _WEATHER_TERMS):
            return await self._find_weather(query)
        return await super().answer(query)

    async def _find_weather(self, query: str = "weather") -> dict[str, Any]:
        result = await self._list_devices(detailed=True, label_filter="weather")
        if result.is_error:
            raise MCPError(result.text or "Weather lookup failed")
        message, display = present_weather(result.data, query)
        return self._decorate(
            self._response(message, "fallback-weather", True, result),
            display,
            result,
        )
