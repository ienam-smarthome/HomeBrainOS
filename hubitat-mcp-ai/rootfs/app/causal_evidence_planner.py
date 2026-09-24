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


def trigger_sensor_history_arguments(
    room_filter: dict[str, Any],
) -> dict[str, str] | None:
    """Return one highest-ranked capability-grounded motion/presence history read."""

    if not isinstance(room_filter, dict):
        return None
    hints = room_filter.get("eventSourceHints")
    if not isinstance(hints, dict):
        return None
    candidates = hints.get("triggerSensorCandidates")
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
    if not label or not attrs or attrs[0].casefold() not in {"motion", "presence"}:
        return None
    return {"name": label, "attribute": attrs[0]}


def _sensor_events(sensor_history: dict[str, Any]) -> list[tuple[datetime, dict[str, Any]]]:
    rows = sensor_history.get("events")
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


def sensor_transition_correlations(
    subject_history: dict[str, Any],
    sensor_history: dict[str, Any],
    *,
    start_delta_seconds: float = 2.0,
    end_delay_seconds: float = 45.0,
) -> list[dict[str, Any]]:
    """Correlate one motion/presence source with subject interval boundaries."""

    attribute = str(sensor_history.get("attribute") or "").strip().casefold()
    if attribute == "motion":
        active_values = {"active"}
        inactive_values = {"inactive"}
    elif attribute == "presence":
        active_values = {"present"}
        inactive_values = {"not present", "not_present", "absent"}
    else:
        return []

    events = _sensor_events(sensor_history)
    if not events:
        return []
    boundaries = _subject_interval_boundaries(subject_history)
    matches: list[dict[str, Any]] = []

    for boundary in boundaries:
        boundary_time = boundary.get("time")
        role = str(boundary.get("role") or "")
        if not isinstance(boundary_time, datetime) or role not in {"start", "end"}:
            continue
        candidates: list[tuple[float, datetime, dict[str, Any]]] = []
        for event_time, row in events:
            value = str(row.get("value") or "").strip().casefold()
            signed = (event_time - boundary_time).total_seconds()
            if role == "start":
                if value not in active_values or abs(signed) > start_delta_seconds:
                    continue
                rank = abs(signed)
            else:
                if value not in inactive_values or signed > 0 or abs(signed) > end_delay_seconds:
                    continue
                rank = abs(signed)
            candidates.append((rank, event_time, row))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0])
        delta, event_time, row = candidates[0]
        matches.append({
            "boundaryRole": role,
            "intervalIndex": boundary.get("intervalIndex"),
            "openInterval": bool(boundary.get("open")),
            "subjectTransition": boundary_time.isoformat(),
            "sensorEvent": event_time.isoformat(),
            "signedDeltaSeconds": round((event_time - boundary_time).total_seconds(), 3),
            "deltaSeconds": round(delta, 3),
            "sensorLabel": sensor_history.get("label"),
            "attribute": attribute,
            "eventValue": row.get("value"),
            "description": row.get("description") or row.get("descriptionText"),
        })
    return matches


def render_sensor_correlation_instruction(
    correlations: list[dict[str, Any]],
) -> str | None:
    if not correlations:
        return None
    starts = [row for row in correlations if row.get("boundaryRole") == "start"]
    ends = [row for row in correlations if row.get("boundaryRole") == "end"]
    rows = [
        (
            f"{str(item.get('boundaryRole')).upper()} interval "
            f"{item.get('intervalIndex')}: sensor {item.get('sensorEvent')} vs "
            f"subject {item.get('subjectTransition')} (signed "
            f"{item.get('signedDeltaSeconds')}s; "
            f"{item.get('attribute')}={item.get('eventValue')})"
        )
        for item in correlations[:12]
    ]
    guidance = (
        f"Repeated pattern: {len(starts)} start alignment(s), "
        f"{len(ends)} delayed-off/end alignment(s). "
    )
    if len(starts) >= 2:
        after = sum(
            1 for row in starts if float(row.get("signedDeltaSeconds") or 0) > 0
        )
        guidance += (
            "This repeated motion/presence timing is materially stronger than a "
            "single incidental environmental correlation. "
        )
        if after >= 2:
            guidance += (
                "In multiple starts the subject changed before Hubitat recorded "
                "the sensor active edge; that ordering argues against a Hubitat "
                "automation reacting to that recorded edge. It may support an "
                "upstream/outside-Hubitat trigger, but do not name a specific "
                "external hub unless topology/config evidence supports it. "
            )
    return (
        "HOST CAUSAL MOTION/PRESENCE CORRELATION\n- "
        + "\n- ".join(rows)
        + "\n"
        + guidance
        + "Treat this as corroborating transition evidence, not automatic proof "
        "of a specific automation."
    )


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _subject_interval_boundaries(
    subject_history: dict[str, Any],
) -> list[dict[str, Any]]:
    temporal = subject_history.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return []
    intervals = temporal.get("observedIntervals")
    if not isinstance(intervals, list):
        intervals = temporal.get("intervals")
    boundaries: list[dict[str, Any]] = []
    if isinstance(intervals, list):
        for index, item in enumerate(intervals, start=1):
            if not isinstance(item, dict):
                continue
            start = _timestamp(item.get("start"))
            end = _timestamp(item.get("end"))
            if start is not None:
                boundaries.append({
                    "role": "start",
                    "time": start,
                    "intervalIndex": index,
                })
            if end is not None:
                boundaries.append({
                    "role": "end",
                    "time": end,
                    "intervalIndex": index,
                })

    open_start = _timestamp(temporal.get("openActiveStart"))
    if temporal.get("unboundedActiveInterval") and open_start is not None:
        boundaries.append({
            "role": "start",
            "time": open_start,
            "intervalIndex": len(intervals) + 1 if isinstance(intervals, list) else 1,
            "open": True,
        })
    return boundaries


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
    bounded = isinstance(intervals, list) and any(
        isinstance(item, dict)
        and str(item.get("start") or "").strip()
        and str(item.get("end") or "").strip()
        for item in intervals
    )
    if bounded:
        return True
    return bool(
        temporal.get("unboundedActiveInterval")
        and str(temporal.get("openActiveStart") or "").strip()
    )


