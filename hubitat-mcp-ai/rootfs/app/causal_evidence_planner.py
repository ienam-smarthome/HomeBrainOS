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


def _candidate_history_arguments(
    room_filter: dict[str, Any],
    *,
    key: str,
    allowed_attributes: set[str] | None = None,
    limit: int = 2,
) -> list[dict[str, Any]]:
    if not isinstance(room_filter, dict):
        return []
    hints = room_filter.get("eventSourceHints")
    if not isinstance(hints, dict):
        return []
    candidates = hints.get(key)
    if not isinstance(candidates, list) or not candidates:
        return []

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        label = str(candidate.get("label") or "").strip()
        attrs = [
            str(value).strip()
            for value in (candidate.get("suggestedHistoryAttributes") or [])
            if str(value).strip()
        ]
        if not label or not attrs:
            continue
        attribute = attrs[0]
        if (
            allowed_attributes is not None
            and attribute.casefold() not in allowed_attributes
        ):
            continue
        rows.append({
            "name": label,
            "attribute": attribute,
            "candidate": dict(candidate),
        })
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def controller_history_candidates(
    room_filter: dict[str, Any],
    *,
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Return bounded ranked controller history requests plus candidate metadata."""

    return _candidate_history_arguments(
        room_filter,
        key="controllerCandidates",
        limit=limit,
    )


def controller_history_arguments(
    room_filter: dict[str, Any],
) -> dict[str, str] | None:
    """Compatibility wrapper returning the highest-ranked controller only."""

    rows = controller_history_candidates(room_filter, limit=1)
    if not rows:
        return None
    return {
        "name": str(rows[0]["name"]),
        "attribute": str(rows[0]["attribute"]),
    }


def trigger_sensor_history_candidates(
    room_filter: dict[str, Any],
    *,
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Return bounded ranked occupancy history requests plus candidate metadata."""

    return _candidate_history_arguments(
        room_filter,
        key="triggerSensorCandidates",
        allowed_attributes={"motion", "presence"},
        limit=limit,
    )


def trigger_sensor_history_arguments(
    room_filter: dict[str, Any],
) -> dict[str, str] | None:
    """Compatibility wrapper returning the highest-ranked occupancy source only."""

    rows = trigger_sensor_history_candidates(room_filter, limit=1)
    if not rows:
        return None
    return {
        "name": str(rows[0]["name"]),
        "attribute": str(rows[0]["attribute"]),
    }


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
    end_after_slop_seconds: float = 2.0,
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
                if value not in inactive_values:
                    continue
                if signed < -end_delay_seconds or signed > end_after_slop_seconds:
                    continue
                rank = abs(signed)
            candidates.append((rank, event_time, row))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0])
        delta, event_time, row = candidates[0]
        producer = row.get("producedBy")
        producer_info = dict(producer) if isinstance(producer, dict) else {}
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
            "producedBy": producer_info or None,
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



def _history_match_basis(
    history: dict[str, Any] | None,
    subject_room: str,
) -> str:
    if not isinstance(history, dict):
        return ""
    explicit = str(history.get("candidateMatchBasis") or "").strip()
    if explicit:
        return explicit
    room = " ".join(str(history.get("room") or "").strip().casefold().split())
    wanted = " ".join(str(subject_room or "").strip().casefold().split())
    return "room" if room and wanted and room == wanted else "label-affinity"


def _controller_analysis(
    subject_history: dict[str, Any],
    history: dict[str, Any],
    *,
    requested_role: str,
    opposite_role: str,
    requested_time: datetime | None,
) -> dict[str, Any]:
    rows = controller_boundary_alignments(subject_history, history)
    relevant = [row for row in rows if row.get("boundaryRole") == requested_role]
    opposite = [row for row in rows if row.get("boundaryRole") == opposite_role]

    def requested(row: dict[str, Any]) -> bool:
        if requested_time is None:
            return False
        row_time = _timestamp(row.get("subjectTransition"))
        return (
            row_time is not None
            and abs((row_time - requested_time).total_seconds()) <= 0.25
        )

    return {
        "label": history.get("label"),
        "attribute": history.get("attribute"),
        "room": history.get("room"),
        "matchBasis": _history_match_basis(
            history,
            str(subject_history.get("room") or ""),
        ),
        "relevantAlignments": relevant[:8],
        "oppositeAlignments": opposite[:8],
        "requestedMatched": any(requested(row) for row in relevant),
    }


