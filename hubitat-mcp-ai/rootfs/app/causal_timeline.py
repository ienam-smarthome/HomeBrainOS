"""Structured causal timeline synthesis support.

This module does not decide what caused an event. It joins already-gathered
current-turn evidence around observed subject intervals so the final reasoning
pass sees each material transition together with the strongest nearby provenance,
device commands, and mode/context evidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    """Return the strongest current-turn history receipt for the causal subject.

    A causal history request can legitimately produce more than one receipt for
    the same subject. In particular, the first attribute-less read may infer a
    binary state from a full noisy page yet establish no interval, after which
    the host performs a scoped retry that does recover the interval. The older
    first-pass receipt must not shadow that corrected result.

    Anchor the subject to the first qualifying history receipt, then rank only
    later receipts for that same canonical subject. Prefer bounded intervals,
    then open/unbounded active transitions, then an otherwise valid empty
    temporal history. Ties prefer the later receipt so deterministic retries can
    supersede stale first-pass evidence without allowing later controller
    histories for another device to become the causal subject.
    """

    candidates: list[tuple[int, int, dict[str, Any]]] = []
    anchor_key = ""

    for index, receipt in enumerate(evidence):
        if (
            not isinstance(receipt, dict)
            or receipt.get("success") is not True
            or receipt.get("tool") != "homebrain_device_history"
        ):
            continue

        details = _details(receipt)
        temporal = details.get("temporalAnalysis")
        if not isinstance(temporal, dict):
            continue
        intervals = temporal.get("observedIntervals")
        if not isinstance(intervals, list):
            continue

        label = str(details.get("label") or "").strip()
        arguments = receipt.get("arguments")
        requested = (
            str(arguments.get("name") or "").strip()
            if isinstance(arguments, dict)
            else ""
        )
        subject_key = re.sub(
            r"[^a-z0-9]",
            "",
            (label or requested).casefold(),
        )
        if not subject_key:
            continue

        if not anchor_key:
            anchor_key = subject_key
        if subject_key != anchor_key:
            continue

        bounded = any(
            isinstance(item, dict)
            and str(item.get("start") or "").strip()
            and str(item.get("end") or "").strip()
            for item in intervals
        )
        open_active = bool(
            temporal.get("unboundedActiveInterval")
            or temporal.get("openActiveInterval")
            or str(temporal.get("openActiveStart") or "").strip()
        )
        rank = 2 if bounded else 1 if open_active else 0
        candidates.append((rank, index, receipt))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


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


def _controller_boundary_matches(
    receipts: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Classify controller events by their nearest subject interval boundary.

    A button event nearest the end of an interval is evidence about the
    turn-off/end boundary, not provenance for the earlier turn-on.  This
    directional distinction prevents an absolute timestamp delta from being
    misread as a causal trigger when an event occurs at the opposite boundary.
    """

    start_matches: list[tuple[float, dict[str, Any]]] = []
    end_matches: list[tuple[float, dict[str, Any]]] = []
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
            event_time = _parse_time(event.get("date") or event.get("timestamp"))
            if event_time is None:
                continue
            start_delta = abs((event_time - start).total_seconds())
            end_delta = (
                abs((event_time - end).total_seconds())
                if end is not None
                else float("inf")
            )
            boundary_role = "start" if start_delta <= end_delta else "end"
            boundary = start if boundary_role == "start" else end
            delta = start_delta if boundary_role == "start" else end_delta
            if boundary is None or delta > _CONTROLLER_DELTA_SECONDS:
                continue

            description = str(
                event.get("description") or event.get("descriptionText") or ""
            )
            signed_delta = (event_time - boundary).total_seconds()
            row = {
                "date": str(event.get("date") or event.get("timestamp") or ""),
                "name": event.get("name") or event.get("attribute"),
                "value": event.get("value"),
                "description": (
                    event.get("description") or event.get("descriptionText")
                ),
                "deltaSeconds": round(delta, 3),
                "signedDeltaSeconds": round(signed_delta, 3),
                "boundaryRole": boundary_role,
                "sourceLabel": label,
                "attribute": attribute,
                "physicalMetadata": "[physical]" in description.casefold(),
            }
            target = start_matches if boundary_role == "start" else end_matches
            target.append((delta, row))

    start_matches.sort(key=lambda item: item[0])
    end_matches.sort(key=lambda item: item[0])
    return (
        [row for _delta, row in start_matches[:4]],
        [row for _delta, row in end_matches[:4]],
    )


