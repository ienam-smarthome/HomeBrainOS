"""Structured causal timeline synthesis support.

This module does not decide what caused an event. It joins already-gathered
current-turn evidence around observed subject intervals so the final reasoning
pass sees each material transition together with the strongest nearby provenance,
device commands, and mode/context evidence.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from natural_datetime import normalize_iso_offset


_BUTTON_ATTRIBUTES = {"pushed", "held", "released", "doubletapped", "double_tapped"}
_MAX_INTERVALS = 8
_CONTROLLER_DELTA_SECONDS = 2.0
_BOUNDARY_EVENT_DELTA_SECONDS = 8.0
_CONTEXT_DELTA_SECONDS = 15.0
_MATERIAL_DURATION_SECONDS = 300


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(normalize_iso_offset(text))
    except (TypeError, ValueError):
        return None


def _details(receipt: dict[str, Any]) -> dict[str, Any]:
    value = receipt.get("details")
    return value if isinstance(value, dict) else {}


def _subject_receipt(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    for receipt in evidence:
        if (
            isinstance(receipt, dict)
            and receipt.get("success") is True
            and receipt.get("tool") == "homebrain_device_history"
        ):
            details = _details(receipt)
            temporal = details.get("temporalAnalysis")
            if isinstance(temporal, dict) and isinstance(
                temporal.get("observedIntervals"), list
            ):
                return receipt
    return None


def _controller_receipts(
    evidence: list[dict[str, Any]],
    *,
    subject: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt is subject or receipt.get("tool") != "homebrain_device_history":
            continue
        details = _details(receipt)
        attribute = re.sub(
            r"[^a-z0-9_]", "", str(details.get("attribute") or "").casefold()
        )
        events = details.get("observedEvents")
        if attribute in _BUTTON_ATTRIBUTES and isinstance(events, list):
            rows.append(receipt)
    return rows


def _location_rows(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer the raw authoritative location receipt carrying details.events.
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = _details(receipt)
        events = details.get("events")
        if isinstance(events, list) and (
            receipt.get("evidence_kind") == "authoritative_location_event_history"
            or receipt.get("tool") == "homebrain_location_events"
        ):
            return [row for row in events if isinstance(row, dict)]
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        if receipt.get("tool") != "homebrain_location_events":
            continue
        events = _details(receipt).get("observedEvents")
        if isinstance(events, list):
            return [row for row in events if isinstance(row, dict)]
    return []


def _event_row(
    event: dict[str, Any],
    *,
    boundary: datetime,
) -> dict[str, Any] | None:
    event_time = _parse_time(event.get("date") or event.get("timestamp"))
    if event_time is None:
        return None
    delta = abs((event_time - boundary).total_seconds())
    return {
        "date": str(event.get("date") or event.get("timestamp") or ""),
        "name": event.get("name") or event.get("attribute"),
        "value": event.get("value"),
        "description": event.get("description") or event.get("descriptionText"),
        "deltaSeconds": round(delta, 3),
    }


def _nearby_events(
    events: list[dict[str, Any]],
    *,
    boundary: datetime,
    max_delta_seconds: float,
    command_only: bool = False,
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for event in events:
        row = _event_row(event, boundary=boundary)
        if row is None or float(row["deltaSeconds"]) > max_delta_seconds:
            continue
        name = str(row.get("name") or "").casefold()
        if command_only and not name.startswith("command-"):
            continue
        ranked.append((float(row["deltaSeconds"]), row))
    ranked.sort(key=lambda item: item[0])
    return [row for _delta, row in ranked[:6]]


def _controller_matches(
    receipts: list[dict[str, Any]],
    *,
    start: datetime,
) -> list[dict[str, Any]]:
    matches: list[tuple[float, dict[str, Any]]] = []
    for receipt in receipts:
        details = _details(receipt)
        label = str(details.get("label") or "controller").strip()
        attribute = str(details.get("attribute") or "").strip()
        events = details.get("observedEvents")
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            row = _event_row(event, boundary=start)
            if row is None:
                continue
            delta = float(row["deltaSeconds"])
            if delta > _CONTROLLER_DELTA_SECONDS:
                continue
            description = str(row.get("description") or "")
            row.update({
                "sourceLabel": label,
                "attribute": attribute,
                "physicalMetadata": "[physical]" in description.casefold(),
            })
            matches.append((delta, row))
    matches.sort(key=lambda item: item[0])
    return [row for _delta, row in matches[:4]]


def _context_matches(
    events: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for boundary_name, boundary in (("start", start), ("end", end)):
        for event in events:
            row = _event_row(event, boundary=boundary)
            if row is None:
                continue
            delta = float(row["deltaSeconds"])
            if delta > _CONTEXT_DELTA_SECONDS:
                continue
            name = str(row.get("name") or "").casefold()
            if name not in {"mode", "sunrise", "sunset"}:
                continue
            row["boundary"] = boundary_name
            ranked.append((delta, boundary_name, row))
    ranked.sort(key=lambda item: item[0])
    return [row for _delta, _boundary, row in ranked[:6]]


def build_causal_timeline_rows(
    evidence: list[dict[str, Any]],
    *,
    max_intervals: int = _MAX_INTERVALS,
) -> list[dict[str, Any]]:
    """Build bounded timeline rows from already-observed current-turn evidence."""

    subject = _subject_receipt(evidence)
    if subject is None:
        return []
    subject_details = _details(subject)
    temporal = subject_details.get("temporalAnalysis")
    if not isinstance(temporal, dict):
        return []
    intervals = temporal.get("observedIntervals")
    if not isinstance(intervals, list):
        return []

    # Boundary-near rows are preserved independently of the generic
    # newest-first event cap. Prefer them, then supplement with ordinary observed
    # rows while de-duplicating by timestamp/name/value.
    subject_events: list[dict[str, Any]] = []
    seen_subject_events: set[tuple[str, str, str]] = set()
    for field in ("boundaryEvents", "observedEvents"):
        source_rows = subject_details.get(field)
        if not isinstance(source_rows, list):
            continue
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            key = (
                str(row.get("date") or row.get("timestamp") or ""),
                str(row.get("name") or row.get("attribute") or ""),
                str(row.get("value") or ""),
            )
            if key in seen_subject_events:
                continue
            seen_subject_events.add(key)
            subject_events.append(row)
    controllers = _controller_receipts(evidence, subject=subject)
    location_events = _location_rows(evidence)
    rows: list[dict[str, Any]] = []

    for index, interval in enumerate(intervals[: max(1, int(max_intervals))], start=1):
        if not isinstance(interval, dict):
            continue
        start = _parse_time(interval.get("start"))
        end = _parse_time(interval.get("end"))
        if start is None or end is None:
            continue

        trigger_evidence = _controller_matches(controllers, start=start)
        start_commands = _nearby_events(
            subject_events,
            boundary=start,
            max_delta_seconds=_BOUNDARY_EVENT_DELTA_SECONDS,
            command_only=True,
        )
        end_commands = _nearby_events(
            subject_events,
            boundary=end,
            max_delta_seconds=_BOUNDARY_EVENT_DELTA_SECONDS,
            command_only=True,
        )
        context = _context_matches(location_events, start=start, end=end)
        duration_seconds = interval.get("durationSeconds")
        try:
            duration_value = int(duration_seconds)
        except (TypeError, ValueError):
            duration_value = max(0, round((end - start).total_seconds()))

        material = bool(
            duration_value >= _MATERIAL_DURATION_SECONDS
            or trigger_evidence
            or start_commands
            or end_commands
        )
        rows.append({
            "id": f"T{index}",
            "subject": subject_details.get("label"),
            "start": str(interval.get("start") or ""),
            "end": str(interval.get("end") or ""),
            "startNatural": interval.get("startNatural"),
            "endNatural": interval.get("endNatural"),
            "duration": interval.get("duration"),
            "durationSeconds": duration_value,
            "material": material,
            "triggerStatus": (
                "aligned-controller-provenance"
                if trigger_evidence
                else "unresolved"
            ),
            "triggerEvidence": trigger_evidence,
            "startCommands": start_commands,
            "endCommands": end_commands,
            "contextEvents": context,
        })
    return rows


def _render_event(event: dict[str, Any]) -> str:
    date = str(event.get("date") or "?")
    name = str(event.get("name") or "event")
    value = event.get("value")
    label = f"{name}={value}" if value not in {None, ""} else name
    description = str(event.get("description") or "").strip()
    if description and description.casefold() not in label.casefold():
        label += f" [{description}]"
    delta = event.get("deltaSeconds")
    if delta is not None:
        label += f" Δ{delta}s"
    source = str(event.get("sourceLabel") or "").strip()
    if source:
        label = f"{source}: {label}"
    return f"{date}: {label}"


def render_causal_timeline(evidence: list[dict[str, Any]]) -> str | None:
    rows = build_causal_timeline_rows(evidence)
    if not rows:
        return None

    rendered = [
        "HOST CAUSAL TIMELINE",
        (
            "This is a structured join of current-turn evidence, not a causal "
            "conclusion. The final answer must account for every MATERIAL row. "
            "Adjacent short non-material unresolved rows may be grouped as brief "
            "unexplained activity, but a material interval with aligned provenance "
            "must not be omitted. A controller alignment supports provenance timing; "
            "it does not identify the person unless event metadata says so."
        ),
    ]
    for row in rows:
        prefix = "MATERIAL" if row.get("material") else "minor"
        rendered.append(
            f"- {row['id']} [{prefix}] {row.get('startNatural') or row['start']} -> "
            f"{row.get('endNatural') or row['end']} "
            f"({row.get('duration') or str(row.get('durationSeconds')) + 's'}); "
            f"trigger={row.get('triggerStatus')}"
        )
        for event in row.get("triggerEvidence") or []:
            rendered.append(f"  provenance: {_render_event(event)}")
        for event in row.get("startCommands") or []:
            rendered.append(f"  subject-start-command: {_render_event(event)}")
        for event in row.get("endCommands") or []:
            rendered.append(f"  subject-end-command: {_render_event(event)}")
        for event in row.get("contextEvents") or []:
            rendered.append(
                f"  {event.get('boundary')}-context: {_render_event(event)}"
            )
    return "\n".join(rendered)


def _time_tokens(value: str) -> set[str]:
    parsed = _parse_time(value)
    if parsed is None:
        return set()
    hour24 = parsed.hour
    minute = parsed.minute
    hour12 = hour24 % 12 or 12
    suffix = "am" if hour24 < 12 else "pm"
    return {
        f"{hour24:02d}:{minute:02d}".casefold(),
        f"{hour24}:{minute:02d}".casefold(),
        f"{hour12}:{minute:02d}".casefold(),
        f"{hour12}:{minute:02d} {suffix}".casefold(),
    }


def missing_material_timeline_rows(
    message: str,
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return material intervals whose start anchor is absent from the draft."""

    comparable = re.sub(r"\s+", " ", str(message or "").casefold())
    missing: list[dict[str, Any]] = []
    for row in build_causal_timeline_rows(evidence):
        if not row.get("material"):
            continue
        tokens = _time_tokens(str(row.get("start") or ""))
        if tokens and not any(token in comparable for token in tokens):
            missing.append(row)
    return missing