def controller_boundary_alignments(
    subject_history: dict[str, Any],
    controller_history: dict[str, Any],
    *,
    max_delta_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Classify controller events by the nearest observed subject boundary.

    The nearest-boundary role is part of the evidence: an event near an interval
    end is evidence about the turn-off/end transition, not the earlier turn-on.
    """

    boundaries = _subject_interval_boundaries(subject_history)
    controller_rows = _controller_events(controller_history)
    if not boundaries or not controller_rows:
        return []

    matches: list[dict[str, Any]] = []
    for event_time, row in controller_rows:
        nearest: tuple[float, dict[str, Any]] | None = None
        for boundary in boundaries:
            boundary_time = boundary.get("time")
            if not isinstance(boundary_time, datetime):
                continue
            delta = abs((event_time - boundary_time).total_seconds())
            if nearest is None or delta < nearest[0]:
                nearest = (delta, boundary)
        if nearest is None or nearest[0] > max_delta_seconds:
            continue
        delta, boundary = nearest
        boundary_time = boundary["time"]
        matches.append({
            "subjectTransition": boundary_time.isoformat(),
            "boundaryRole": boundary.get("role"),
            "intervalIndex": boundary.get("intervalIndex"),
            "openInterval": bool(boundary.get("open")),
            "controllerEvent": event_time.isoformat(),
            "deltaSeconds": round(delta, 3),
            "signedDeltaSeconds": round(
                (event_time - boundary_time).total_seconds(), 3
            ),
            "eventName": row.get("name") or row.get("attribute"),
            "eventValue": row.get("value"),
            "description": row.get("description") or row.get("descriptionText"),
        })
    matches.sort(
        key=lambda item: (
            int(item.get("intervalIndex") or 0),
            0 if item.get("boundaryRole") == "start" else 1,
            float(item.get("deltaSeconds") or 0),
        )
    )
    return matches


def controller_transition_alignments(
    subject_history: dict[str, Any],
    controller_history: dict[str, Any],
    *,
    max_delta_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Compatibility view containing start/turn-on controller alignments only."""

    return [
        item
        for item in controller_boundary_alignments(
            subject_history,
            controller_history,
            max_delta_seconds=max_delta_seconds,
        )
        if item.get("boundaryRole") == "start"
    ]


def render_controller_alignment_instruction(
    alignments: list[dict[str, Any]],
) -> str | None:
    if not alignments:
        return None

    rows: list[str] = []
    has_start = False
    has_end = False
    for item in alignments[:8]:
        role = str(item.get("boundaryRole") or "start")
        has_start = has_start or role == "start"
        has_end = has_end or role == "end"
        rows.append(
            f"{role.upper()} boundary: {item.get('controllerEvent')} -> "
            f"subject {item.get('subjectTransition')} "
            f"(delta {item.get('deltaSeconds')}s, signed "
            f"{item.get('signedDeltaSeconds')}s; "
            f"{item.get('eventName')}={item.get('eventValue')}; "
            f"{item.get('description') or 'no description'})"
        )

    guidance: list[str] = []
    if has_start:
        guidance.append(
            "START-boundary controller events are stronger provenance evidence "
            "than environmental motion/illuminance correlation for a turn-on, "
            "although timing alone does not identify the person."
        )
    if has_end:
        guidance.append(
            "END-boundary controller events are evidence about the interval end/"
            "turn-off boundary only. Never cite an END-boundary controller event "
            "as evidence that it caused the earlier turn-on."
        )

    return (
        "HOST CAUSAL CONTROLLER BOUNDARY EVIDENCE\n- "
        + "\n- ".join(rows)
        + "\n"
        + " ".join(guidance)
        + " Use remaining reads for downstream automation/rule/app/log provenance "
        "or genuinely unexplained transitions rather than weaker room sensors."
    )


__all__ = [
    "controller_boundary_alignments",
    "controller_history_arguments",
    "controller_transition_alignments",
    "render_controller_alignment_instruction",
    "render_sensor_correlation_instruction",
    "sensor_transition_correlations",
    "subject_has_observed_intervals",
    "subject_room_filter_arguments",
    "trigger_sensor_history_arguments",
]
