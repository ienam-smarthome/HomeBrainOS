"""Deterministic temporal analysis for bounded device event history.

The language model should decide *what the user is asking*, but timestamp
arithmetic should not be delegated to free-form model reasoning. This module
turns authoritative state-change rows into complete observed intervals and
pre-computed totals that the model can safely synthesize into a natural answer.

Only state pairs with unambiguous active/inactive semantics are analysed. A
partial boundary is never guessed: if the first observed row is an inactive
state, or the newest row leaves the device active, totals are explicitly marked
as lower bounds rather than silently closing an interval at an invented time.

The module also owns the narrow final-answer consistency guard for temporal
history claims. When one authoritative history receipt proves a total duration
and the model makes an explicit total-duration claim, a contradictory numeric
claim is replaced with a concise deterministic summary rather than being exposed
to the user as if it were grounded.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from natural_datetime import format_natural_datetime, normalize_iso_offset


_STATE_PAIRS: dict[str, tuple[str, str]] = {
    "switch": ("on", "off"),
    "contact": ("open", "closed"),
    "motion": ("active", "inactive"),
    "lock": ("unlocked", "locked"),
    "valve": ("open", "closed"),
}

_TOTALISH_DURATION_CLAIM = re.compile(
    r"\b(?:total(?:ly)?|altogether|in all)\b|"
    r"\b(?:was|were)\b.{0,50}\b(?:on|open|active|unlocked)\b.{0,20}\bfor\b",
    re.I | re.S,
)
_HOURS_DURATION = re.compile(
    r"(?P<hours>\d+)\s*(?:h(?:ours?|rs?)?)\s*"
    r"(?:and\s*)?"
    r"(?:(?P<minutes>\d+)\s*(?:m(?:in(?:ute)?s?)?))?",
    re.I,
)
_MINUTES_DURATION = re.compile(
    r"(?P<minutes>\d+)\s*(?:m(?:in(?:ute)?s?)?)\b",
    re.I,
)
_SECONDS_DURATION = re.compile(
    r"(?P<seconds>\d+)\s*(?:s(?:ec(?:ond)?s?)?)\b",
    re.I,
)


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


def _display_duration_seconds(seconds: int) -> int:
    """Normalise seconds to the same precision exposed by ``_duration_text``."""

    seconds = max(0, int(seconds))
    if seconds < 60:
        return seconds
    return ((seconds + 30) // 60) * 60


def _duration_mentions_seconds(text: str) -> list[int]:
    """Extract numeric duration mentions from concise natural-language answers."""

    source = str(text or "")
    values: list[int] = []
    occupied: list[tuple[int, int]] = []

    for match in _HOURS_DURATION.finditer(source):
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        values.append(hours * 3600 + minutes * 60)
        occupied.append(match.span())

    def overlaps(span: tuple[int, int]) -> bool:
        start, end = span
        return any(start < used_end and end > used_start for used_start, used_end in occupied)

    for match in _MINUTES_DURATION.finditer(source):
        if overlaps(match.span()):
            continue
        values.append(int(match.group("minutes") or 0) * 60)
        occupied.append(match.span())

    for match in _SECONDS_DURATION.finditer(source):
        if overlaps(match.span()):
            continue
        values.append(int(match.group("seconds") or 0))

    return values


def analyze_state_intervals(
    attribute: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Derive complete active-state intervals from newest-first event rows.

    The input order from Hubitat is newest first. Rows are sorted into
    chronological order using their full timestamps. For identical timestamps
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
        "continuous": len(intervals) == 1 and coverage_complete,
        "coverage": "complete" if coverage_complete else "partial",
        "totalIsLowerBound": not coverage_complete,
        "openActiveInterval": open_interval,
        "unmatchedInactiveRows": unmatched_inactive_rows,
        "duplicateStateRowsIgnored": duplicate_state_rows,
        "ignoredRows": ignored_rows,
    }


def history_temporal_evidence_details(result_data: Any) -> dict[str, Any] | None:
    """Return the small, privacy-safe temporal proof subset for evidence output."""

    if not isinstance(result_data, dict):
        return None
    temporal = result_data.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return None

    temporal_keys = (
        "activeState",
        "inactiveState",
        "totalActiveDuration",
        "totalActiveSeconds",
        "intervalCount",
        "longestActiveDuration",
        "longestActiveSeconds",
        "continuous",
        "coverage",
        "totalIsLowerBound",
    )
    details = {
        "label": result_data.get("label"),
        "attribute": result_data.get("attribute"),
        "hoursBack": result_data.get("hoursBack"),
        "temporalAnalysis": {
            key: temporal.get(key)
            for key in temporal_keys
            if key in temporal
        },
    }
    return details


def guard_history_duration_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Correct an explicit total-duration claim that conflicts with one proof.

    This is intentionally narrow. It runs only when exactly one successful
    ``homebrain_device_history`` receipt exposes deterministic temporal details,
    the final answer makes a total-ish duration claim, and that numeric duration
    does not include the deterministic total at the same display precision.
    Queries/answers about a longest interval alone are therefore left untouched.
    """

    text = str(message or "")
    if not _TOTALISH_DURATION_CLAIM.search(text):
        return text, False

    receipts = [
        receipt
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("tool") == "homebrain_device_history"
        and receipt.get("success") is True
        and isinstance(receipt.get("details"), dict)
        and isinstance(receipt["details"].get("temporalAnalysis"), dict)
    ]
    if len(receipts) != 1:
        return text, False

    details = receipts[0]["details"]
    temporal = details["temporalAnalysis"]
    try:
        total_seconds = int(temporal.get("totalActiveSeconds"))
        interval_count = int(temporal.get("intervalCount"))
    except (TypeError, ValueError):
        return text, False
    total_duration = str(temporal.get("totalActiveDuration") or "").strip()
    if not total_duration or interval_count <= 0:
        return text, False

    mentions = _duration_mentions_seconds(text)
    if not mentions:
        return text, False
    expected = _display_duration_seconds(total_seconds)
    if expected in mentions:
        return text, False

    label = str(details.get("label") or "The device").strip() or "The device"
    active_state = str(temporal.get("activeState") or "active").strip() or "active"
    lower_bound = bool(temporal.get("totalIsLowerBound"))
    qualifier = "at least " if lower_bound else ""
    interval_word = "interval" if interval_count == 1 else "separate intervals"
    corrected = (
        f"{label} was {active_state} for a total of {qualifier}{total_duration} "
        f"across {interval_count} {interval_word}."
    )
    longest = str(temporal.get("longestActiveDuration") or "").strip()
    if longest and interval_count > 1:
        corrected += f" The longest interval was {longest}."
    if lower_bound:
        corrected += (
            " The observed history has an incomplete boundary, so that total is "
            "a lower bound."
        )
    return corrected, True


__all__ = [
    "analyze_state_intervals",
    "guard_history_duration_claim",
    "history_temporal_evidence_details",
]
