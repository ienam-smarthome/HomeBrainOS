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


def normalize_iso_offset(text: str) -> str:
    """Normalize a Hubitat ISO timestamp for ``datetime.fromisoformat()``.

    Rewrites a trailing "Z" to "+00:00" and inserts the colon into a
    trailing UTC offset that lacks one (e.g. "+0100" -> "+01:00"), which
    ``fromisoformat()`` only accepts natively on Python 3.11+. Hubitat emits
    timestamps in exactly the no-colon shape (e.g. "...23:32:52.656+0100").
    Shared by every module in this codebase that parses a raw Hubitat event
    timestamp, so the offset fix lives in exactly one place rather than
    being reimplemented (or forgotten) per call site.
    """

    normalized = str(text or "").replace("Z", "+00:00")
    return _OFFSET_WITHOUT_COLON.sub(r"\1:\2", normalized)


def format_natural_datetime(value: Any) -> str:
    """Render an ISO event timestamp as a concise, human-readable local time."""

    text = str(value or "").strip()
    if not text:
        return "an unreported time"

    normalized = normalize_iso_offset(text)

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


__all__ = ["format_natural_datetime", "normalize_iso_offset"]