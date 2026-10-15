"""Host-owned, exact-time diagnostic source completion for causal investigations.

Unbounded latest-N device history must not substitute for the incident window.
A checked source with no retained values is not evidence of a complete window.
All queries are read-only and identified from *matching* subject receipts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

from causal_evidence_graph import build_causal_evidence_graph
from skill_decision_summary import causal_skill_conclusion
from causal_subject_prefetch import switch_transition_from_prompt


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



_MONTHS = {month.lower(): n for n, month in enumerate(
    ("January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"), 1
)}
_EXPLICIT_DATE = re.compile(
    r"\b([0-3]?\d)\s+(" + "|".join(_MONTHS) + r")\s+(20\d{2})\b",
    re.I,
)
_EXPLICIT_CLOCK = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?\b")


def _requested_clock(question: str, reference: datetime) -> datetime | None:
    """Parse user-provided calendar date and time, using a receipt's offset.

    Never use system time or an invented hub timezone for historical dates.
    The offset is *only* used when a command receipt matches the given date.
    """
    day = _EXPLICIT_DATE.search(str(question or ""))
    clocks = list(_EXPLICIT_CLOCK.finditer(str(question or "")))
    if day is None or len(clocks) != 1 or reference.tzinfo is None:
        return None
    clock = clocks[0]
    try:
        wanted = datetime(
            int(day.group(3)), _MONTHS[day.group(2).lower()],
            int(day.group(1)), int(clock.group(1)), int(clock.group(2)),
            int(clock.group(3) or 0), tzinfo=reference.tzinfo,
        )
    except ValueError:
        return None
    return wanted


def _missing_boundary_plan(
    evidence: list[dict[str, Any]], question: str,
) -> dict[str, Any] | None:
    """Resolve a *read plan*, not a causal verdict, from a dated command clue.

    A historical ON state may have been evicted from latest-N pages. Require
    one unique command-on with app producer, one exact subject/device identity,
    and a date/time stated by the user. Query the entire requested minute
    without declaring that an ON occurred.
    """
    if switch_transition_from_prompt(question) != "on":
        return None
    possible = {}
    for row in evidence:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if _leaf(row) != "hub_list_device_events":
            continue
        details = row.get("details") or {}
        label = str(details.get("label") or "").strip()
        device_id = str(_args(row).get("deviceId") or details.get("deviceId") or "")
        if not label or not device_id.isdigit() or label.casefold() not in question.casefold():
            continue
        for event in details.get("events") or []:
            if not isinstance(event, dict) or event.get("name") != "command-on":
                continue
            command_at = _time(event.get("date"))
            producer = event.get("producedBy") or {}
            app_id = str(producer.get("id") or "")
            if not command_at or not app_id.isdigit() or producer.get("type") != "app":
                continue
            requested = _requested_clock(question, command_at)
            if requested is None:
                continue
            if not 0 <= (requested + timedelta(minutes=1) - command_at).total_seconds() <= 90:
                continue
            if not (requested - timedelta(seconds=30) <= command_at < requested + timedelta(minutes=1)):
                continue
            unique = (label, device_id, command_at.isoformat(), app_id)
            possible[unique] = (command_at, requested)
    if len(possible) != 1:
        return None
    (subject, device_id, command_text, app_id), (command_at, requested) = next(iter(possible.items()))
    if _device_ids(evidence, subject) != {device_id}:
        return None
    # For minute-only clocks the observed ON might have occurred at any
    # second in that minute. Preserve all state events through minute end.
    begin = min(command_at - timedelta(seconds=10), requested - timedelta(seconds=15))
    end = requested + timedelta(minutes=1)
    state_args = {
        "deviceId": device_id, "attribute": "switch",
        "since": _iso_utc(begin), "until": _iso_utc(end), "limit": 100,
    }
    log_args = {
        "appId": int(app_id),
        "since": state_args["since"], "until": state_args["until"],
        "limit": 100,
    }
    for row in evidence:
        if not isinstance(row, dict):
            continue
        args, kind = _args(row), _leaf(row)
        if (
            kind == "hub_list_device_events"
            and str(args.get("deviceId") or "") == device_id
            and str(args.get("attribute") or "") == "switch"
            and _contains(args.get("since"), args.get("until"), begin, end)
        ):
            state_args = None
        if (
            kind == "hub_get_logs"
            and str(args.get("appId") or "") == app_id
            and _contains(args.get("since"), args.get("until"), begin, end)
        ):
            log_args = None
    return {
        "subject": subject, "deviceId": device_id,
        "producerAppId": app_id, "requestedOn": requested.isoformat(),
        "requestedMinuteOnly": True, "observedBoundaryVerified": False,
        "commandTime": command_text,
        "sourceWindow": {"since": _iso_utc(begin), "until": _iso_utc(end)},
        "stateRead": state_args, "producerLogRead": log_args,
        "stateHistoryStatus": "not-verified-at-focal-minute",
        "producerLogStatus": "not-verified-at-command",
        "fullHistoricalCoverageVerified": False,
    }


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
        return _missing_boundary_plan(evidence, question)
    graph = build_causal_evidence_graph(evidence, question)
    if graph.get("scope") != "single-observed-event":
        return _missing_boundary_plan(evidence, question)
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
    for item in rows[:500]:
        event_device_id = str(item.get("deviceId") or "")
        if event_device_id and event_device_id != str(plan.get("deviceId") or ""):
            continue
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
    ordered = sorted(events.values(), key=lambda e: _time(e["date"]))
    # EvidenceRecorder redacts any list after 20 entries. Reserve slots for
    # the exact focal ON and the nearest intervening OFF, even if a noisy
    # stream contains many other events closer to the focal timestamp.
    if len(ordered) > 20:
        target = _time(plan.get("requestedOn")) or stop
        focus_on = [
            ev for ev in ordered
            if ev["value"] == "on" and (
                (0 <= (_time(ev["date"]) - target).total_seconds() < 60)
                if plan.get("requestedMinuteOnly") else
                abs((_time(ev["date"]) - target).total_seconds()) <= .002
            )
        ]
        # Preserve exact ON if known; for minute-only questions retain each
        # candidate (up to cap) so ambiguity cannot be silently resolved.
        required: list[dict[str, Any]] = focus_on[:15]
        selected_on = (_time(focus_on[0]["date"]) if len(focus_on) == 1 else target)
        prior_off = [
            ev for ev in ordered
            if ev["value"] == "off" and _time(ev["date"]) < selected_on
        ]
        if prior_off:
            required.append(prior_off[-1])
        required_keys = {(e["date"], e["value"]) for e in required}
        selected = sorted(
            [ev for ev in ordered
             if (ev["date"], ev["value"]) not in required_keys],
            key=lambda ev: (
                abs((_time(ev["date"]) - target).total_seconds()),
                _time(ev["date"]),
            ),
        )[: 20 - len(required)]
        retained = sorted(required + selected, key=lambda e: _time(e["date"]))
    else:
        retained = ordered
    return {
        "label": str(plan.get("subject") or ""),
        "deviceId": str(plan.get("deviceId") or ""),
        "attribute": "switch",
        "events": retained,
        "returnedRowsInWindow": len(ordered),
        "retainedRows": len(retained),
        "eventsTruncated": len(ordered) > len(retained) or len(rows) > 500,
        "requestedSince": interval["since"],
        "requestedUntil": interval["until"],
        "requestedOn": str(plan.get("requestedOn") or ""),
        "requestedMinuteOnly": bool(plan.get("requestedMinuteOnly")),
        "sourceVerifiedOn": (
            sum(
                1 for ev in retained
                if ev["value"] == "on" and (
                    (0 <= (_time(ev["date"]) - _time(plan["requestedOn"])).total_seconds() < 60)
                    if plan.get("requestedMinuteOnly") else
                    abs((_time(ev["date"]) - _time(plan["requestedOn"])).total_seconds()) <= .002
                )
            ) == 1
        ),
        # Upstream hub_list_device_events reads the currently retained
        # /device/eventsJson page then applies since/until; it cannot page
        # backward into evicted device events. Preserve that limitation.
        "upstreamReturnedCount": len(rows),
        "upstreamSinceMode": (
            str(response_data.get("sinceMode") or "")
            if isinstance(response_data, dict) else ""
        ),
        "upstreamEventStoreCompletenessVerified": False,
        "sourceHistoryComplete": False,
        "status": "bounded-events-retained-not-proof-of-complete-history",
    }


def render_unverified_focal_outcome(
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    question: str,
) -> str | None:
    """Fail closed when exact-window reads cannot uniquely establish the ON.

    Only applies to missing-boundary recovery from a dated command. A normal
    observed incident retains the richer evidence graph and skill synthesis.
    """
    if not plan.get("requestedMinuteOnly"):
        return None
    if build_causal_evidence_graph(evidence, question).get("scope") == "single-observed-event":
        return None
    source_reads = [
        row for row in evidence
        if isinstance(row, dict)
        and row.get("evidence_kind") == "focal_exact_state_history"
        and str((row.get("details") or {}).get("deviceId") or "") == str(plan.get("deviceId") or "")
        and row.get("success") is True
    ]
    failed_reads = [
        row for row in evidence
        if isinstance(row, dict)
        and row.get("evidence_kind") in {
            "focal_source_unavailable", "focal_source_execution_failed",
            "focal_event_payload_unrecognised", "focal_source_catalog_unavailable",
        }
    ]
    if not source_reads and not failed_reads:
        return None
    command_producer = "an identified Hubitat app"
    command_at = _time(plan.get("commandTime"))
    for row in evidence:
        if _leaf(row) != "hub_list_device_events" or row.get("success") is not True:
            continue
        if str((row.get("details") or {}).get("label") or "") != str(plan.get("subject") or ""):
            continue
        for event in (row.get("details") or {}).get("events") or []:
            if not isinstance(event, dict):
                continue
            if event.get("name") != "command-on" or _time(event.get("date")) != command_at:
                continue
            producer = event.get("producedBy") or {}
            if str(producer.get("id") or "") == str(plan.get("producerAppId") or ""):
                command_producer = str(producer.get("label") or command_producer)
    minute = _time(plan.get("requestedOn"))
    minute_text = minute.strftime("%d %B %Y at %H:%M %z") if minute else "the requested time"
    summary = (
        f"**Historical ON not independently verified — {plan.get('subject')}.** "
        f"The recorded command history shows {command_producer} issued an "
        f"on() command at {plan.get('commandTime')}. "
        f"This is a verified Hubitat command invocation, not proof the "
        f"device turned on or that this app caused a later state transition."
    )
    if source_reads:
        count = max(
            len((row.get("details") or {}).get("events") or [])
            for row in source_reads
        )
        check = (
            f"An exact timestamp-filtered state query was completed for "
            f"{minute_text} and preserved {count} state event(s), but it did "
            "not establish exactly one ON in the requested minute."
        )
    else:
        check = (
            "The exact timestamp-filtered state query failed or yielded no "
            "usable event payload, so the requested ON transition could not "
            "be independently established."
        )
    # Reading an exact interval from the native gateway is a filter of the
    # currently retained device events, not an archival query. Show the
    # oldest timestamp *seen in the returned recent page* as context,
    # without claiming it is the oldest event ever stored by Hubitat.
    page_events: list[datetime] = []
    for receipt in evidence:
        if receipt.get("success") is not True:
            continue
        if receipt.get("tool") != "homebrain_device_history":
            continue
        details = receipt.get("details") or {}
        if str(details.get("label") or "") != str(plan.get("subject") or ""):
            continue
        for event in (details.get("correlationEvents") or []):
            if not isinstance(event, dict):
                continue
            if event.get("name") != "switch":
                continue
            when = _time(event.get("date"))
            if when:
                page_events.append(when)
    oldest = min(page_events) if page_events else None
    limitation = (
        f"The oldest switch-state event in the checked recent history was "
        f"{oldest.isoformat()}, later than the requested minute. "
        "This is consistent with older state rows no longer being accessible "
        "through the current native history page; it does not independently "
        "establish the hub's retention settings or prove the event never occurred."
        if oldest and minute and oldest > minute else
        "The native history API filters the hub's currently retained events. "
        "An exact-time query cannot retrieve records already outside that store."
    )
    app_logs = [
        receipt for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("evidence_kind") == "focal_producer_execution_logs"
        and str(_args(receipt).get("appId") or "") == str(plan.get("producerAppId") or "")
        and receipt.get("success") is True
    ]
    if app_logs:
        log_count = max(
            int((receipt.get("details") or {}).get("logCount") or 0)
            for receipt in app_logs
        )
        app_log_note = (
            f"The producer app's timestamp-filtered execution logs were "
            f"checked and returned {log_count} record(s). "
            "This is not proof that no app action occurred."
        )
    else:
        app_log_note = (
            "The producer app's scoped execution-log history was not "
            "successfully verified, so its execution remains unverified."
        )
    return (
        summary + "\n\n" + check
        + "\n\n" + app_log_note + " " + limitation
        + "\n\nHistorical source completeness is unverified. A missing "
          "event in a bounded Hubitat page does not prove the light stayed "
          "off, and a prior command cannot be promoted into verified causation."
        + "\n\n**Next read-only checks:** Check the device's configured "
          "maximum event-history retention and any independent historical "
          "journal; check the producer's archived MQTT/execution records. "
          "Do not change devices or automations."
    )



def project_archived_focal_state(
    stored: dict[str, Any], plan: dict[str, Any],
) -> dict[str, Any]:
    """Only source-timestamped archived ONs establish an exact boundary.

    Collector reception is useful context but can lag the physical action.
    A coverage gap, empty query or duplicated candidate never proves an
    external cause, even if the journal persisted the information correctly.
    """
    begin = _time(plan.get("sourceWindow", {}).get("since"))
    end = _time(plan.get("sourceWindow", {}).get("until"))
    if begin is None or end is None:
        raise ValueError("Exact bounded journal window required")
    events: list[dict[str, Any]] = []
    received_only = 0
    for row in (stored.get("events") or [])[:200]:
        if not isinstance(row, dict) or row.get("attribute") != "switch":
            continue
        if str(row.get("device_id") or "") != str(plan.get("deviceId") or ""):
            continue
        state = str(row.get("value") or "").lower()
        when = _time(row.get("observed_at"))
        if state not in {"on", "off"} or when is None or not begin <= when <= end:
            continue
        if row.get("timestamp_basis") != "source":
            received_only += 1
            continue
        events.append({
            "name": "switch", "value": state,
            "date": when.isoformat(),
            "timestampBasis": "source",
            "source": str(row.get("source") or "")[:80],
        })
    events.sort(key=lambda item: _time(item["date"]))
    requested = _time(plan.get("requestedOn"))
    on_matches = [
        item for item in events
        if requested and item["value"] == "on" and (
            0 <= (_time(item["date"]) - requested).total_seconds() < 60
            if plan.get("requestedMinuteOnly") else
            abs((_time(item["date"]) - requested).total_seconds()) <= .002
        )
    ]
    gaps = [row for row in (stored.get("gaps") or []) if isinstance(row, dict)]
    return {
        "label": plan.get("subject"),
        "deviceId": str(plan.get("deviceId") or ""),
        "attribute": "switch",
        "requestedOn": plan.get("requestedOn"),
        "requestedMinuteOnly": bool(plan.get("requestedMinuteOnly")),
        "events": events[:20],
        "sourceVerifiedOn": len(on_matches) == 1,
        "sourceTimestampedCount": len(events),
        "collectorReceivedOnlyCount": received_only,
        "gapCount": len(gaps),
        "eventsTruncated": len(events) > 20,
        "sourceHistoryComplete": False,
        "archiveHistoricalCoverageComplete": False,
        "provenance": "persistent-homebrain-journal",
    }


async def execute_focal_source_plan(
    plan: dict[str, Any],
    *,
    catalog: Any,
    executor: Any,
    recorder: Any,
    messages: list[dict[str, Any]],
    count_metric: Any,
) -> dict[str, str]:
    """Perform host-authorised source reads independent of model visibility.

    The initial model catalog deliberately hides the broad hub_read_devices
    gateway. Using declared_tool() here silently skipped the focal switch
    read in v0.17.73, although the gateway was available and device reads
    were performed elsewhere in the request. A host-directed read should
    use available_tool(), with explicit failure receipts on any missing
    source, failed operation or undecodable event payload.
    """
    statuses: dict[str, str] = {}
    specifications = (
        ("state", "hub_read_devices", "hub_list_device_events",
         plan.get("stateRead"), "focal_exact_state_history",
         "skills_focal_state_window"),
        ("producer_logs", "hub_read_diagnostics", "hub_get_logs",
         plan.get("producerLogRead"), "focal_producer_execution_logs",
         "skills_focal_producer_logs"),
    )
    for source, gateway, leaf, args, evidence_kind, metric in specifications:
        if not args:
            statuses[source] = "previously-queried"
            continue
        operation = {"tool": leaf, "args": args}
        # Runtime availability and model visibility are intentionally
        # different registries. Host-owned reads must use availability.
        tool = catalog.available_tool(gateway)
        if tool is None:
            statuses[source] = "gateway-unavailable"
            recorder.record(
                gateway, operation, success=False, elapsed_ms=0,
                summary="Required focal source gateway not available",
                supports_live_claim=False,
                evidence_kind="focal_source_unavailable", mutates=False,
                effect="read",
            )
            count_metric("skills_focal_read_failed")
            continue
        try:
            execution = await executor.execute(
                gateway, operation, tool=tool,
                supports_live_claim=True, evidence_kind=evidence_kind,
            )
        except Exception:
            # Do not record exception text, which may contain sensitive
            # broker details. Retain the precise requested source arguments.
            statuses[source] = "execution-failed"
            recorder.record(
                gateway, operation, success=False, elapsed_ms=0,
                summary="Required focal source read raised an error",
                supports_live_claim=False,
                evidence_kind="focal_source_execution_failed",
                mutates=False, effect="read",
            )
            count_metric("skills_focal_read_failed")
            continue
        messages.append({
            "role": "tool", "tool_name": gateway,
            "content": execution.content,
        })
        count_metric(metric)
        if not execution.success or execution.result is None:
            statuses[source] = "read-failed"
            count_metric("skills_focal_read_failed")
            continue
        if source == "producer_logs":
            statuses[source] = "queried"
            continue
        details = project_focal_state_result(execution.result.data, plan)
        if details is None:
            statuses[source] = "unrecognised-event-payload"
            recorder.record(
                gateway, operation, success=False, elapsed_ms=0,
                summary="Focal state gateway returned no parseable event array",
                supports_live_claim=False,
                evidence_kind="focal_event_payload_unrecognised",
                mutates=False, effect="read",
            )
            count_metric("skills_focal_read_failed")
            continue
        recorder.record(
            gateway, operation, success=True, elapsed_ms=0,
            summary="Focal switch window event rows retained",
            supports_live_claim=True,
            evidence_kind="focal_exact_state_history",
            mutates=False, effect="read",
            details=details,
        )
        count = details["returnedRowsInWindow"]
        if count:
            count_metric("skills_focal_state_rows_retained")
            statuses[source] = "rows-retained"
        else:
            statuses[source] = "queried-no-rows"
    return statuses


__all__ = ["build_focal_source_plan", "project_focal_state_result", "execute_focal_source_plan", "render_unverified_focal_outcome", "project_archived_focal_state"]
