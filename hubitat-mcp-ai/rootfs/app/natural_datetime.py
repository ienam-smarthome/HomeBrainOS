from __future__ import annotations

from datetime import datetime
from typing import Any


def format_natural_datetime(value: Any) -> str:
    """Render an ISO event timestamp as a concise, human-readable local time."""

    text = str(value or "").strip()
    if not text:
        return "an unreported time"

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text

    hour = parsed.strftime("%I").lstrip("0") or "0"
    minute = parsed.strftime("%M")
    meridiem = parsed.strftime("%p").lower()
    weekday = parsed.strftime("%A")
    month = parsed.strftime("%B")
    return f"{hour}:{minute} {meridiem} on {weekday} {parsed.day} {month} {parsed.year}"


__all__ = ["format_natural_datetime"]
