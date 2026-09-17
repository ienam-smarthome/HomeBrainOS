"""Deterministic semantic time windows for device-history questions.

The model decides that device history is needed, but calendar phrases such as
"last night" must not be left to free-form model arithmetic. This module
recognises a deliberately small, auditable vocabulary and resolves it against
the add-on's local timezone into explicit aware datetimes.

The stable policy for ``last night`` is 18:00 on the previous local calendar
day through 08:00 today, capped at ``now`` when that overnight window is still
in progress. Common equivalent wording (``during the night``, ``overnight``,
``through the night``) maps to that same auditable window. Explicit
``between X and Y`` clock ranges override that default and are resolved to
yesterday/today/last-night when those anchors are present, or to the most
recent started occurrence otherwise.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import math
import re
from typing import Any


_CLOCK_TOKEN = (
    r"(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)?"
)
_BETWEEN = re.compile(
    rf"\bbetween\s+(?P<start>{_CLOCK_TOKEN})\s+(?:and|to)\s+"
    rf"(?P<end>{_CLOCK_TOKEN})\b",
    re.I,
)
_NIGHT_ALIASES = (
    "last night",
    "during the night",
    "overnight",
    "through the night",
)
_ACTIVE_HISTORY_WINDOW: ContextVar[dict[str, Any] | None] = ContextVar(
    "homebrain_history_time_window",
    default=None,
)


@dataclass(frozen=True, slots=True)
class HistoryWindow:
    kind: str
    label: str
    start: datetime
    end: datetime
    ongoing: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "ongoing": self.ongoing,
        }


def set_history_window_request(request: dict[str, Any] | None) -> Token:
    """Bind one parsed semantic window to the current async request context."""

    return _ACTIVE_HISTORY_WINDOW.set(dict(request) if isinstance(request, dict) else None)


def reset_history_window_request(token: Token) -> None:
    _ACTIVE_HISTORY_WINDOW.reset(token)


def active_history_window_request() -> dict[str, Any] | None:
    value = _ACTIVE_HISTORY_WINDOW.get()
    return dict(value) if isinstance(value, dict) else None


def _local_now(now: datetime) -> datetime:
    # An injected aware datetime already carries the authoritative local offset
    # for that request/test. The production default is datetime.now().astimezone(),
    # so preserving awareness avoids accidentally converting an explicit Hubitat
    # local offset to the container's timezone during deterministic tests.
    return now if now.tzinfo is not None else now.astimezone()


def _parse_clock(value: str) -> time | None:
    text = str(value or "").strip().lower().replace(".", "")
    match = re.fullmatch(
        r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?",
        text,
    )
    if match is None:
        return None
    hour = int(match.group("hour"))
    minute_text = match.group("minute")
    minute = int(minute_text or 0)
    ampm = match.group("ampm")
    if not 0 <= minute <= 59:
        return None
    if ampm:
        if not 1 <= hour <= 12:
            return None
        hour %= 12
        if ampm == "pm":
            hour += 12
    else:
        # Bare "10" is too ambiguous for a deterministic clock range. A
        # colon (10:00) or an explicit am/pm marker is required.
        if minute_text is None or not 0 <= hour <= 23:
            return None
    return time(hour=hour, minute=minute)


def _clock_label(value: time) -> str:
    hour = value.hour % 12 or 12
    suffix = "am" if value.hour < 12 else "pm"
    if value.minute:
        return f"{hour}:{value.minute:02d}{suffix}"
    return f"{hour}{suffix}"


def _night_phrase_present(text: str) -> bool:
    return any(phrase in text for phrase in _NIGHT_ALIASES)


def parse_history_window_request(prompt: str) -> dict[str, Any] | None:
    """Recognise a bounded semantic history window from the original prompt."""

    text = " ".join(str(prompt or "").strip().casefold().split())
    if not text:
        return None

    explicit = _BETWEEN.search(text)
    if explicit is not None:
        start = _parse_clock(explicit.group("start"))
        end = _parse_clock(explicit.group("end"))
        if start is not None and end is not None:
            if "yesterday" in text:
                anchor = "yesterday"
            elif _night_phrase_present(text):
                anchor = "last_night"
            elif "today" in text or "this morning" in text or "since midnight" in text:
                anchor = "today"
            else:
                anchor = "most_recent"
            return {
                "kind": "clock_range",
                "label": f"between {_clock_label(start)} and {_clock_label(end)}",
                "startClock": start.strftime("%H:%M"),
                "endClock": end.strftime("%H:%M"),
                "anchor": anchor,
            }

    if _night_phrase_present(text):
        return {"kind": "last_night", "label": "last night"}
    if "yesterday" in text:
        return {"kind": "yesterday", "label": "yesterday"}
    if "this morning" in text:
        return {"kind": "this_morning", "label": "this morning"}
    if "since midnight" in text:
        return {"kind": "since_midnight", "label": "since midnight"}
    if re.search(r"\btoday\b", text):
        return {"kind": "today", "label": "today"}
    return None


def _combine(day: datetime, clock: time) -> datetime:
    return day.replace(
        hour=clock.hour,
        minute=clock.minute,
        second=0,
        microsecond=0,
    )


def _clock_from_request(value: Any) -> time | None:
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, TypeError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return time(hour=hour, minute=minute)


def _range_from_start(start: datetime, start_clock: time, end_clock: time) -> tuple[datetime, datetime]:
    resolved_start = _combine(start, start_clock)
    resolved_end = _combine(start, end_clock)
    if resolved_end <= resolved_start:
        resolved_end += timedelta(days=1)
    return resolved_start, resolved_end


def resolve_history_window(
    request: dict[str, Any] | None,
    *,
    now: datetime,
) -> HistoryWindow | None:
    """Resolve a parsed request, falling back to the request-scoped prompt window."""

    if not isinstance(request, dict):
        request = active_history_window_request()
    if not isinstance(request, dict):
        return None
    local_now = _local_now(now)
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    kind = str(request.get("kind") or "").strip().casefold()
    label = str(request.get("label") or kind.replace("_", " ")).strip()

    if kind == "last_night":
        start = today - timedelta(days=1) + timedelta(hours=18)
        natural_end = today + timedelta(hours=8)
        end = min(local_now, natural_end)
        if end <= start:
            return None
        return HistoryWindow(kind, label or "last night", start, end, local_now < natural_end)

    if kind == "yesterday":
        start = today - timedelta(days=1)
        return HistoryWindow(kind, label or "yesterday", start, today, False)

    if kind == "this_morning":
        start = today
        natural_end = today + timedelta(hours=12)
        end = min(local_now, natural_end)
        if end <= start:
            return None
        return HistoryWindow(kind, label or "this morning", start, end, local_now < natural_end)

    if kind in {"since_midnight", "today"}:
        if local_now <= today:
            return None
        return HistoryWindow(kind, label or kind.replace("_", " "), today, local_now, True)

    if kind != "clock_range":
        return None
    start_clock = _clock_from_request(request.get("startClock"))
    end_clock = _clock_from_request(request.get("endClock"))
    if start_clock is None or end_clock is None:
        return None
    anchor = str(request.get("anchor") or "most_recent").casefold()

    if anchor == "yesterday":
        start, end = _range_from_start(today - timedelta(days=1), start_clock, end_clock)
        if start > local_now:
            return None
        return HistoryWindow(kind, label, start, min(end, local_now), end > local_now)

    if anchor == "today":
        start, end = _range_from_start(today, start_clock, end_clock)
        if start > local_now:
            return None
        return HistoryWindow(kind, label, start, min(end, local_now), end > local_now)

    if anchor == "last_night":
        envelope_start = today - timedelta(days=1) + timedelta(hours=18)
        envelope_end = min(today + timedelta(hours=8), local_now)
        candidates: list[tuple[datetime, datetime]] = []
        for day in (today - timedelta(days=1), today):
            start, end = _range_from_start(day, start_clock, end_clock)
            clipped_end = min(end, local_now)
            if start < envelope_end and clipped_end > envelope_start and start <= local_now:
                candidates.append((start, clipped_end))
        if not candidates:
            return None
        start, end = max(candidates, key=lambda pair: pair[0])
        start = max(start, envelope_start)
        end = min(end, envelope_end)
        if end <= start:
            return None
        return HistoryWindow(kind, label, start, end, end == local_now)

    # Unanchored ranges mean the most recent occurrence that has started.
    candidates = []
    for day in (today - timedelta(days=1), today):
        start, end = _range_from_start(day, start_clock, end_clock)
        if start <= local_now:
            candidates.append((start, min(end, local_now), end > local_now))
    if not candidates:
        return None
    start, end, ongoing = max(candidates, key=lambda item: item[0])
    if end <= start:
        return None
    return HistoryWindow(kind, label, start, end, ongoing)


def required_history_hours(window: HistoryWindow, *, now: datetime) -> int:
    """Return an integer hoursBack that reaches one hour before the window."""

    local_now = _local_now(now)
    age_hours = max(0.0, (local_now - window.start).total_seconds() / 3600.0)
    return max(1, min(168, int(math.ceil(age_hours)) + 1))


__all__ = [
    "HistoryWindow",
    "active_history_window_request",
    "parse_history_window_request",
    "required_history_hours",
    "reset_history_window_request",
    "resolve_history_window",
    "set_history_window_request",
]
