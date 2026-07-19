from __future__ import annotations

import re
from typing import Any

from weather_presenter_v2 import present_weather as _present_weather


def weather_condition_icon(value: Any) -> str:
    """Return an icon that reflects the condition text without implying rain."""

    condition = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not condition:
        return "🌡️"

    if any(term in condition for term in ("thunder", "lightning", "storm")):
        return "⛈️"
    if any(term in condition for term in ("snow", "blizzard", "flurr")):
        return "🌨️"
    if "sleet" in condition or "freezing rain" in condition:
        return "🌨️"
    if any(term in condition for term in ("rain", "shower", "drizzle")):
        return "🌧️"
    if any(term in condition for term in ("fog", "mist", "haze")):
        return "🌫️"
    if any(term in condition for term in ("wind", "breez", "gale")):
        return "💨"
    if "overcast" in condition or condition == "cloudy":
        return "☁️"
    if "mostly cloudy" in condition:
        return "🌥️"
    if "partly cloudy" in condition:
        return "⛅"
    if "mostly sunny" in condition or "partly sunny" in condition:
        return "🌤️"
    if any(term in condition for term in ("sunny", "clear", "fair")):
        return "☀️"
    if "cloud" in condition:
        return "☁️"
    return "🌤️"


def present_weather(
    value: Any,
    query: str = "weather",
) -> tuple[str, dict[str, Any]]:
    """Present parsed weather with a condition-specific, non-misleading icon."""

    message, display = _present_weather(value, query)
    metrics = display.get("metrics") if isinstance(display, dict) else None
    if isinstance(metrics, list):
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            if str(metric.get("label") or "").strip().lower() != "condition":
                continue
            metric["icon"] = weather_condition_icon(metric.get("value"))
    return message, display


__all__ = ["present_weather", "weather_condition_icon"]
