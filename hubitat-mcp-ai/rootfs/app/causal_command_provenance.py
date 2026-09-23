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
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds % 60 == 0:
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minutes"
        hours, remainder = divmod(minutes, 60)
        if remainder == 0:
            return f"{hours} hours"
        hour_word = "hour" if hours == 1 else "hours"
        return f"{hours} {hour_word} {remainder} minutes"
    return f"approximately {max(1, round(seconds / 60))} minutes"


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

            candidates: list[tuple[float, datetime, dict[str, Any]]] = []
            event_name = f"command-{action}"
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
                # Command provenance is directional: the command must be issued
                # at or before the resulting state boundary. A later command,
                # even if close in absolute time, cannot explain an earlier
                # switch transition.
                if 0.0 <= delta <= max(0.1, float(max_delta_seconds)):
                    candidates.append((delta, event_time, event))
            if not candidates:
                continue

            candidates.sort(key=lambda item: item[0])
            _distance, command_time, event = candidates[0]
            producer = dict(event.get("producedBy") or {})
            correlations.append({
                "timelineId": str(timeline.get("id") or ""),
                "boundaryRole": role,
                "subject": subject,
                "open": bool(timeline.get("open")),
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
                },
                "producer": producer,
                "provenanceStrength": "authoritative-command-producer",
            })
    return correlations


def command_producer_turn_on_sufficient(
    correlations: list[dict[str, Any]],
) -> bool:
    """A direct producer on an adjacent command-on is sufficient for turn-on."""

    return any(
        isinstance(row, dict)
        and str(row.get("boundaryRole") or "") == "start"
        and str(row.get("action") or "") == "on"
        and isinstance(row.get("producer"), dict)
        and str(row["producer"].get("label") or "").strip()
        and isinstance(row.get("command"), dict)
        for row in correlations
    )


def render_command_producer_answer(
    evidence: list[dict[str, Any]],
) -> str | None:
    """Render the strongest direct command-producer result without a model."""

    correlations = correlate_command_producers(evidence)
    starts = [
        row
        for row in correlations
        if str(row.get("boundaryRole") or "") == "start"
        and str(row.get("action") or "") == "on"
        and isinstance(row.get("producer"), dict)
    ]
    if not starts:
        return None

    starts.sort(
        key=lambda row: _parse_time(row.get("stateBoundary"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    start = starts[0]
    timeline_id = str(start.get("timelineId") or "")
    end = next(
        (
            row
            for row in correlations
            if str(row.get("timelineId") or "") == timeline_id
            and str(row.get("boundaryRole") or "") == "end"
            and str(row.get("action") or "") == "off"
        ),
        None,
    )

    subject = str(start.get("subject") or "the device").strip()
    producer = start.get("producer") or {}
    producer_label = str(producer.get("label") or "").strip()
    command = start.get("command") or {}
    command_time = _clock_text(command.get("date"))
    state_time = _clock_text(start.get("stateBoundary"))
    delay = command.get("commandToStateMs")

    paragraphs = [
        (
            f"Hubitat records the ON command for {subject} as produced by "
            f"{producer_label}."
        ),
        (
            f"The ON command was issued at {command_time}, followed by the "
            f"device reporting ON at {state_time}"
            + (
                f" ({abs(float(delay)):g} ms later)."
                if delay not in {None, ""}
                else "."
            )
        ),
    ]

    if isinstance(end, dict):
        end_producer = end.get("producer") or {}
        end_label = str(end_producer.get("label") or "").strip()
        end_command = end.get("command") or {}
        off_command_time = _clock_text(end_command.get("date"))
        off_state_time = _clock_text(end.get("stateBoundary"))
        off_delay = end_command.get("commandToStateMs")
        duration = _duration_text(
            start.get("stateBoundary"),
            end.get("stateBoundary"),
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
    elif start.get("open"):
        paragraphs.append(
            "The current ON interval is still open, so no closing OFF command "
            "or completed run duration has been observed yet."
        )

    paragraphs.append(
        "The Produced By field identifies the Hubitat app/action that issued "
        "the command. It does not identify the person who initiated that action."
    )
    return "\n\n".join(paragraphs)


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
    "command_producer_turn_on_sufficient",
    "correlate_command_producers",
    "render_command_producer_answer",
    "render_command_producer_evidence",
]