def _start_context_matches(
    events: list[dict[str, Any]],
    *,
    start: datetime,
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for event in events:
        row = _event_row(event, boundary=start)
        if row is None:
            continue
        delta = float(row["deltaSeconds"])
        if delta > _CONTEXT_DELTA_SECONDS:
            continue
        name = str(row.get("name") or "").casefold()
        if name not in {"mode", "sunrise", "sunset"}:
            continue
        row["boundary"] = "start"
        ranked.append((delta, row))
    ranked.sort(key=lambda item: item[0])
    return [row for _delta, row in ranked[:6]]


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

        trigger_evidence, end_controller_evidence = _controller_boundary_matches(
            controllers,
            start=start,
            end=end,
        )
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
            or end_controller_evidence
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
            "endControllerEvidence": end_controller_evidence,
            "startCommands": start_commands,
            "endCommands": end_commands,
            "contextEvents": context,
        })

    # For an unverified stream, a final active transition with no observed closing
    # transition is deliberately excluded from bounded-duration arithmetic. It is
    # still material causal evidence and must not disappear from final synthesis.
    if temporal.get("unboundedActiveInterval") and len(rows) < max(1, int(max_intervals)):
        open_start_text = str(temporal.get("openActiveStart") or "").strip()
        open_start = _parse_time(open_start_text)
        if open_start is not None:
            trigger_evidence, _ignored_end = _controller_boundary_matches(
                controllers,
                start=open_start,
                end=None,
            )
            start_commands = _nearby_events(
                subject_events,
                boundary=open_start,
                max_delta_seconds=_BOUNDARY_EVENT_DELTA_SECONDS,
                command_only=True,
            )
            rows.append({
                "id": f"T{len(rows) + 1}",
                "subject": subject_details.get("label"),
                "start": open_start_text,
                "end": "",
                "startNatural": temporal.get("openActiveStartNatural"),
                "endNatural": None,
                "duration": None,
                "durationSeconds": None,
                "open": True,
                "material": True,
                "triggerStatus": (
                    "aligned-controller-provenance"
                    if trigger_evidence
                    else "unresolved"
                ),
                "triggerEvidence": trigger_evidence,
                "endControllerEvidence": [],
                "startCommands": start_commands,
                "endCommands": [],
                "contextEvents": _start_context_matches(
                    location_events,
                    start=open_start,
                ),
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
            "must not be omitted. A controller event aligned to an interval START "
            "can support turn-on provenance timing. A controller event aligned to an "
            "interval END is end/turn-off-adjacent evidence and must never be used as "
            "the cause of the earlier turn-on. Controller timing does not identify "
            "the person unless event metadata says so. OPEN rows have a recorded "
            "active transition but no observed closing transition, so their duration "
            "must not be inferred."
        ),
    ]
    for row in rows:
        prefix = "MATERIAL" if row.get("material") else "minor"
        if row.get("open"):
            rendered.append(
                f"- {row['id']} [{prefix} OPEN] "
                f"{row.get('startNatural') or row['start']} -> "
                "no observed closing transition; duration=not established; "
                f"trigger={row.get('triggerStatus')}"
            )
        else:
            rendered.append(
                f"- {row['id']} [{prefix}] {row.get('startNatural') or row['start']} -> "
                f"{row.get('endNatural') or row['end']} "
                f"({row.get('duration') or str(row.get('durationSeconds')) + 's'}); "
                f"trigger={row.get('triggerStatus')}"
            )
        for event in row.get("triggerEvidence") or []:
            rendered.append(f"  start-provenance: {_render_event(event)}")
        for event in row.get("endControllerEvidence") or []:
            rendered.append(f"  end-controller: {_render_event(event)}")
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


def unresolved_material_timeline_rows(
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return material rows whose turn-on/start provenance remains unresolved."""

    return [
        row
        for row in build_causal_timeline_rows(evidence)
        if row.get("material")
        and row.get("triggerStatus") == "unresolved"
    ]


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


def causal_log_windows(
    evidence: list[dict[str, Any]],
    *,
    padding_seconds: int = 10,
    max_windows: int = 2,
) -> list[dict[str, str]]:
    """Return UTC log windows around unresolved material start boundaries.

    Device-history timestamps carry the Hubitat location offset. Native
    hub_get_logs accepts timezone-aware ISO timestamps, but timezone-free or
    incorrectly suffixed values are interpreted as UTC. Convert the observed
    boundary explicitly to UTC so a 22:07 +01:00 event becomes 21:07Z rather
    than an impossible 22:07Z query one hour later.

    At most two windows are returned because causal completion itself permits
    only a bounded pair of complementary provenance reads.
    """

    rows = unresolved_material_timeline_rows(evidence)
    if not rows:
        rows = [
            row
            for row in build_causal_timeline_rows(evidence)
            if row.get("material")
        ]

    parsed: list[tuple[datetime, dict[str, Any]]] = []
    seen: set[str] = set()
    for row in rows:
        start_text = str(row.get("start") or "").strip()
        start = _parse_time(start_text)
        if start is None:
            continue
        key = start.isoformat()
        if key in seen:
            continue
        seen.add(key)
        parsed.append((start, row))

    # Most recent material transition first: "why did X turn on?" normally
    # refers to the latest observed activation, while still allowing a second
    # material boundary to be checked in the same bounded completion phase.
    parsed.sort(key=lambda item: item[0], reverse=True)
    pad = timedelta(seconds=max(1, min(60, int(padding_seconds))))
    windows: list[dict[str, str]] = []
    for start, row in parsed[: max(1, min(2, int(max_windows)))]:
        since = (start - pad).astimezone(timezone.utc)
        until = (start + pad).astimezone(timezone.utc)
        windows.append({
            "timelineId": str(row.get("id") or ""),
            "subjectStart": start.isoformat(),
            "since": since.isoformat().replace("+00:00", "Z"),
            "until": until.isoformat().replace("+00:00", "Z"),
        })
    return windows


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
        "been checked. Before final synthesis, make one bounded provenance "
        "round using relevant rule/app configuration, execution evidence, or native "
        "logs. You may issue up to two complementary read calls in that single "
        "round when both materially test the same command source (for example logs "
        "plus the most relevant app/rule configuration). Known read-only provenance "
        "gateways are exposed directly; use hub_search_tools only if the needed "
        "evidence class is still absent. Do not revisit controller or "
        "environmental-sensor history. Do not revisit location history either. "
        "If no stronger source can be obtained in this round, leave the command "
        "source explicitly unresolved rather than guessing."
    )


__all__ = [
    "build_causal_timeline_rows",
    "causal_log_windows",
    "command_source_followup_needed",
    "missing_material_timeline_rows",
    "unresolved_material_timeline_rows",
    "render_causal_timeline",
    "render_command_source_followup",
]
