"""Authoritative causal provenance from Hubitat command events.

Hubitat's device event history contains command-<name> rows separately from
attribute state changes. Command rows can include a producedBy value naming the
app/action that issued the command. That is stronger causal evidence than
timestamp-only correlation against logs and usually survives long after live
log buffers have rolled over.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from causal_timeline import build_causal_timeline_rows
from natural_datetime import normalize_iso_offset


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clock_text(value: Any) -> str:
    parsed = _parse_time(value)
    if parsed is None:
        return str(value or "").strip()
    return parsed.strftime("%I:%M:%S %p").lstrip("0")


def _duration_text(start: Any, end: Any) -> str:
    left = _parse_time(start)
    right = _parse_time(end)
    if left is None or right is None or right < left:
        return ""
    seconds = round((right - left).total_seconds())
    if seconds < 60:
        return f"{seconds} seconds"

    rounded_minutes = max(1, round(seconds / 60))
    exact_minute = seconds % 60 == 0
    if rounded_minutes < 60:
        prefix = "" if exact_minute else "approximately "
        return f"{prefix}{rounded_minutes} minutes"

    hours, remainder = divmod(rounded_minutes, 60)
    hour_word = "hour" if hours == 1 else "hours"
    prefix = "" if exact_minute else "approximately "
    if remainder == 0:
        return f"{prefix}{hours} {hour_word}"
    return f"{prefix}{hours} {hour_word} {remainder} minutes"


def _subject_command_events(
    evidence: list[dict[str, Any]],
    *,
    subject: str,
) -> list[dict[str, Any]]:
    wanted = str(subject or "").strip().casefold()
    for receipt in reversed(evidence):
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("tool") != "homebrain_device_history"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        label = str(details.get("label") or "").strip().casefold()
        if wanted and label != wanted:
            continue
        events = details.get("commandEvents")
        if isinstance(events, list):
            return [row for row in events if isinstance(row, dict)]
    return []


def _subject_boundary_events(
    evidence: list[dict[str, Any]],
    *,
    subject: str,
) -> list[dict[str, Any]]:
    wanted = str(subject or "").strip().casefold()
    for receipt in reversed(evidence):
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("tool") != "homebrain_device_history"
        ):
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        label = str(details.get("label") or "").strip().casefold()
        if wanted and label != wanted:
            continue
        events = details.get("boundaryEvents")
        if isinstance(events, list):
            return [row for row in events if isinstance(row, dict)]
    return []


def _producer_key(value: Any) -> tuple[str, str, str]:
    if not isinstance(value, dict):
        return "", "", ""
    return (
        str(value.get("type") or "").strip().casefold(),
        str(value.get("id") or "").strip(),
        str(value.get("label") or "").strip().casefold(),
    )


def _same_producer(left: Any, right: Any) -> bool:
    left_type, left_id, left_label = _producer_key(left)
    right_type, right_id, right_label = _producer_key(right)
    if left_id and right_id:
        return left_id == right_id and (
            not left_type or not right_type or left_type == right_type
        )
    return bool(left_label and left_label == right_label)


def _matching_boundary_event(
    evidence: list[dict[str, Any]],
    *,
    subject: str,
    action: str,
    boundary: datetime,
    max_delta_seconds: float = 0.5,
) -> dict[str, Any] | None:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for event in _subject_boundary_events(evidence, subject=subject):
        if str(event.get("name") or "").casefold() != "switch":
            continue
        if str(event.get("value") or "").strip().casefold() != action:
            continue
        event_time = _parse_time(event.get("date"))
        if event_time is None:
            continue
        delta = abs((event_time - boundary).total_seconds())
        if delta <= max(0.05, float(max_delta_seconds)):
            candidates.append((delta, event))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def correlate_boundary_producers(
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expose authoritative producer metadata carried by switch boundary events."""

    correlations: list[dict[str, Any]] = []
    for timeline in build_causal_timeline_rows(evidence):
        # Direct structured boundary provenance is authoritative for the observed
        # transition itself, even when the interval is brief. The generic
        # timeline's five-minute "material" threshold is useful for weaker
        # contextual reasoning, but must not discard a short switch boundary that
        # independently names its producer.
        subject = str(timeline.get("subject") or "").strip()
        for role, action, boundary_key in (
            ("start", "on", "start"),
            ("end", "off", "end"),
        ):
            if role == "end" and timeline.get("open"):
                continue
            boundary = _parse_time(timeline.get(boundary_key))
            if boundary is None:
                continue
            event = _matching_boundary_event(
                evidence,
                subject=subject,
                action=action,
                boundary=boundary,
            )
            if not isinstance(event, dict):
                continue
            producer = event.get("producedBy")
            if not (
                isinstance(producer, dict)
                and str(producer.get("label") or "").strip()
            ):
                continue
            correlations.append({
                "timelineId": str(timeline.get("id") or ""),
                "boundaryRole": role,
                "subject": subject,
                "open": bool(timeline.get("open")),
                "intervalStart": timeline.get("start"),
                "intervalEnd": timeline.get("end"),
                "stateBoundary": boundary.isoformat(),
                "action": action,
                "event": {
                    "name": str(event.get("name") or "").strip(),
                    "value": str(event.get("value") or "").strip(),
                    "date": str(event.get("date") or "").strip(),
                    "type": str(event.get("type") or "").strip(),
                    "description": str(event.get("description") or "").strip(),
                    "triggered": (
                        list(event.get("triggered"))
                        if isinstance(event.get("triggered"), list)
                        else []
                    ),
                },
                "producer": dict(producer),
                "provenanceStrength": "authoritative-state-boundary-producer",
            })
    return correlations


