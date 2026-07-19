from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fallback_router import _normalise
from fast_fallback_extended_reads import _rows
from presenter import first_value


def parse_event_time(value: Any, timezone: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or re.fullmatch(r"\d+(?:\.\d+)?", str(value).strip()):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        try:
            return datetime.fromtimestamp(number, tz=timezone)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
        for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                pass
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def switch_events(value: Any, timezone: Any) -> list[tuple[datetime, str]]:
    found: set[tuple[datetime, str]] = set()
    for row in _rows(value, ("events", "items", "history", "entries")):
        state = _normalise(first_value(row, "value", "currentValue", "state", "newValue"))
        if state not in {"on", "off"}:
            continue
        attribute = _normalise(first_value(row, "name", "attribute", "type"))
        description = _normalise(first_value(row, "descriptionText", "description"))
        if attribute and attribute not in {"switch", "switch state", "state"} and "switch" not in description:
            continue
        occurred = parse_event_time(
            first_value(row, "date", "timestamp", "time", "eventTime", "createdAt", "unixTime"),
            timezone,
        )
        if occurred is not None:
            found.add((occurred, state))
    return sorted(found, key=lambda item: item[0])


def calculate_on_time(
    events: list[tuple[datetime, str]],
    day_start: datetime,
    now: datetime,
    live_state: str,
) -> dict[str, Any]:
    before = [item for item in events if item[0] <= day_start]
    today = [item for item in events if day_start < item[0] <= now]
    opened = day_start if before and before[-1][1] == "on" else None
    seconds = 0.0
    unmatched_off: list[datetime] = []
    duplicate_on = 0

    for occurred, state in today:
        if state == "on":
            if opened is None:
                opened = occurred
            else:
                duplicate_on += 1
        elif opened is None:
            unmatched_off.append(occurred)
        else:
            seconds += max(0.0, (occurred - opened).total_seconds())
            opened = None

    unmatched_on = False
    if opened is not None:
        if live_state == "on":
            seconds += max(0.0, (now - opened).total_seconds())
        else:
            unmatched_on = True

    notes: list[str] = []
    if unmatched_off:
        notes.append(f"{len(unmatched_off)} unmatched off event{'s' if len(unmatched_off) != 1 else ''}")
    if unmatched_on:
        notes.append("unmatched on event while live state is off")
    if duplicate_on:
        notes.append(f"{duplicate_on} duplicate on event{'s' if duplicate_on != 1 else ''} ignored")
    if not before and today and today[0][1] == "off":
        notes.append("midnight state unknown")

    return {
        "seconds": seconds,
        "event_count": len(events),
        "today_event_count": len(today),
        "state_known_at_start": bool(before),
        "unmatched_off_times": [item.isoformat() for item in unmatched_off],
        "unmatched_on": unmatched_on,
        "duplicate_on": duplicate_on,
        "incomplete": bool(unmatched_off or unmatched_on),
        "notes": notes,
    }


def duration_text(seconds: float, compact: bool = False) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m" if compact else f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes}m" if compact else f"{minutes} min"
    return "<1 min" if total else "0 min"


__all__ = ["calculate_on_time", "duration_text", "parse_event_time", "switch_events"]
