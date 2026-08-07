from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# Matches a trailing UTC offset with no colon, e.g. "+0100" or "-0530",
# which datetime.fromisoformat() only accepts on Python 3.11+. Hubitat
# emits timestamps in exactly this shape (e.g. "...23:32:52.656+0100"),
# so on Python 3.10 and earlier fromisoformat() raised ValueError and this
# function silently fell back to the raw ISO string instead of rendering
# natural-language text -- the bug this module now guards against.
_OFFSET_WITHOUT_COLON = re.compile(r"(?<=\d)([+-]\d{2})(\d{2})$")


def format_natural_datetime(value: Any) -> str:
    """Render an ISO event timestamp as a concise, human-readable local time."""

    text = str(value or "").strip()
    if not text:
        return "an unreported time"

    normalized = text.replace("Z", "+00:00")
    normalized = _OFFSET_WITHOUT_COLON.sub(r"\1:\2", normalized)

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text

    hour = parsed.strftime("%I").lstrip("0") or "0"
    minute = parsed.strftime("%M")
    meridiem = parsed.strftime("%p").lower()
    weekday = parsed.strftime("%A")
    month = parsed.strftime("%B")
    return f"{hour}:{minute} {meridiem} on {weekday} {parsed.day} {month} {parsed.year}"


__all__ = ["format_natural_datetime"]