def boundary_producer_transition_match(
    correlations: list[dict[str, Any]],
    transition: str,
) -> dict[str, Any] | None:
    """Return the newest non-self producer row for the requested boundary."""

    action = str(transition or "").strip().casefold()
    role = {"on": "start", "off": "end"}.get(action)
    if role is None:
        return None
    candidates: list[dict[str, Any]] = []
    for row in correlations:
        if not isinstance(row, dict):
            continue
        if str(row.get("boundaryRole") or "") != role:
            continue
        if str(row.get("action") or "") != action:
            continue
        producer = row.get("producer")
        if not isinstance(producer, dict):
            continue
        producer_label = str(producer.get("label") or "").strip()
        subject = str(row.get("subject") or "").strip()
        if not producer_label or producer_label.casefold() == subject.casefold():
            continue
        candidates.append(row)
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: _parse_time(row.get("stateBoundary"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return candidates[0]


def boundary_producer_transition_kind(
    correlations: list[dict[str, Any]],
    transition: str,
) -> str | None:
    row = boundary_producer_transition_match(correlations, transition)
    if row is None:
        return None
    producer = row.get("producer") or {}
    producer_type = str(producer.get("type") or "").strip().casefold()
    return "app" if producer_type == "app" else "reporting_source"


def boundary_producer_transition_sufficient(
    correlations: list[dict[str, Any]],
    transition: str,
) -> bool:
    """Return whether a non-self producer is recorded on the requested boundary."""

    action = str(transition or "").strip().casefold()
    role = {"on": "start", "off": "end"}.get(action)
    if role is None:
        return False
    for row in correlations:
        if not isinstance(row, dict):
            continue
        if str(row.get("boundaryRole") or "") != role:
            continue
        if str(row.get("action") or "") != action:
            continue
        producer = row.get("producer")
        if not isinstance(producer, dict):
            continue
        producer_label = str(producer.get("label") or "").strip()
        subject = str(row.get("subject") or "").strip()
        if not producer_label:
            continue
        # Self-produced MQTT/device state events do not identify the initiator;
        # keep those eligible for the established deeper fallback path.
        if producer_label.casefold() == subject.casefold():
            continue
        return True
    return False


def correlate_command_producers(
    evidence: list[dict[str, Any]],
    *,
    max_delta_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Join command producer metadata to observed subject state boundaries."""

    correlations: list[dict[str, Any]] = []
    for timeline in build_causal_timeline_rows(evidence):
        if not timeline.get("material"):
            continue
        subject = str(timeline.get("subject") or "").strip()
        command_events = _subject_command_events(evidence, subject=subject)
        if not command_events:
            continue

        for role, action, boundary_key in (
            ("start", "on", "start"),
            ("end", "off", "end"),
        ):
            if role == "end" and timeline.get("open"):
                continue
            boundary = _parse_time(timeline.get(boundary_key))
            if boundary is None:
                continue

            candidates: list[
                tuple[float, datetime, dict[str, Any], bool]
            ] = []
            event_name = f"command-{action}"
            boundary_event = _matching_boundary_event(
                evidence,
                subject=subject,
                action=action,
                boundary=boundary,
            )
            boundary_producer = (
                boundary_event.get("producedBy")
                if isinstance(boundary_event, dict)
                else None
            )
            for event in command_events:
                if str(event.get("name") or "").casefold() != event_name:
                    continue
                producer = event.get("producedBy")
                if not (
                    isinstance(producer, dict)
                    and str(producer.get("label") or "").strip()
                ):
                    continue
                event_time = _parse_time(event.get("date"))
                if event_time is None:
                    continue
                delta = (boundary - event_time).total_seconds()
                if 0.0 <= delta <= max(0.1, float(max_delta_seconds)):
                    candidates.append((delta, event_time, event, False))
                    continue

                # Some Hubitat integrations record the state event a few
                # milliseconds before the corresponding command row. Never
                # accept that inversion from timing alone. It is eligible only
                # when the boundary event independently names the same APP
                # producer, which makes the producer identity authoritative even
                # though the two event timestamps landed in reverse order.
                producer_type = str(producer.get("type") or "").casefold()
                if (
                    -0.25 <= delta < 0.0
                    and producer_type == "app"
                    and _same_producer(producer, boundary_producer)
                ):
                    candidates.append((abs(delta), event_time, event, True))
            if not candidates:
                continue

            candidates.sort(key=lambda item: item[0])
            _distance, command_time, event, inverted = candidates[0]
            producer = dict(event.get("producedBy") or {})
            correlations.append({
                "timelineId": str(timeline.get("id") or ""),
                "boundaryRole": role,
                "subject": subject,
                "open": bool(timeline.get("open")),
                "intervalStart": timeline.get("start"),
                "intervalEnd": timeline.get("end"),
                "stateBoundary": boundary.isoformat(),
                "action": action,
                "command": {
                    "name": event_name,
                    "date": command_time.isoformat(),
                    "description": str(event.get("description") or "").strip(),
                    "type": str(event.get("type") or "").strip(),
                    "source": str(event.get("source") or "").strip(),
                    "commandToStateMs": round(
                        (boundary - command_time).total_seconds() * 1000,
                        1,
                    ),
                    "recordingOrderInverted": inverted,
                },
                "boundaryProducer": (
                    dict(boundary_producer)
                    if isinstance(boundary_producer, dict)
                    else None
                ),
                "producer": producer,
                "provenanceStrength": (
                    "authoritative-command-producer-boundary-corroborated"
                    if inverted
                    else "authoritative-command-producer"
                ),
            })
    return correlations


def command_producer_transition_sufficient(
    correlations: list[dict[str, Any]],
    transition: str,
) -> bool:
    """Return whether direct producer provenance proves the requested boundary."""

    action = str(transition or "").strip().casefold()
    boundary_role = {"on": "start", "off": "end"}.get(action)
    if boundary_role is None:
        return False

    return any(
        isinstance(row, dict)
        and str(row.get("boundaryRole") or "") == boundary_role
        and str(row.get("action") or "") == action
        and isinstance(row.get("producer"), dict)
        and str(row["producer"].get("label") or "").strip()
        and isinstance(row.get("command"), dict)
        for row in correlations
    )


def command_producer_turn_on_sufficient(
    correlations: list[dict[str, Any]],
) -> bool:
    """Compatibility wrapper for the original 0.16.17 turn-on contract."""

    return command_producer_transition_sufficient(correlations, "on")


def _command_state_timing_text(
    *,
    action: str,
    subject: str,
    producer_label: str,
    command_time: str,
    state_time: str,
    delay_ms: Any,
    inverted: bool,
) -> str:
    action_upper = action.upper()
    try:
        delay_value = float(delay_ms)
    except (TypeError, ValueError):
        delay_value = 0.0

    if inverted:
        return (
            f"The {action_upper} state for {subject} was recorded at {state_time}; "
            f"an adjacent {action_upper} command from {producer_label} was recorded "
            f"{abs(delay_value):g} ms later. The state boundary independently names "
            f"the same app producer, so this is treated as a recording-order "
            f"inversion rather than a later unrelated command."
        )

    return (
        f"The {action_upper} command was issued at {command_time}, followed by the "
        f"device reporting {action_upper} at {state_time}"
        + (
            f" ({abs(delay_value):g} ms later)."
            if delay_ms not in {None, ""}
            else "."
        )
    )


def render_boundary_producer_answer(
    evidence: list[dict[str, Any]],
    *,
    transition: str,
) -> str | None:
    """Render direct switch-boundary provenance without overstating causation."""

    action = str(transition or "").strip().casefold()
    role = {"on": "start", "off": "end"}.get(action)
    if role is None:
        return None

    matches = [
        row
        for row in correlate_boundary_producers(evidence)
        if str(row.get("boundaryRole") or "") == role
        and str(row.get("action") or "") == action
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda row: _parse_time(row.get("stateBoundary"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    focus = matches[0]
    subject = str(focus.get("subject") or "the device").strip()
    producer = focus.get("producer") or {}
    producer_label = str(producer.get("label") or "").strip()
    producer_type = str(producer.get("type") or "").strip().casefold()
    if not producer_label or producer_label.casefold() == subject.casefold():
        return None

    event = focus.get("event") or {}
    event_type = str(event.get("type") or "").strip().casefold()
    state_time = _clock_text(focus.get("stateBoundary"))
    action_upper = action.upper()
    paragraphs: list[str] = []

    if producer_type == "app":
        paragraphs.append(
            f"Hubitat records the {action_upper} state event for {subject} as "
            f"produced by the app {producer_label}."
        )
        paragraphs.append(
            f"The device reported {action_upper} at {state_time}. No separate "
            f"command-{action} producer was recorded for this boundary, so this "
            f"is direct state-event provenance rather than a separate command row."
        )
    else:
        qualifier = f" {event_type}" if event_type else ""
        paragraphs.append(
            f"Hubitat did not record a command-{action} producer aligned with "
            f"this {action_upper} transition for {subject}. "
            f"The {action_upper} state event at {state_time} is marked{qualifier} "
            f"and was produced by {producer_label}."
        )
        paragraphs.append(
            f"This identifies the reporting path into Hubitat, not the exact "
            f"initiating action. From this evidence alone, HomeBrain cannot "
            f"distinguish a bridge-side button/switch action, vendor app command, "
            f"vendor-native automation, or another action behind {producer_label}."
        )

    triggered = [
        str(item.get("name") or "").strip()
        for item in event.get("triggered", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    if triggered:
        unique_triggered = list(dict.fromkeys(triggered))
        paragraphs.append(
            "Hubitat also records these downstream listeners as triggered by the "
            f"state event: {', '.join(unique_triggered)}. Their presence shows "
            "reaction to the state change; it does not prove they initiated it."
        )

    if action == "on":
        interval_end = focus.get("intervalEnd")
        duration = _duration_text(focus.get("stateBoundary"), interval_end)
        if duration:
            paragraphs.append(
                f"The observed ON interval ended at {_clock_text(interval_end)} "
                f"after {duration}."
            )
    else:
        interval_start = focus.get("intervalStart")
        duration = _duration_text(interval_start, focus.get("stateBoundary"))
        if duration:
            paragraphs.append(
                f"This ended an observed run of {duration}, which began when the "
                f"device reported ON at {_clock_text(interval_start)}."
            )

    return "\n\n".join(paragraphs)


def render_command_producer_answer(
    evidence: list[dict[str, Any]],
    *,
    transition: str = "on",
) -> str | None:
    """Render the strongest direct command-producer result without a model."""

    correlations = correlate_command_producers(evidence)
    action = str(transition or "").strip().casefold()
    if action not in {"on", "off"}:
        action = "on"
    boundary_role = "start" if action == "on" else "end"

    matches = [
        row
        for row in correlations
        if str(row.get("boundaryRole") or "") == boundary_role
        and str(row.get("action") or "") == action
        and isinstance(row.get("producer"), dict)
    ]
    if not matches:
        return None

    matches.sort(
        key=lambda row: _parse_time(row.get("stateBoundary"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    focus = matches[0]
    timeline_id = str(focus.get("timelineId") or "")
    subject = str(focus.get("subject") or "the device").strip()
    producer = focus.get("producer") or {}
    producer_label = str(producer.get("label") or "").strip()
    command = focus.get("command") or {}
    command_time = _clock_text(command.get("date"))
    state_time = _clock_text(focus.get("stateBoundary"))
    delay = command.get("commandToStateMs")

    if action == "off":
        start_row = next(
            (
                row
                for row in correlations
                if str(row.get("timelineId") or "") == timeline_id
                and str(row.get("boundaryRole") or "") == "start"
                and str(row.get("action") or "") == "on"
            ),
            None,
        )
        paragraphs = [
            (
                f"Hubitat records the OFF command for {subject} as produced by "
                f"{producer_label}."
            ),
            _command_state_timing_text(
                action="off",
                subject=subject,
                producer_label=producer_label,
                command_time=command_time,
                state_time=state_time,
                delay_ms=delay,
                inverted=bool(command.get("recordingOrderInverted")),
            ),
        ]
        if isinstance(start_row, dict):
            start_producer = start_row.get("producer") or {}
            start_label = str(start_producer.get("label") or "").strip()
            start_command = start_row.get("command") or {}
            on_command_time = _clock_text(start_command.get("date"))
            on_state_time = _clock_text(start_row.get("stateBoundary"))
            on_delay = start_command.get("commandToStateMs")
            duration = _duration_text(
                start_row.get("stateBoundary"),
                focus.get("stateBoundary"),
            )
            context = "This ended"
            if duration:
                context += f" an observed run of {duration}"
            else:
                context += " the observed ON interval"
            if start_label:
                context += (
                    f". The matching ON command was produced by {start_label} "
                    f"at {on_command_time}, and the device reported ON at "
                    f"{on_state_time}"
                )
                if on_delay not in {None, ""}:
                    context += f" ({abs(float(on_delay)):g} ms later)"
            context += "."
            paragraphs.append(context)
        else:
            interval_start = focus.get("intervalStart")
            duration = _duration_text(
                interval_start,
                focus.get("stateBoundary"),
            )
            if duration:
                paragraphs.append(
                    f"This ended an observed run of {duration}, which began when "
                    f"the device reported ON at {_clock_text(interval_start)}."
                )
    else:
        start_row = focus
        end_row = next(
            (
                row
                for row in correlations
                if str(row.get("timelineId") or "") == timeline_id
                and str(row.get("boundaryRole") or "") == "end"
                and str(row.get("action") or "") == "off"
            ),
            None,
        )
        paragraphs = [
            (
                f"Hubitat records the ON command for {subject} as produced by "
                f"{producer_label}."
            ),
            _command_state_timing_text(
                action="on",
                subject=subject,
                producer_label=producer_label,
                command_time=command_time,
                state_time=state_time,
                delay_ms=delay,
                inverted=bool(command.get("recordingOrderInverted")),
            ),
        ]

        if isinstance(end_row, dict):
            end_producer = end_row.get("producer") or {}
            end_label = str(end_producer.get("label") or "").strip()
            end_command = end_row.get("command") or {}
            off_command_time = _clock_text(end_command.get("date"))
            off_state_time = _clock_text(end_row.get("stateBoundary"))
            off_delay = end_command.get("commandToStateMs")
            duration = _duration_text(
                start_row.get("stateBoundary"),
                end_row.get("stateBoundary"),
            )
            ending = (
                f"At {off_command_time}, the OFF command was produced by "
                f"{end_label}, and the device reported OFF at {off_state_time}"
            )
            if off_delay not in {None, ""}:
                ending += f" ({abs(float(off_delay)):g} ms later)"
            if duration:
                ending += f", ending an observed run of {duration}"
            ending += "."
            paragraphs.append(ending)
        elif start_row.get("open"):
            paragraphs.append(
                "The current ON interval is still open, so no closing OFF command "
                "or completed run duration has been observed yet."
            )
        else:
            interval_end = focus.get("intervalEnd")
            duration = _duration_text(
                focus.get("stateBoundary"),
                interval_end,
            )
            if duration:
                paragraphs.append(
                    f"The observed run ended when the device reported OFF at "
                    f"{_clock_text(interval_end)}, after {duration}."
                )

    paragraphs.append(
        "The Produced By field identifies the Hubitat app/action that issued "
        "the command. It does not identify the person who initiated that action."
    )
    return "\n\n".join(paragraphs)

def render_boundary_producer_summary(
    evidence: list[dict[str, Any]],
    *,
    transition: str,
) -> str | None:
    """Render a compact user-facing boundary provenance summary."""

    action = str(transition or "").strip().casefold()
    action_upper = action.upper()
    if action not in {"on", "off"}:
        return None

    focus = boundary_producer_transition_match(
        correlate_boundary_producers(evidence),
        action,
    )
    if not isinstance(focus, dict):
        return None

    subject = str(focus.get("subject") or "the device").strip()
    producer = focus.get("producer") or {}
    producer_label = str(producer.get("label") or "").strip()
    producer_type = str(producer.get("type") or "").strip().casefold()
    if not producer_label:
        return None

    event = focus.get("event") or {}
    state_time = _clock_text(focus.get("stateBoundary"))
    lines: list[str] = []

    if producer_type == "app":
        lines.append(
            f"**Main finding:** {producer_label} produced the {action_upper} "
            f"state event for {subject} at {state_time}."
        )
        lines.append(
            "- **Provenance:** This is direct state-event metadata; no separate "
            f"aligned command-{action} row was recorded."
        )
    else:
        lines.append(
            f"**Main finding:** Hubitat has no direct command producer for this "
            f"{action_upper} transition. {subject} reported {action_upper} at "
            f"{state_time} via {producer_label}."
        )
        lines.append(
            f"- **Reporting path:** {producer_label} carried the event into "
            "Hubitat; it does not identify the exact initiating action."
        )

    triggered = [
        str(item.get("name") or "").strip()
        for item in event.get("triggered", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    if triggered:
        unique_triggered = list(dict.fromkeys(triggered))
        lines.append(
            f"- **Downstream only:** {', '.join(unique_triggered)} reacted to "
            "the state event; they are not proven initiators."
        )

    if action == "on":
        if focus.get("open"):
            lines.append("- **Status:** The current ON interval is still open.")
        else:
            duration = _duration_text(
                focus.get("stateBoundary"),
                focus.get("intervalEnd"),
            )
            if duration:
                lines.append(f"- **Run:** The light/device stayed ON for {duration}.")
    else:
        duration = _duration_text(
            focus.get("intervalStart"),
            focus.get("stateBoundary"),
        )
        if duration:
            lines.append(f"- **Run:** This ended an ON run of {duration}.")

    return "\n".join(lines)


def render_command_producer_summary(
    evidence: list[dict[str, Any]],
    *,
    transition: str = "on",
) -> str | None:
    """Render a compact user-facing direct command-producer summary."""

    action = str(transition or "").strip().casefold()
    if action not in {"on", "off"}:
        action = "on"
    boundary_role = "start" if action == "on" else "end"

    matches = [
        row
        for row in correlate_command_producers(evidence)
        if str(row.get("boundaryRole") or "") == boundary_role
        and str(row.get("action") or "") == action
        and isinstance(row.get("producer"), dict)
    ]
    if not matches:
        return None

    matches.sort(
        key=lambda row: _parse_time(row.get("stateBoundary"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    focus = matches[0]
    subject = str(focus.get("subject") or "the device").strip()
    producer = focus.get("producer") or {}
    producer_label = str(producer.get("label") or "").strip()
    command = focus.get("command") or {}
    command_time = _clock_text(command.get("date"))
    state_time = _clock_text(focus.get("stateBoundary"))
    delay = command.get("commandToStateMs")
    inverted = bool(command.get("recordingOrderInverted"))
    action_upper = action.upper()

    if inverted:
        timing = (
            f"{subject} reported {action_upper} at {state_time}; the matching "
            f"command from {producer_label} was recorded "
            f"{abs(float(delay or 0)):g} ms later (recording-order inversion)."
        )
    else:
        timing = (
            f"{producer_label} issued the {action_upper} command for {subject} "
            f"at {command_time}; the device reported {action_upper} at "
            f"{state_time}"
        )
        if delay not in {None, ""}:
            timing += f" ({abs(float(delay)):g} ms later)"
        timing += "."

    lines = [f"**Cause:** {timing}"]

    if action == "on":
        if focus.get("open"):
            lines.append("- **Status:** The current ON interval is still open.")
        else:
            duration = _duration_text(
                focus.get("stateBoundary"),
                focus.get("intervalEnd"),
            )
            if duration:
                lines.append(f"- **Run:** The observed ON run lasted {duration}.")
    else:
        duration = _duration_text(
            focus.get("intervalStart"),
            focus.get("stateBoundary"),
        )
        if duration:
            lines.append(f"- **Run:** This ended an ON run of {duration}.")

    lines.append(
        "- **Note:** The Hubitat producer identifies the app/action that issued "
        "the command, not the person who initiated it."
    )
    return "\n".join(lines)


def render_command_producer_evidence(
    correlations: list[dict[str, Any]],
) -> str | None:
    if not correlations:
        return None
    lines = [
        "HOST COMMAND-PRODUCER PROVENANCE",
        (
            "These rows come from Hubitat device command events. producedBy is "
            "direct command-source metadata and outranks timestamp-only log "
            "correlation or app configuration."
        ),
    ]
    for row in correlations:
        producer = row.get("producer") or {}
        command = row.get("command") or {}
        lines.append(
            f"- {row.get('timelineId')} {row.get('boundaryRole')}: "
            f"command-{row.get('action')} at {command.get('date')} was produced by "
            f"{producer.get('label')} -> state boundary {row.get('stateBoundary')} "
            f"(command-to-state {command.get('commandToStateMs')} ms)."
        )
    return "\n".join(lines)


__all__ = [
    "boundary_producer_transition_kind",
    "boundary_producer_transition_match",
    "boundary_producer_transition_sufficient",
    "command_producer_transition_sufficient",
    "command_producer_turn_on_sufficient",
    "correlate_boundary_producers",
    "correlate_command_producers",
    "render_boundary_producer_answer",
    "render_command_producer_answer",
    "render_command_producer_evidence",
]
