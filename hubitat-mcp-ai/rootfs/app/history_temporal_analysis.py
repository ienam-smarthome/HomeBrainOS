"""Deterministic temporal analysis for bounded device event history.

The language model should decide *what the user is asking*, but timestamp
arithmetic should not be delegated to free-form model reasoning. This module
pairs recorded state rows and pre-computes duration evidence that the model can
safely synthesize into a natural answer.

Only state pairs with unambiguous active/inactive semantics are analysed.
Pagination completeness is deliberately kept separate from event-stream
integrity: a Hubitat page can reach the requested boundary while still omitting
physical transitions recorded elsewhere. Window-aware analysis therefore refuses
to turn missing rows into exact boundary state or exact duration unless source
integrity has been independently verified.

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
    r"\b(?:was|were)\b.{0,50}\b(?:on|open|active|unlocked)\b.{0,20}\bfor\b|"
    r"\b(?:continuously|throughout|all\s+night|entire\s+night)\b",
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
_UNVERIFIED_ESTIMATE_QUALIFIER = re.compile(
    r"\b(?:estimate|estimated|approximately|approx\.?|about|observed|recorded|pairing)\b",
    re.I,
)
_UNVERIFIED_EXACTNESS_CLAIM = re.compile(
    r"\b(?:exact|exactly|definitely|genuinely|continuous|continuously|"
    r"throughout|all\s+night|entire\s+night)\b",
    re.I,
)


def _explicit_false(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, str) and value.strip().casefold() == "false"


def _explicit_true(value: Any) -> bool:
    """Return True only when the source explicitly marks a state change."""

    if value is True:
        return True
    return isinstance(value, str) and value.strip().casefold() == "true"


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


def _replace_unverified_totalish_sentences(
    text: str,
    *,
    replacement: str,
    expected_seconds: int,
) -> tuple[str, bool]:
    """Correct only unsafe duration sentences and preserve other analysis.

    0.10.458 deliberately failed closed for unverified event streams by replacing
    the entire model answer whenever it mentioned a total duration. Live
    investigative queries later showed the cost: a useful normality/causal
    analysis could be erased just because one sentence said "1h 43m" instead of
    the deterministic recorded-row estimate. Keep the safety property, but make
    the correction local to the duration/continuity claim.

    A correctly rounded duration can remain untouched when the same sentence
    explicitly frames it as an estimate/recorded observation and makes no exact
    continuity claim.
    """

    # Treat line breaks as claim boundaries too. Investigative answers commonly
    # use bullets/tables where a duration claim has no terminal punctuation; the
    # old sentence-only splitter could therefore treat an entire rich answer as
    # one sentence and replace all of it with the deterministic duration fallback.
    pieces = re.split(r"(?P<space>(?<=[.!?])\s+|\n+)", str(text or ""))
    changed = False
    replacement_used = False
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if not _TOTALISH_DURATION_CLAIM.search(sentence):
            continue
        mentions = _duration_mentions_seconds(sentence)
        has_expected = expected_seconds in mentions
        qualified = _UNVERIFIED_ESTIMATE_QUALIFIER.search(sentence) is not None
        exactness = _UNVERIFIED_EXACTNESS_CLAIM.search(sentence) is not None
        if has_expected and qualified and not exactness:
            continue
        if not replacement_used:
            pieces[index] = replacement
            replacement_used = True
        else:
            pieces[index] = ""
        changed = True

    if changed:
        return "".join(pieces), True
    return str(text or ""), False


def _parsed_state_rows(
    attribute: str,
    events: list[dict[str, Any]],
) -> tuple[str, str, str, list[tuple[datetime, int, str, dict[str, Any]]], int] | None:
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
    parsed.sort(key=lambda item: (item[0], -item[1]))
    return attribute_name, active_state, inactive_state, parsed, ignored_rows


def _interval(
    start: datetime,
    end: datetime,
    *,
    start_value: Any | None = None,
    end_value: Any | None = None,
    clipped_start: bool = False,
    clipped_end: bool = False,
) -> dict[str, Any]:
    duration_seconds = max(0, int(round((end - start).total_seconds())))
    start_text = str(start_value or start.isoformat())
    end_text = str(end_value or end.isoformat())
    return {
        "start": start_text,
        "end": end_text,
        "startNatural": format_natural_datetime(start_text),
        "endNatural": format_natural_datetime(end_text),
        "durationSeconds": duration_seconds,
        "duration": _duration_text(duration_seconds),
        "clippedAtWindowStart": clipped_start,
        "clippedAtWindowEnd": clipped_end,
    }


def analyze_state_intervals(
    attribute: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Derive complete active-state intervals from newest-first event rows."""

    parsed_result = _parsed_state_rows(attribute, events)
    if parsed_result is None:
        return None
    attribute_name, active_state, inactive_state, parsed, ignored_rows = parsed_result
    if not parsed:
        return None

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
        intervals.append(
            _interval(
                start_timestamp,
                timestamp,
                start_value=start_event.get("date"),
                end_value=event.get("date"),
            )
        )
        active_start = None

    open_interval = active_start is not None
    open_start = active_start[0] if active_start is not None else None
    open_start_raw = (
        active_start[1].get("date")
        if active_start is not None and isinstance(active_start[1], dict)
        else None
    )
    total_seconds = sum(int(item.get("durationSeconds") or 0) for item in intervals)
    longest_seconds = max(
        (int(item.get("durationSeconds") or 0) for item in intervals),
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
        "unboundedActiveInterval": open_interval,
        "openActiveStart": (
            str(open_start_raw or open_start.isoformat())
            if open_start is not None
            else None
        ),
        "openActiveStartNatural": (
            format_natural_datetime(str(open_start_raw or open_start.isoformat()))
            if open_start is not None
            else None
        ),
        "unmatchedInactiveRows": unmatched_inactive_rows,
        "duplicateStateRowsIgnored": duplicate_state_rows,
        "ignoredRows": ignored_rows,
    }