def command_source_followup_needed(
    evidence: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Detect boundary command evidence whose source has not been investigated.

    A list-apps/list-rules manifest is navigation context, not provenance. A
    successful log read or non-list app/rule detail read satisfies this slot.
    """

    command_times: list[str] = []
    for row in build_causal_timeline_rows(evidence):
        for event in [*(row.get("startCommands") or []), *(row.get("endCommands") or [])]:
            date = str(event.get("date") or "").strip()
            if date and date not in command_times:
                command_times.append(date)
    if not command_times:
        return False, []

    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        tool = str(receipt.get("tool") or "").casefold()
        sub_tool = str(receipt.get("sub_tool") or "").casefold()
        if sub_tool == "hub_get_logs" or tool == "hub_get_logs":
            return False, command_times
        identity = " ".join(part for part in (tool, sub_tool) if part)
        if ("app" in identity or "rule" in identity) and "list" not in identity:
            return False, command_times
    return True, command_times


def render_command_source_followup(evidence: list[dict[str, Any]]) -> str | None:
    needed, times = command_source_followup_needed(evidence)
    if not needed:
        return None
    shown = ", ".join(times[:6])
    return (
        "HOST CAUSAL COMPLETENESS REQUIREMENT\n"
        "Current-turn subject history contains command events close to observed "
        f"interval boundaries ({shown}), but their issuing app/rule/source has not "
        "been checked. Before final synthesis, make one bounded attempt to obtain "
        "stronger downstream provenance using relevant rule/app configuration, "
        "execution evidence, or native logs. If the needed gateway is not declared, "
        "use hub_search_tools for that evidence class. Do not revisit controller or "
        "environmental-sensor history. If no stronger source can be obtained in this "
        "attempt, leave the command source explicitly unresolved rather than guessing."
    )


__all__ = [
    "build_causal_timeline_rows",
    "command_source_followup_needed",
    "missing_material_timeline_rows",
    "render_causal_timeline",
    "render_command_source_followup",
]
