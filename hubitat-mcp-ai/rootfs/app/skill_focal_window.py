"""Host-owned, exact-time diagnostic source completion for causal investigations.

Unbounded latest-N device history must not substitute for the incident window.
A checked source with no retained values is not evidence of a complete window.
All queries are read-only and identified from *matching* subject receipts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from causal_evidence_graph import build_causal_evidence_graph
from skill_decision_summary import causal_skill_conclusion


def _time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo is not None else None


def _args(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("arguments") or {}
    if not isinstance(args, dict):
        return {}
    return args.get("args") if isinstance(args.get("args"), dict) else args


def _leaf(row: dict[str, Any]) -> str:
    args = row.get("arguments") or {}
    return str(row.get("sub_tool") or (args.get("tool") if isinstance(args, dict) else "") or row.get("tool") or "")


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _contains(outer_since: Any, outer_until: Any, start: datetime, stop: datetime) -> bool:
    since, until = _time(outer_since), _time(outer_until)
    return bool(since and until and since <= start and until >= stop)


def _device_ids(evidence: list[dict[str, Any]], subject: str) -> set[str]:
    found: set[str] = set()
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if _leaf(row) != "hub_list_device_events":
            continue
        details = row.get("details") or {}
        if str(details.get("label") or "").casefold() != subject.casefold():
            continue
        device_id = str(_args(row).get("deviceId") or details.get("deviceId") or "")
        if device_id.isdigit():
            found.add(device_id)
    return found


def build_focal_source_plan(
    evidence: list[dict[str, Any]], question: str,
) -> dict[str, Any] | None:
    """Return only missing, bounded device/producer history reads.

    A request with an explicit clock must have one uniquely observed matching
    state boundary. A preceding ON command must belong to this exact device.
    The 'state' and 'app_logs' actions are independent and will be attempted
    at most once per final-answer path. Existing unbounded pages DO NOT count.
    """
    verdict = causal_skill_conclusion(evidence, question)
    if not verdict or verdict.get("status") != "leading-recorded-candidate-unverified":
        return None
    graph = build_causal_evidence_graph(evidence, question)
    if graph.get("scope") != "single-observed-event":
        return None
    subject = str(verdict.get("subject") or "")
    command = verdict.get("command") or {}
    focus = _time(verdict.get("focusTime"))
    command_at = _time(command.get("timestamp"))
    app_id = str(command.get("producerId") or "")
    # The verdict intentionally omits a public producer ID; obtain the id
    # from a matched preceding command receipt, never from app name guessing.
    if not app_id:
        for row in evidence:
            if _leaf(row) != "hub_list_device_events" or row.get("success") is not True:
                continue
            if str((row.get("details") or {}).get("label") or "").casefold() != subject.casefold():
                continue
            for event in (row.get("details") or {}).get("events") or []:
                if not isinstance(event, dict) or event.get("name") != "command-on":
                    continue
                event_at = _time(event.get("date"))
                if event_at is None or command_at is None or abs((event_at - command_at).total_seconds()) > .002:
                    continue
                producer = event.get("producedBy") or {}
                candidate = str(producer.get("id") or "")
                if candidate.isdigit():
                    app_id = candidate
    if not (subject and focus and command_at and 0 <= (focus - command_at).total_seconds() <= 30):
        return None
    ids = _device_ids(evidence, subject)
    if len(ids) != 1:
        return None
    device_id = next(iter(ids))
    # Include command, the following OFF, the focal ON, and a small margin.
    begin = command_at - timedelta(seconds=10)
    end = focus + timedelta(seconds=5)
    state_args = {
        "deviceId": device_id,
        "attribute": "switch",
        "since": _iso_utc(begin),
        "until": _iso_utc(end),
        "limit": 100,
    }
    # Independent producer-log investigation, not a repeated broad hub log read.
    log_args = {
        "appId": int(app_id),
        "since": _iso_utc(begin),
        "until": _iso_utc(end),
        "limit": 100,
    } if app_id else None
    checked_state = False
    checked_logs = False
    for row in evidence:
        if not isinstance(row, dict):
            continue
        args = _args(row)
        kind = _leaf(row)
        if (
            kind == "hub_list_device_events"
            and str(args.get("deviceId") or "") == device_id
            and str(args.get("attribute") or "") == "switch"
            and _contains(args.get("since"), args.get("until"), begin, end)
        ):
            checked_state = True  # attempted regardless of success
        if (
            kind == "hub_get_logs" and app_id
            and str(args.get("appId") or "") == app_id
            and _contains(args.get("since"), args.get("until"), begin, end)
        ):
            checked_logs = True
    return {
        "subject": subject,
        "deviceId": device_id,
        "producerAppId": app_id or None,
        "requestedOn": verdict.get("focusTime"),
        "commandTime": command.get("timestamp"),
        "sourceWindow": {"since": state_args["since"], "until": state_args["until"]},
        "stateRead": None if checked_state else state_args,
        "producerLogRead": None if checked_logs else log_args,
        "stateHistoryStatus": "read-attempted" if checked_state else "not-checked-in-exact-window",
        "producerLogStatus": "read-attempted" if checked_logs else "not-checked-in-exact-window",
        "fullHistoricalCoverageVerified": False,
    }


def project_focal_state_result(
    response_data: Any, plan: dict[str, Any],
) -> dict[str, Any] | None:
    """Persist a safe, time-filtered event projection from a gateway response.

    The generic tool executor may record only a summary for gateway event
    results. Return a separate scoped receipt with event rows, never a
    guessed event or a copy of arbitrary configuration payload.
    """
    def find_rows(value: Any, depth: int = 0) -> list[dict[str, Any]] | None:
        if depth > 3:
            return None
        if isinstance(value, list):
            return value if all(isinstance(x, dict) for x in value) else None
        if not isinstance(value, dict):
            return None
        if isinstance(value.get("events"), list):
            return value["events"]
        for name in ("result", "data", "payload"):
            nested = value.get(name)
            if isinstance(nested, (list, dict)):
                selected = find_rows(nested, depth + 1)
                if selected is not None:
                    return selected
        return None

    rows = find_rows(response_data)
    if rows is None:
        return None
    interval = plan.get("sourceWindow") or {}
    start, stop = _time(interval.get("since")), _time(interval.get("until"))
    if start is None or stop is None:
        return None
    events = {}
    for item in rows[:100]:
        name = str(item.get("name") or item.get("attribute") or "")
        if name != "switch":
            continue
        state = str(item.get("value") or "").casefold()
        if state not in {"on", "off"}:
            continue
        when = str(item.get("date") or item.get("timestamp") or "")
        clock = _time(when)
        if clock is None or not (start <= clock <= stop):
            continue
        producer = item.get("producedBy")
        owner = {}
        if isinstance(producer, dict):
            owner = {
                key: str(producer[key])[:100]
                for key in ("label", "id", "type")
                if producer.get(key) is not None
            }
        events[(clock.isoformat(), state)] = {
            "name": "switch", "value": state, "date": when,
            "producedBy": owner,
        }
    return {
        "label": str(plan.get("subject") or ""),
        "deviceId": str(plan.get("deviceId") or ""),
        "attribute": "switch",
        "events": sorted(events.values(), key=lambda e: _time(e["date"])),
        "returnedRowsInWindow": len(events),
        "requestedSince": interval["since"],
        "requestedUntil": interval["until"],
        "sourceHistoryComplete": False,
        "status": "bounded-events-retained-not-proof-of-complete-history",
    }


__all__ = ["build_focal_source_plan", "project_focal_state_result"]