def _sensor_analysis(
    subject_history: dict[str, Any],
    history: dict[str, Any],
    *,
    requested_role: str,
    opposite_role: str,
    requested_time: datetime | None,
) -> dict[str, Any]:
    rows = sensor_transition_correlations(
        subject_history,
        history,
        start_delta_seconds=5.0,
        end_delay_seconds=45.0,
        end_after_slop_seconds=2.0,
    )
    relevant = [row for row in rows if row.get("boundaryRole") == requested_role]
    opposite = [row for row in rows if row.get("boundaryRole") == opposite_role]

    def requested(row: dict[str, Any]) -> bool:
        if requested_time is None:
            return False
        row_time = _timestamp(row.get("subjectTransition"))
        return (
            row_time is not None
            and abs((row_time - requested_time).total_seconds()) <= 0.25
        )

    after_count = sum(
        1
        for row in relevant
        if float(row.get("signedDeltaSeconds") or 0) > 0
    )
    producer_labels = sorted({
        str(producer.get("label") or producer.get("name") or "").strip()
        for row in [*relevant, *opposite]
        for producer in [row.get("producedBy")]
        if isinstance(producer, dict)
        and str(producer.get("label") or producer.get("name") or "").strip()
    })
    return {
        "label": history.get("label"),
        "attribute": history.get("attribute"),
        "room": history.get("room"),
        "matchBasis": _history_match_basis(
            history,
            str(subject_history.get("room") or ""),
        ),
        "relevantCorrelations": relevant[:12],
        "oppositeCorrelations": opposite[:12],
        "requestedMatched": any(requested(row) for row in relevant),
        "afterSubjectCount": after_count,
        "producerLabels": producer_labels,
        "repeatedUpstreamPattern": (
            requested_role == "start"
            and len(relevant) >= 2
            and after_count >= 2
        ),
    }


