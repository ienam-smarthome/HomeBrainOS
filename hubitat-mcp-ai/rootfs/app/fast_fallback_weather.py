from __future__ import annotations

from typing import Any

from fast_fallback import FastFallbackRouter as BaseFastFallbackRouter
from mcp_client import MCPError
from weather_presenter_v2 import present_weather


class FastFallbackRouter(BaseFastFallbackRouter):
    """Fast fallback with robust weather-device attribute parsing."""

    async def _find_weather(self) -> dict[str, Any]:
        result = await self._list_devices(detailed=True, label_filter="weather")
        if result.is_error:
            raise MCPError(result.text or "Weather lookup failed")
        message, display = present_weather(result.data)
        return self._decorate(
            self._response(message, "fallback-weather", True, result),
            display,
            result,
        )
