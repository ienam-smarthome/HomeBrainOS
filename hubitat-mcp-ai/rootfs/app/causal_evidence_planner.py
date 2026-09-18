"""Deterministic evidence planning for causal device-history investigations.

The planner chooses *which evidence classes to acquire*, not the causal answer.
It uses resolved subject metadata to remove model-dependent room-filter syntax and
ranks controller provenance ahead of weaker environmental correlation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from natural_datetime import normalize_iso_offset


def subject_room_filter_arguments(
    subject_history: dict[str, Any],
) -> dict[str, Any] | None:
    """Return one exact-room discovery read for a resolved subject."""

    if not isinstance(subject_history, dict):
        return None
    room = str(subject_history.get("room") or "").strip()
    if not room:
        return None
    return {
        "attribute": "room",
        "operator": "eq",
        "value": room,
    }


def controller_history_arguments(
    room_filter: dict[str, Any],
) -> dict[str, str] | None:
    """Return one highest-ranked controller history read from room evidence."""

    if not isinstance(room_filter, dict):
        return None
    hints = room_filter.get("eventSourceHints")
    if not isinstance(hints, dict):
        return None
    candidates = hints.get("controllerCandidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return None
    label = str(candidate.get("label") or "").strip()
    attrs = [
        str(value).strip()
        for value in (candidate.get("suggestedHistoryAttributes") or [])
        if str(value).strip()
    ]
    if not label or not attrs:
        return None
    return {"name": label, "attribute": attrs[0]}


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _subject_active_starts(subject_history: dict[str, Any]) -> list[datetime]:
    temporal = subject_history.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return []
    intervals = temporal.get("observedIntervals")
    if not isinstance(intervals, list):
        intervals = temporal.get("intervals")
    if not isinstance(intervals, list):
        return []
    starts: list[datetime] = []
    for item in intervals:
        if not isinstance(item, dict):
            continue
        parsed = _timestamp(item.get("start"))
        if parsed is not None:
            starts.append(parsed)
    return starts


def _controller_events(controller_history: dict[str, Any]) -> list[tuple[datetime, dict[str, Any]]]:
    rows = controller_history.get("events")
    if not isinstance(rows, list):
        return []
    result: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed = _timestamp(row.get("date") or row.get("timestamp"))
        if parsed is not None:
            result.append((parsed, row))
    return result


def subject_has_observed_intervals(
    subject_history: dict[str, Any],
) -> bool:
    """Return whether the current-turn subject history established any interval."""

    if not isinstance(subject_history, dict):
        return False
    temporal = subject_history.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return False
    intervals = temporal.get("observedIntervals")
    if not isinstance(intervals, list):
        intervals = temporal.get("intervals")
    return isinstance(intervals, list) and any(
        isinstance(item, dict)
        and str(item.get("start") or "").strip()
        and str(item.get("end") or "").strip()
        for item in intervals
    )


def controller_transition_alignments(
    subject_history: dict[str, Any],
    controller_history: dict[str, Any],
    *,
    max_delta_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Correlate controller events with subject active-interval starts.

    Close timing is provenance-strength evidence, not automatic proof of who
    operated a physical control. The caller decides how to phrase that distinction.
    """

    starts = _subject_active_starts(subject_history)
    controller_rows = _controller_events(controller_history)
    if not starts or not controller_rows:
        return []

    matches: list[dict[str, Any]] = []
    for start in starts:
        nearest: tuple[float, datetime, dict[str, Any]] | None = None
        for event_time, row in controller_rows:
            delta = abs((event_time - start).total_seconds())
            if delta > max_delta_seconds:
                continue
            if nearest is None or delta < nearest[0]:
                nearest = (delta, event_time, row)
        if nearest is None:
            continue
        delta, event_time, row = nearest
        matches.append({
            "subjectTransition": start.isoformat(),
            "controllerEvent": event_time.isoformat(),
            "deltaSeconds": round(delta, 3),
            "eventName": row.get("name") or row.get("attribute"),
            "eventValue": row.get("value"),
            "description": row.get("description") or row.get("descriptionText"),
        })
    return matches


def render_controller_alignment_instruction(
    alignments: list[dict[str, Any]],
) -> str | None:
    if not alignments:
        return None
    rows: list[str] = []
    for item in alignments[:6]:
        rows.append(
            f"{item.get('controllerEvent')} -> subject {item.get('subjectTransition')} "
            f"(delta {item.get('deltaSeconds')}s; "
            f"{item.get('eventName')}={item.get('eventValue')}; "
            f"{item.get('description') or 'no description'})"
        )
    return (
        "HOST CAUSAL EVIDENCE PRIORITY\n"
        "Direct controller event history aligns with one or more subject active "
        "transitions within two seconds:\n- "
        + "\n- ".join(rows)
        + "\nTreat these aligned controller events as stronger provenance evidence "
        "than environmental motion/illuminance correlation. Do not spend remaining "
        "evidence budget on weaker room sensors merely to explain an already-aligned "
        "turn-on transition. Use remaining reads to test downstream automation/rule/"
        "app/log behavior or genuinely unexplained transitions. Timing alignment does "
        "not by itself identify the person who operated a physical control."
    )


__all__ = [
    "controller_history_arguments",
    "controller_transition_alignments",
    "render_controller_alignment_instruction",
    "subject_has_observed_intervals",
    "subject_room_filter_arguments",
]