def _level_recovery_pattern(
    subject_history: dict[str, Any],
    detail_history: dict[str, Any] | None,
    *,
    requested_boundary: Any,
) -> dict[str, Any]:
    if not isinstance(detail_history, dict):
        return {}

    raw_events = detail_history.get("events")
    if not isinstance(raw_events, list):
        return {}

    events: list[tuple[datetime, dict[str, Any]]] = []
    for row in raw_events:
        if not isinstance(row, dict):
            continue
        ts = _timestamp(row.get("date") or row.get("timestamp"))
        if ts is not None:
            events.append((ts, row))
    if not events:
        return {}
    events.sort(key=lambda item: item[0])

    starts = [
        row for row in _subject_interval_boundaries(subject_history)
        if row.get("role") == "start" and isinstance(row.get("time"), datetime)
    ]
    requested = _timestamp(requested_boundary)
    matches: list[dict[str, Any]] = []

    for boundary in starts:
        boundary_time = boundary["time"]
        level_rows: list[tuple[float, datetime, dict[str, Any]]] = []
        command_rows: list[tuple[float, datetime, dict[str, Any]]] = []

        for event_time, row in events:
            signed = (event_time - boundary_time).total_seconds()
            if signed < 0 or signed > 5.0:
                continue
            name = str(row.get("name") or "").strip().casefold()
            if name == "level":
                level_rows.append((signed, event_time, row))
            elif name == "command-setlevel":
                producer = row.get("producedBy")
                if isinstance(producer, dict) and str(
                    producer.get("label") or ""
                ).strip():
                    command_rows.append((signed, event_time, row))

        if not level_rows or not command_rows:
            continue

        level_rows.sort(key=lambda item: item[0])
        command_rows.sort(key=lambda item: item[0])
        command_delta, command_time, command_row = command_rows[0]

        # Two valid downstream recovery shapes are observed live:
        #
        #   ON -> bridge level -> app setLevel
        #   ON -> app setLevel -> resulting bridge level
        #
        # Keep them distinct so a resulting level is never called an initial
        # level merely because it happened close to the ON boundary.
        before_command = [
            item
            for item in level_rows
            if item[0] <= min(1.0, command_delta)
        ]
        after_command = [
            item
            for item in level_rows
            if command_delta <= item[0] <= min(5.0, command_delta + 2.0)
        ]

        sequence = ""
        level_delta: float
        level_time: datetime
        level_row: dict[str, Any]
        initial_level: float | None = None
        result_level: float | None = None

        if before_command:
            level_delta, level_time, level_row = before_command[0]
            sequence = "level-before-command"
            try:
                initial_level = float(level_row.get("value"))
            except (TypeError, ValueError):
                initial_level = None
        elif after_command:
            level_delta, level_time, level_row = after_command[0]
            sequence = "command-before-level"
            try:
                result_level = float(level_row.get("value"))
            except (TypeError, ValueError):
                result_level = None
        else:
            continue

        producer = dict(command_row.get("producedBy") or {})
        matches.append({
            "subjectTransition": boundary_time.isoformat(),
            "sequence": sequence,
            "levelEvent": level_time.isoformat(),
            "levelValue": (
                initial_level if initial_level is not None else result_level
            ),
            "initialLevel": initial_level,
            "resultLevel": result_level,
            "levelDeltaSeconds": round(level_delta, 3),
            "commandEvent": command_time.isoformat(),
            "commandDeltaSeconds": round(command_delta, 3),
            "commandDescription": (
                command_row.get("description")
                or command_row.get("descriptionText")
            ),
            "producer": producer,
            "requestedMatched": (
                requested is not None
                and abs((boundary_time - requested).total_seconds()) <= 0.25
            ),
        })

    if not matches:
        return {}

    producer_counts: dict[str, int] = {}
    for row in matches:
        label = str((row.get("producer") or {}).get("label") or "").strip()
        if label:
            producer_counts[label] = producer_counts.get(label, 0) + 1
    producer_label = (
        max(producer_counts, key=producer_counts.get)
        if producer_counts
        else ""
    )
    high_level_count = sum(
        1
        for row in matches
        if isinstance(row.get("initialLevel"), (int, float))
        and float(row["initialLevel"]) >= 99.0
    )
    level_before_count = sum(
        1 for row in matches if row.get("sequence") == "level-before-command"
    )
    command_before_count = sum(
        1 for row in matches if row.get("sequence") == "command-before-level"
    )
    return {
        "matchCount": len(matches),
        "transitionCount": len(starts),
        "requestedMatched": any(row.get("requestedMatched") for row in matches),
        "highInitialLevelCount": high_level_count,
        "levelBeforeCommandCount": level_before_count,
        "commandBeforeLevelCount": command_before_count,
        "producerLabel": producer_label or None,
        "matches": matches[:12],
    }