def analyze_state_intervals_in_window(
    attribute: str,
    events: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
    window_label: str,
    source_complete_to_start: bool,
    window_ongoing: bool = False,
    source_integrity_verified: bool = False,
) -> dict[str, Any] | None:
    """Measure state intervals observed inside the requested window.

    source_complete_to_start is only a pagination/coverage fact: it means the
    returned page reaches the requested start. It does not prove the device-event
    stream contains every physical transition. Unless an independent source has
    verified event-stream integrity, HomeBrain must not extend a predecessor state
    to the window start, infer a missing boundary from the first row, or extend an
    open interval to the window end. Those operations can turn omitted transitions
    into many hours of invented activity.

    With unverified source integrity this function therefore reports only intervals
    bounded by observed active/inactive rows and marks the duration as an
    unverified-event-stream estimate rather than an exact total or mathematical
    lower bound.
    """

    if start.tzinfo is None or end.tzinfo is None or end <= start:
        return None
    parsed_result = _parsed_state_rows(attribute, events)
    if parsed_result is None:
        return None
    attribute_name, active_state, inactive_state, parsed, ignored_rows = parsed_result

    before = [row for row in parsed if row[0] < start]
    inside = [row for row in parsed if start <= row[0] < end]
    predecessor = before[-1] if before else None

    current_state: str | None = None
    boundary_known = False
    boundary_basis = (
        "unknown" if source_integrity_verified else "source-integrity-unverified"
    )
    inferred_boundary_state: str | None = None

    if source_integrity_verified and predecessor is not None:
        current_state = predecessor[2]
        boundary_known = True
        boundary_basis = "predecessor-event"
    elif (
        source_integrity_verified
        and inside
        and source_complete_to_start
        and _explicit_true(inside[0][3].get("isStateChange"))
    ):
        first_value = inside[0][2]
        inferred_boundary_state = (
            inactive_state if first_value == active_state else active_state
        )
        current_state = inferred_boundary_state
        boundary_known = True
        boundary_basis = "first-transition-inference"
    elif inside and source_complete_to_start and _explicit_true(
        inside[0][3].get("isStateChange")
    ):
        first_value = inside[0][2]
        inferred_boundary_state = (
            inactive_state if first_value == active_state else active_state
        )
        boundary_basis = "first-transition-inference-untrusted"

    intervals: list[dict[str, Any]] = []
    duplicate_state_rows = 0
    active_start: datetime | None = start if current_state == active_state else None
    active_start_raw: Any | None = None
    active_start_clipped = active_start is not None

    for timestamp, _index, value, event in inside:
        if current_state is None:
            current_state = value
            if value == active_state:
                active_start = timestamp
                active_start_raw = event.get("date")
                active_start_clipped = False
            continue
        if value == current_state:
            duplicate_state_rows += 1
            continue
        if value == active_state:
            current_state = active_state
            active_start = timestamp
            active_start_raw = event.get("date")
            active_start_clipped = False
            continue
        if current_state == active_state and active_start is not None:
            intervals.append(
                _interval(
                    active_start,
                    timestamp,
                    start_value=active_start_raw,
                    end_value=event.get("date"),
                    clipped_start=active_start_clipped,
                )
            )
        current_state = inactive_state
        active_start = None
        active_start_raw = None
        active_start_clipped = False

    open_active_interval = bool(current_state == active_state and active_start is not None)
    open_active_start_text = (
        str(active_start_raw or active_start.isoformat())
        if open_active_interval and active_start is not None
        else None
    )
    if source_integrity_verified and open_active_interval:
        intervals.append(
            _interval(
                active_start,
                end,
                start_value=active_start_raw,
                clipped_start=active_start_clipped,
                clipped_end=True,
            )
        )

    total_seconds = sum(int(item.get("durationSeconds") or 0) for item in intervals)
    longest_seconds = max(
        (int(item.get("durationSeconds") or 0) for item in intervals),
        default=0,
    )
    coverage_complete = bool(source_integrity_verified and boundary_known)
    reliability = "exact" if coverage_complete else "unverified-event-stream"

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
        "totalIsLowerBound": False if not source_integrity_verified else not coverage_complete,
        "durationReliability": reliability,
        "sourceIntegrity": "verified" if source_integrity_verified else "unverified",
        "sourceIntegrityVerified": bool(source_integrity_verified),
        "pageCompleteToWindowStart": bool(source_complete_to_start),
        "observedBoundedIntervalsOnly": not bool(source_integrity_verified),
        # An unbounded active interval means a recorded active transition had no
        # observed closing transition before the analysed window ended. It is
        # useful evidence even for a historical/closed window, but it is not a
        # duration claim. openActiveInterval is the stronger ongoing-window form.
        "unboundedActiveInterval": open_active_interval,
        "openActiveInterval": bool(window_ongoing and open_active_interval),
        "openActiveStart": open_active_start_text,
        "openActiveStartNatural": (
            format_natural_datetime(open_active_start_text)
            if open_active_start_text
            else None
        ),
        "unmatchedInactiveRows": 0,
        "duplicateStateRowsIgnored": duplicate_state_rows,
        "ignoredRows": ignored_rows,
        "analyzedStateEventCount": len(parsed),
        "firstWindowStateEvent": (
            {
                "timestamp": inside[0][0].isoformat(),
                "state": inside[0][2],
                "isStateChange": inside[0][3].get("isStateChange"),
            }
            if inside
            else None
        ),
        "predecessorStateEvent": (
            {
                "timestamp": predecessor[0].isoformat(),
                "state": predecessor[2],
                "isStateChange": predecessor[3].get("isStateChange"),
            }
            if predecessor is not None
            else None
        ),
        "inferredBoundaryState": inferred_boundary_state,
        "windowed": True,
        "windowLabel": str(window_label),
        "windowStart": start.isoformat(),
        "windowEnd": end.isoformat(),
        "windowOngoing": bool(window_ongoing),
        "boundaryStateKnown": boundary_known,
        "boundaryBasis": boundary_basis,
        "sourceCompleteToWindowStart": bool(source_complete_to_start),
    }
