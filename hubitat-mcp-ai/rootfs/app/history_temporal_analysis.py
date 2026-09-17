"""Deterministic temporal analysis for bounded device event history.

The language model should decide *what the user is asking*, but timestamp
arithmetic should not be delegated to free-form model reasoning.  This module
turns authoritative state-change rows into complete observed intervals and
pre-computed totals that the model can safely synthesize into a natural answer.

Only state pairs with unambiguous active/inactive semantics are analysed.  A
partial boundary is never guessed: if the first observed row is an inactive
state, or the newest row leaves the device active, totals are explicitly marked
as lower bounds rather than silently closing an interval at an invented time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from natural_datetime import format_natural_datetime, normalize_iso_offset


_STATE_PAIRS: dict[str, tuple[str, str]] = {
    "switch": ("on", "off"),
    "contact": ("open", "closed"),
    "motion": ("active", "inactive"),
    "lock": ("unlocked", "locked"),
    "valve": ("open", "closed"),
}


def _explicit_false(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, str) and value.strip().casefold() == "false"


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _duration_text(seconds: int) -> str:
    """Human duration rounded to the nearest minute once >= 60 seconds."""

    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    rounded_minutes = (seconds + 30) // 60
    hours, minutes = divmod(rounded_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def analyze_state_intervals(
    attribute: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Derive complete active-state intervals from newest-first event rows.

    The input order from Hubitat is newest first.  Rows are sorted into
    chronological order using their full timestamps.  For identical timestamps
    the original newest-first order is reversed, preserving the only sequence
    information available from the upstream feed.
    """

    attribute_name = str(attribute or "").strip()
    pair = _STATE_PAIRS.get(attribute_name.casefold())
    if pair is None:
        return None
    active_state, inactive_state = pair

    parsed: list[tuple[datetime, int, str, dict[str, Any]]] = []
    ignored_rows = 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            ignored_rows += 1
            continue
        if str(event.get("name") or "").casefold() != attribute_name.casefold():
            ignored_rows += 1
            continue
        value = str(event.get("value") or "").strip().casefold()
        if value not in {active_state, inactive_state}:
            ignored_rows += 1
            continue
        if _explicit_false(event.get("isStateChange")):
            ignored_rows += 1
            continue
        timestamp = _parse_timestamp(event.get("date"))
        if timestamp is None:
            ignored_rows += 1
            continue
        parsed.append((timestamp, index, value, event))

    if not parsed:
        return None

    parsed.sort(key=lambda item: (item[0], -item[1]))

    intervals: list[dict[str, Any]] = []
    active_start: tuple[datetime, dict[str, Any]] | None = None
    duplicate_state_rows = 0
    unmatched_inactive_rows = 0

    for timestamp, _index, value, event in parsed:
        if value == active_state:
            if active_start is None:
                active_start = (timestamp, event)
            else:
                duplicate_state_rows += 1
            continue

        if active_start is None:
            unmatched_inactive_rows += 1
            continue

        start_timestamp, start_event = active_start
        duration_seconds = max(
            0,
            int(round((timestamp - start_timestamp).total_seconds())),
        )
        intervals.append({
            "start": start_event.get("date"),
            "end": event.get("date"),
            "startNatural": format_natural_datetime(start_event.get("date")),
            "endNatural": format_natural_datetime(event.get("date")),
            "durationSeconds": duration_seconds,
            "duration": _duration_text(duration_seconds),
        })
        active_start = None

    open_interval = active_start is not None
    total_seconds = sum(
        int(interval.get("durationSeconds") or 0) for interval in intervals
    )
    longest_seconds = max(
        (int(interval.get("durationSeconds") or 0) for interval in intervals),
        default=0,
    )
    coverage_complete = not open_interval and unmatched_inactive_rows == 0

    return {
        "attribute": attribute_name,
        "activeState": active_state,
        "inactiveState": inactive_state,
        "intervalCount": len(intervals),
        "intervals": intervals,
        "totalActiveSeconds": total_seconds,
        "totalActiveDuration": _duration_text(total_seconds),
        "longestActiveSeconds": longest_seconds,
        "longestActiveDuration": _duration_text(longest_seconds),
        "continuous": len(intervals) <= 1 and coverage_complete,
        "coverage": "complete" if coverage_complete else "partial",
        "totalIsLowerBound": not coverage_complete,
        "openActiveInterval": open_interval,
        "unmatchedInactiveRows": unmatched_inactive_rows,
        "duplicateStateRowsIgnored": duplicate_state_rows,
        "ignoredRows": ignored_rows,
    }


__all__ = ["analyze_state_intervals"]