def build_reporting_source_secondary_analysis(
    subject_history: dict[str, Any],
    *,
    transition: str,
    requested_boundary: Any,
    controller_history: dict[str, Any] | None = None,
    sensor_history: dict[str, Any] | None = None,
    controller_histories: list[dict[str, Any]] | None = None,
    sensor_histories: list[dict[str, Any]] | None = None,
    subject_event_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build bounded deterministic correlation around an external reporting source."""

    action = str(transition or "").strip().casefold()
    requested_role = {"on": "start", "off": "end"}.get(action)
    if requested_role is None:
        return {}

    boundaries = _subject_interval_boundaries(subject_history)
    requested_time = _timestamp(requested_boundary)
    relevant_boundaries = [
        row for row in boundaries if row.get("role") == requested_role
    ]
    opposite_role = "end" if requested_role == "start" else "start"

    controller_inputs = [
        item for item in (controller_histories or []) if isinstance(item, dict)
    ]
    sensor_inputs = [
        item for item in (sensor_histories or []) if isinstance(item, dict)
    ]
    if isinstance(controller_history, dict) and not controller_inputs:
        controller_inputs = [controller_history]
    if isinstance(sensor_history, dict) and not sensor_inputs:
        sensor_inputs = [sensor_history]

    controllers = [
        _controller_analysis(
            subject_history,
            item,
            requested_role=requested_role,
            opposite_role=opposite_role,
            requested_time=requested_time,
        )
        for item in controller_inputs
    ]
    sensors = [
        _sensor_analysis(
            subject_history,
            item,
            requested_role=requested_role,
            opposite_role=opposite_role,
            requested_time=requested_time,
        )
        for item in sensor_inputs
    ]

    recovery = (
        _level_recovery_pattern(
            subject_history,
            subject_event_history,
            requested_boundary=requested_boundary,
        )
        if action == "on"
        else {}
    )

    return {
        "subject": subject_history.get("label"),
        "room": subject_history.get("room"),
        "transition": action,
        "requestedBoundary": (
            requested_time.isoformat() if requested_time is not None else None
        ),
        "transitionCount": len(relevant_boundaries),
        "controllers": controllers,
        "sensors": sensors,
        # Compatibility aliases for the established single-candidate contract.
        "controller": controllers[0] if controllers else {
            "label": None,
            "attribute": None,
            "room": None,
            "matchBasis": None,
            "relevantAlignments": [],
            "oppositeAlignments": [],
            "requestedMatched": False,
        },
        "sensor": sensors[0] if sensors else {
            "label": None,
            "attribute": None,
            "room": None,
            "matchBasis": None,
            "relevantCorrelations": [],
            "oppositeCorrelations": [],
            "requestedMatched": False,
            "afterSubjectCount": 0,
            "repeatedUpstreamPattern": False,
        },
        "levelRecovery": recovery,
    }

def _delta_phrase(row: dict[str, Any]) -> str:
    try:
        signed = float(row.get("signedDeltaSeconds"))
    except (TypeError, ValueError):
        return "at nearly the same time"
    seconds = abs(signed)
    number = f"{seconds:.3f}".rstrip("0").rstrip(".")
    if signed > 0:
        return f"{number}s after"
    if signed < 0:
        return f"{number}s before"
    return "at the same time as"


def _candidate_phrase(
    item: dict[str, Any],
    *,
    kind: str,
    subject_room: str,
) -> str:
    label = str(item.get("label") or "").strip()
    room = str(item.get("room") or "").strip()
    basis = str(item.get("matchBasis") or "").strip()
    normalized_room = " ".join(room.casefold().split())
    normalized_subject = " ".join(subject_room.casefold().split())

    if (
        basis == "room"
        and normalized_room
        and normalized_room == normalized_subject
    ):
        return f"same-room {kind} {label}"
    if basis == "label-affinity":
        if room:
            return (
                f"{kind} candidate {label} (label-associated with {subject_room}, "
                f"but assigned to Hubitat room {room})"
            )
        return f"{kind} candidate {label} (label-associated with {subject_room})"
    if room:
        return f"{kind} {label} (Hubitat room {room})"
    return f"{kind} {label}"


def render_reporting_source_secondary_analysis(
    analysis: dict[str, Any],
) -> str | None:
    """Render bounded multi-candidate correlation without overstating causation."""

    if not isinstance(analysis, dict):
        return None
    transition = str(analysis.get("transition") or "").strip().casefold()
    role_word = "ON" if transition == "on" else "OFF" if transition == "off" else ""
    if not role_word:
        return None

    subject_room = str(analysis.get("room") or "").strip()
    paragraphs: list[str] = []

    controllers = [
        row for row in analysis.get("controllers", [])
        if isinstance(row, dict)
    ]
    if not controllers and isinstance(analysis.get("controller"), dict):
        controllers = [analysis["controller"]]

    for controller in controllers:
        label = str(controller.get("label") or "").strip()
        if not label:
            continue
        phrase = _candidate_phrase(
            controller,
            kind="controller",
            subject_room=subject_room,
        )
        relevant = [
            row for row in controller.get("relevantAlignments", [])
            if isinstance(row, dict)
        ]
        opposite = [
            row for row in controller.get("oppositeAlignments", [])
            if isinstance(row, dict)
        ]
        if relevant:
            paragraphs.append(
                f"The checked {phrase} had {len(relevant)} {role_word} boundary "
                "alignment(s). "
                + (
                    "One aligns with the specific requested transition. "
                    if controller.get("requestedMatched")
                    else "None aligns with the specific requested transition. "
                )
                + "Controller timing is corroborating evidence only unless a "
                "direct command/producer row establishes causation."
            )
        elif opposite:
            opposite_word = "OFF" if role_word == "ON" else "ON"
            paragraphs.append(
                f"The checked {phrase} did not align with the {role_word} "
                f"boundaries. It did align with {len(opposite)} {opposite_word} "
                f"boundary event(s), which is evidence about those "
                f"{opposite_word} transitions, not the requested {role_word} "
                "transition."
            )
        else:
            paragraphs.append(
                f"The checked {phrase} had no event within 2 seconds of the "
                f"observed {role_word} boundaries."
            )

    sensors = [
        row for row in analysis.get("sensors", [])
        if isinstance(row, dict)
    ]
    if not sensors and isinstance(analysis.get("sensor"), dict):
        sensors = [analysis["sensor"]]

    transition_count = int(analysis.get("transitionCount") or 0)
    for sensor in sensors:
        label = str(sensor.get("label") or "").strip()
        if not label:
            continue
        phrase = _candidate_phrase(
            sensor,
            kind="motion/presence source",
            subject_room=subject_room,
        )
        relevant = [
            row for row in sensor.get("relevantCorrelations", [])
            if isinstance(row, dict)
        ]
        opposite = [
            row for row in sensor.get("oppositeCorrelations", [])
            if isinstance(row, dict)
        ]

        if relevant:
            timings = ", ".join(_delta_phrase(row) for row in relevant[:4])
            paragraphs.append(
                f"For the checked {phrase}, {len(relevant)} of "
                f"{transition_count or len(relevant)} observed {role_word} "
                f"transition(s) had a matching "
                f"{sensor.get('attribute') or 'sensor'} edge within the bounded "
                f"window ({timings}). "
                + (
                    "The specific requested transition also has such an edge."
                    if sensor.get("requestedMatched")
                    else "The specific requested transition does not have such an "
                    "edge within the bounded window."
                )
            )
        else:
            paragraphs.append(
                f"The checked {phrase} had no bounded correlation with the "
                f"observed {role_word} transitions."
            )

        if sensor.get("repeatedUpstreamPattern"):
            paragraphs.append(
                f"In multiple ON transitions the light/device changed before "
                f"Hubitat recorded {label} becoming active. That repeated ordering "
                f"is consistent with an upstream or outside-Hubitat relationship "
                f"involving {label}, but it does not prove that {label} triggered "
                "the device and it does not identify a specific external hub or "
                "automation."
            )
        if opposite and role_word == "ON":
            timings = ", ".join(_delta_phrase(row) for row in opposite[:5])
            paragraphs.append(
                f"{label} also had {len(opposite)} inactive edge(s) correlated "
                f"with observed OFF boundaries ({timings}). That strengthens the "
                "repeated timing pattern, but remains temporal correlation rather "
                "than direct producer evidence."
            )

    shared_producers: dict[str, list[str]] = {}
    for sensor in sensors:
        label = str(sensor.get("label") or "").strip()
        producers = [
            str(value).strip()
            for value in (sensor.get("producerLabels") or [])
            if str(value).strip()
        ]
        if label and len(producers) == 1:
            shared_producers.setdefault(producers[0], []).append(label)
    for producer, labels in shared_producers.items():
        unique_labels = list(dict.fromkeys(labels))
        if len(unique_labels) < 2:
            continue
        if len(unique_labels) == 2:
            joined = f"{unique_labels[0]} and {unique_labels[1]}"
        else:
            joined = ", ".join(unique_labels[:-1]) + f", and {unique_labels[-1]}"
        paragraphs.append(
            f"{joined} are both reported into Hubitat through {producer}. Their "
            "matching timing therefore should not be treated as independent "
            "upstream confirmations. This identifies a shared reporting path, "
            "not the automation or action that initiated the light/device change."
        )

    recovery = analysis.get("levelRecovery")
    if isinstance(recovery, dict) and recovery.get("matchCount"):
        count = int(recovery.get("matchCount") or 0)
        total = int(recovery.get("transitionCount") or count)
        high = int(recovery.get("highInitialLevelCount") or 0)
        level_first = int(recovery.get("levelBeforeCommandCount") or 0)
        command_first = int(recovery.get("commandBeforeLevelCount") or 0)
        producer = str(recovery.get("producerLabel") or "").strip()
        examples = [
            row for row in recovery.get("matches", [])
            if isinstance(row, dict)
        ][:4]

        example_texts: list[str] = []
        for row in examples:
            sequence = str(row.get("sequence") or "")
            level_delta = float(row.get("levelDeltaSeconds") or 0)
            command_delta = float(row.get("commandDeltaSeconds") or 0)
            if (
                sequence == "level-before-command"
                and isinstance(row.get("initialLevel"), (int, float))
            ):
                example_texts.append(
                    f"level {row.get('initialLevel'):g} at {level_delta:g}s, "
                    f"recovery command at {command_delta:g}s"
                )
            elif (
                sequence == "command-before-level"
                and isinstance(row.get("resultLevel"), (int, float))
            ):
                example_texts.append(
                    f"recovery command at {command_delta:g}s, resulting level "
                    f"{row.get('resultLevel'):g} at {level_delta:g}s"
                )

        producer_text = f" from {producer}" if producer else ""
        sequence_parts: list[str] = []
        if level_first:
            sequence_parts.append(
                f"{level_first} level-first sequence(s)"
            )
        if command_first:
            sequence_parts.append(
                f"{command_first} command-first sequence(s)"
            )
        sequence_text = (
            "; " + ", ".join(sequence_parts)
            if sequence_parts
            else ""
        )
        paragraphs.append(
            f"Downstream level-recovery pattern: {count} of {total} observed ON "
            f"transition(s) had a setLevel command{producer_text} within 5 seconds "
            f"and a nearby level event{sequence_text}; {high} began at about "
            "level 100. "
            + (
                f"Examples: {', '.join(example_texts)}. "
                if example_texts
                else ""
            )
            + "Because those setLevel commands occur after the ON boundary, they "
            "are evidence of recovery/adjustment after the light was already on, "
            "not evidence that the app initiated the ON."
        )
        if recovery.get("requestedMatched"):
            paragraphs.append(
                "The specific requested ON transition also shows this downstream "
                "level-recovery pattern."
            )

    if not paragraphs:
        return None
    return "\n\n".join(paragraphs)

def render_reporting_source_secondary_evidence(
    evidence: list[dict[str, Any]],
) -> str | None:
    for receipt in reversed(evidence):
        if (
            isinstance(receipt, dict)
            and receipt.get("success") is True
            and receipt.get("tool") == "homebrain_causal_secondary_correlation"
            and isinstance(receipt.get("details"), dict)
        ):
            return render_reporting_source_secondary_analysis(receipt["details"])
    return None

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
    """Return bounded subject transitions for correlation.

    Explicit causal prefetch can retain several switch rows from the same
    authoritative source page as `correlationEvents`. Prefer those rows so a
    bounded secondary investigation can compare repeated transitions without
    re-reading the subject. Fall back to interval analysis for older/general
    callers.
    """

    correlation_events = subject_history.get("correlationEvents")
    if isinstance(correlation_events, list):
        boundaries: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in correlation_events:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip().casefold() != "switch":
                continue
            value = str(item.get("value") or "").strip().casefold()
            role = "start" if value == "on" else "end" if value == "off" else ""
            event_time = _timestamp(item.get("date") or item.get("timestamp"))
            if not role or event_time is None:
                continue
            key = (role, event_time.isoformat())
            if key in seen:
                continue
            seen.add(key)
            boundaries.append({
                "role": role,
                "time": event_time,
                "intervalIndex": len(boundaries) + 1,
                "source": "correlationEvents",
            })
        if boundaries:
            boundaries.sort(key=lambda item: item["time"])
            return boundaries

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
    "build_reporting_source_secondary_analysis",
    "render_reporting_source_secondary_analysis",
    "render_reporting_source_secondary_evidence",
    "render_sensor_correlation_instruction",
    "sensor_transition_correlations",
    "subject_has_observed_intervals",
    "subject_room_filter_arguments",
    "trigger_sensor_history_arguments",
]