def window_event_evidence(
    events: list[dict[str, Any]],
    time_window: dict[str, Any] | None,
    *,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Return bounded source rows that actually fall inside the requested window.

    This evidence channel is independent of interval construction. It remains
    useful when an unverified stream establishes no bounded active interval but
    still contains commands or other device rows inside the requested period.
    """

    if not isinstance(time_window, dict):
        return []
    start = _parse_timestamp(time_window.get("start"))
    end = _parse_timestamp(time_window.get("end"))
    if start is None or end is None or end <= start:
        return []

    selected: list[tuple[datetime, int, dict[str, Any]]] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        event_time = _parse_timestamp(item.get("date") or item.get("timestamp"))
        if event_time is None or event_time < start or event_time > end:
            continue
        row = {
            key: item.get(key)
            for key in (
                "name",
                "value",
                "unit",
                "description",
                "date",
                "isStateChange",
            )
            if key in item
        }
        selected.append((event_time, index, row))

    # Render a causal/temporal window chronologically even when the upstream
    # device page is newest-first. Preserve source-order as the stable tiebreaker.
    selected.sort(key=lambda item: (item[0], item[1]))
    return [row for _time, _index, row in selected[: max(1, int(limit))]]


def boundary_event_evidence(
    events: list[dict[str, Any]],
    temporal_analysis: dict[str, Any] | None,
    *,
    max_delta_seconds: float = 8.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Keep source rows close to observed interval boundaries.

    This selection is independent of the ordinary newest-first presentation cap.
    A long history can therefore accumulate newer daytime events without pushing
    materially relevant command/state rows near an earlier investigated boundary
    out of the evidence receipt.
    """

    if not isinstance(temporal_analysis, dict):
        return []
    intervals = temporal_analysis.get("intervals")
    if not isinstance(intervals, list):
        return []

    boundaries: list[datetime] = []
    for interval in intervals:
        if not isinstance(interval, dict):
            continue
        for key in ("start", "end"):
            parsed = _parse_timestamp(interval.get(key))
            if parsed is not None:
                boundaries.append(parsed)
    if not boundaries:
        return []

    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        event_time = _parse_timestamp(item.get("date") or item.get("timestamp"))
        if event_time is None:
            continue
        nearest = min(
            abs((event_time - boundary).total_seconds())
            for boundary in boundaries
        )
        if nearest > max(0.0, float(max_delta_seconds)):
            continue
        row = {
            key: item.get(key)
            for key in (
                "name",
                "value",
                "unit",
                "description",
                "date",
                "isStateChange",
            )
            if key in item
        }
        row["boundaryDeltaSeconds"] = round(nearest, 3)
        ranked.append((nearest, index, row))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [row for _delta, _index, row in ranked[: max(1, int(limit))]]


def history_temporal_evidence_details(result_data: Any) -> dict[str, Any] | None:
    """Return bounded history proof for evidence output.

    Temporal state histories retain their interval analysis, while event-style
    histories (buttons, remotes, custom events) retain a small set of timestamped
    rows. This lets final synthesis reason across heterogeneous evidence instead
    of losing controller provenance merely because it is not a binary state pair.
    """

    if not isinstance(result_data, dict):
        return None
    temporal = result_data.get("temporalAnalysis")

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
        "windowed",
        "windowLabel",
        "windowStart",
        "windowEnd",
        "windowOngoing",
        "boundaryStateKnown",
        "boundaryBasis",
        "sourceCompleteToWindowStart",
        "pageCompleteToWindowStart",
        "sourceIntegrity",
        "sourceIntegrityVerified",
        "durationReliability",
        "observedBoundedIntervalsOnly",
        "unboundedActiveInterval",
        "openActiveInterval",
        "openActiveStart",
        "openActiveStartNatural",
        "inferredBoundaryState",
        "analyzedStateEventCount",
        "firstWindowStateEvent",
        "predecessorStateEvent",
    )
    temporal_details: dict[str, Any] = {}
    if isinstance(temporal, dict):
        temporal_details = {
            key: temporal.get(key)
            for key in temporal_keys
            if key in temporal
        }
    intervals = temporal.get("intervals") if isinstance(temporal, dict) else None
    if isinstance(intervals, list):
        # Keep the deterministic bounded interval proof visible to final
        # synthesis without copying raw Hubitat rows. Twelve intervals is enough
        # for auditability while keeping evidence receipts compact.
        temporal_details["observedIntervals"] = [
            {
                key: item.get(key)
                for key in (
                    "start",
                    "end",
                    "startNatural",
                    "endNatural",
                    "durationSeconds",
                    "duration",
                    "clippedAtWindowStart",
                    "clippedAtWindowEnd",
                )
                if key in item
            }
            for item in intervals[:12]
            if isinstance(item, dict)
        ]
        temporal_details["observedIntervalsTruncated"] = len(intervals) > 12

    details = {
        "label": result_data.get("label"),
        "attribute": result_data.get("attribute"),
        "hoursBack": result_data.get("hoursBack"),
        "timeWindow": result_data.get("timeWindow"),
    }
    room = str(result_data.get("room") or "").strip()
    if room:
        details["room"] = room
    if temporal_details:
        details["temporalAnalysis"] = temporal_details

    events = result_data.get("events")
    window_events = result_data.get("windowEvents")
    if not isinstance(window_events, list) and isinstance(events, list):
        window_events = window_event_evidence(
            events,
            result_data.get("timeWindow")
            if isinstance(result_data.get("timeWindow"), dict)
            else None,
        )
    if isinstance(window_events, list):
        bounded_window_events = [
            {
                key: item.get(key)
                for key in (
                    "name",
                    "value",
                    "unit",
                    "description",
                    "date",
                    "isStateChange",
                )
                if key in item
            }
            for item in window_events[:24]
            if isinstance(item, dict)
        ]
        if bounded_window_events:
            details["windowEvents"] = bounded_window_events
            details["windowEventsTruncated"] = len(window_events) > 24

    boundary_events = result_data.get("boundaryEvents")
    if isinstance(boundary_events, list):
        bounded_boundary_events = [
            {
                key: item.get(key)
                for key in (
                    "name",
                    "value",
                    "unit",
                    "description",
                    "date",
                    "isStateChange",
                    "boundaryDeltaSeconds",
                )
                if key in item
            }
            for item in boundary_events[:20]
            if isinstance(item, dict)
        ]
        if bounded_boundary_events:
            details["boundaryEvents"] = bounded_boundary_events
            details["boundaryEventsTruncated"] = len(boundary_events) > 20

    if isinstance(events, list):
        observed_events: list[dict[str, Any]] = []
        for item in events[:16]:
            if not isinstance(item, dict):
                continue
            observed_events.append({
                key: item.get(key)
                for key in (
                    "name",
                    "value",
                    "unit",
                    "description",
                    "date",
                    "isStateChange",
                )
                if key in item
            })
        if observed_events:
            details["observedEvents"] = observed_events
            details["observedEventsTruncated"] = len(events) > 16
    for key in (
        "analysisEventCount",
        "sourceEventCount",
        "historySourceIntegrity",
        "historySourceIntegrityVerified",
    ):
        if key in result_data:
            details[key] = result_data.get(key)
    if "attributeInferred" in result_data:
        details["attributeInferred"] = bool(result_data.get("attributeInferred"))
    meaningful = (
        bool(temporal_details)
        or bool(details.get("observedEvents"))
        or bool(details.get("windowEvents"))
        or bool(details.get("boundaryEvents"))
        or any(
            key in result_data
            for key in (
                "analysisEventCount",
                "sourceEventCount",
                "historySourceIntegrity",
                "historySourceIntegrityVerified",
            )
        )
    )
    return details if meaningful else None


