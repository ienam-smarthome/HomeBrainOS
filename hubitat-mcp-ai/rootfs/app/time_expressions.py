"""Shared deterministic clock-time parsing.

Used wherever a request may contain a spoken/typed time expression that
needs to be recognised or stripped. This only ever interprets an
already-isolated time token matched by `AT_TIME` -- it never scans free
text for meaning, and it never guesses a time from something that doesn't
parse. Keeping this in one place means `rule_authoring_service.py` and
`device_control_service.py` can't drift into two different definitions of
what counts as a valid clock expression.
"""

from __future__ import annotations

import re

AT_TIME = re.compile(
    r"\bat\s+(?P<time>\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\b",
    re.I,
)


def parse_clock(value: str) -> str | None:
    """Parse a clock expression like '7am', '11:11pm', '19:00' into 'HH:MM'.

    Returns None for anything that doesn't cleanly parse as a 12- or
    24-hour clock time -- never a best-effort guess.
    """

    compact = re.sub(r"[.\s]", "", value.casefold())
    match = re.fullmatch(r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?(?P<ampm>am|pm)?", compact)
    if match is None:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = match.group("ampm")
    if minute > 59 or (ampm and not 1 <= hour <= 12) or (not ampm and hour > 23):
        return None
    if ampm:
        hour %= 12
        if ampm == "pm":
            hour += 12
    return f"{hour:02d}:{minute:02d}"


def strip_trailing_time(text: str) -> tuple[str, str | None]:
    """Remove a trailing "at <time>" clause from text, if present.

    Returns (cleaned_text, parsed_time_or_None). Only strips when the
    matched clause actually parses as a clock time; a malformed "at"
    phrase is left in place rather than guessed at.
    """

    match = AT_TIME.search(text)
    if match is None:
        return text, None
    parsed = parse_clock(match.group("time"))
    if parsed is None:
        return text, None
    cleaned = text[: match.start()] + text[match.end():]
    cleaned = " ".join(cleaned.split()).strip(" ,.-")
    return cleaned, parsed


__all__ = ["AT_TIME", "parse_clock", "strip_trailing_time"]