def guard_history_duration_claim(
    message: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Keep explicit duration wording within the reliability of current evidence."""

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
    if not total_duration or interval_count < 0:
        return text, False

    source_integrity_verified = temporal.get("sourceIntegrityVerified")
    if source_integrity_verified is None:
        source_integrity_verified = details.get("historySourceIntegrityVerified")
    reliability = str(temporal.get("durationReliability") or "").strip().casefold()
    source_integrity = str(
        temporal.get("sourceIntegrity")
        or details.get("historySourceIntegrity")
        or ""
    ).strip().casefold()
    unverified_stream = (
        source_integrity_verified is False
        or reliability == "unverified-event-stream"
        or source_integrity == "unverified"
    )

    label = str(details.get("label") or "The device").strip() or "The device"
    active_state = str(temporal.get("activeState") or "active").strip() or "active"
    inactive_state = str(temporal.get("inactiveState") or "inactive").strip() or "inactive"
    window_label = str(temporal.get("windowLabel") or "").strip()
    window_suffix = f" {window_label}" if window_label else ""

    if unverified_stream:
        # Interval-count prose such as "five observed intervals in total" is
        # cardinality, not a duration claim. Do not let the duration guard erase
        # it merely because the word "total" appears. Continuity/exactness claims
        # remain guarded even when they contain no numeric duration.
        duration_mentions = _duration_mentions_seconds(text)
        if (
            not duration_mentions
            and _UNVERIFIED_EXACTNESS_CLAIM.search(text) is None
        ):
            return text, False
        if interval_count == 0:
            corrected = (
                f"No bounded {active_state} interval was established for {label}"
                f"{window_suffix} by the recorded device-event rows. The event "
                f"stream has not been independently verified as complete, so "
                f"this does not prove it stayed {inactive_state} or establish an "
                "exact total."
            )
            return corrected, True

        interval_word = "interval" if interval_count == 1 else "intervals"
        corrected = (
            f"Pairing the recorded state rows gives an {active_state}-time "
            f"estimate of {total_duration} for {label}{window_suffix} across "
            f"{interval_count} observed {interval_word}. The device-event "
            "stream has not been independently verified as complete, so this "
            "is not an exact total or a mathematical lower bound."
        )
        expected = _display_duration_seconds(total_seconds)
        mentions = _duration_mentions_seconds(text)
        if (
            expected in mentions
            and _UNVERIFIED_ESTIMATE_QUALIFIER.search(text) is not None
            and _UNVERIFIED_EXACTNESS_CLAIM.search(text) is None
        ):
            return text, False
        localized, changed = _replace_unverified_totalish_sentences(
            text,
            replacement=corrected,
            expected_seconds=expected,
        )
        # A totalish claim was detected at function entry. If sentence
        # segmentation somehow could not isolate it, retain the original
        # fail-closed behaviour rather than leaking an unsafe exact claim.
        # Never replace the whole synthesis merely because a local claim could
        # not be isolated. Final safety correction is clause/line-scoped; the
        # model's supported causal analysis must survive serialization.
        return (localized, True) if changed else (text, False)

    mentions = _duration_mentions_seconds(text)
    if not mentions:
        return text, False
    expected = _display_duration_seconds(total_seconds)
    if expected in mentions:
        return text, False

    lower_bound = bool(temporal.get("totalIsLowerBound"))
    qualifier = "at least " if lower_bound else ""
    if interval_count == 0:
        corrected = (
            f"{label} had a total of {qualifier}{total_duration} in the "
            f"{active_state} state{window_suffix}."
        )
    else:
        interval_word = "interval" if interval_count == 1 else "separate intervals"
        corrected = (
            f"{label} was {active_state} for a total of {qualifier}{total_duration}"
            f"{window_suffix} across {interval_count} {interval_word}."
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
    "analyze_state_intervals_in_window",
    "boundary_event_evidence",
    "window_event_evidence",
    "guard_history_duration_claim",
    "history_temporal_evidence_details",
]
