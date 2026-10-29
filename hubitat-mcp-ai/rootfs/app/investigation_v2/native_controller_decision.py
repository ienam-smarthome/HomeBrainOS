"""Source-led upstream decision inspection for the Native V2 investigator.

A command tells us *what* an automation requested, not *why* it requested
it. A model may choose a second READ of the independently identified app's
incident-time execution logs. Host never executes that recommendation.
Privacy: only typed, matched app INFO/WARN/ERROR log rows are projected.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .native_source_adapters import log_rows, log_source, safe_string
from .native_event_relevance import clock_candidates

def _time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def controller_decision_followup(
    witnesses: Sequence[Mapping[str,Any]],
    focus_ids: Sequence[str],
    incident: Mapping[str,Any] | None,
    *,
    app_logs_offered: bool,
    question: str = "",
) -> dict[str,Any] | None:
    """Expose an evidence obligation, never a fabricated tool permission.

    Require an approved target-scoped event history and an event's own
    producedBy.appId; app names and apparent names are not authority.
    """
    if not app_logs_offered or not incident or len(set(focus_ids)) != 1:
        return None
    focus = str(focus_ids[0])
    bounds = incident.get("incident_period")
    if not isinstance(bounds, Mapping):
        return None
    start = _time(bounds.get("start_utc_interpreted"))
    end = _time(bounds.get("end_utc_interpreted"))
    if start is None or end is None or end <= start:
        return None
    candidates: list[tuple[datetime,str,str,int]] = []
    for w in witnesses[:20]:
        if (w.get("operation") != "hub_list_device_events"
                or str(w.get("read_filters",{}).get("deviceId")) != focus):
            continue
        data = w.get("source_data")
        if not isinstance(data, Mapping):
            continue
        read = w.get("read")
        if type(read) is not int:
            continue
        for event in data.get("events",[])[:90]:
            if not isinstance(event, Mapping) or not str(event.get("name","")).startswith("command-"):
                continue
            issuer = event.get("producedBy")
            if not isinstance(issuer, Mapping):
                continue
            ident = str(issuer.get("appId") or "")
            stamp = _time(event.get("date"))
            if not ident.isdecimal() or stamp is None or not start-timedelta(hours=2) <= stamp <= end+timedelta(hours=2):
                continue
            label = safe_string(issuer.get("name") or "",80)
            candidates.append((stamp,ident,label,read))
    if not candidates:
        return None
    # For an explicit user incident clock, choosing the last command of the
    # *whole date* can identify a completely different controller. Rank
    # against the incident clock (UTC and BST candidates are ranking only),
    # and require proximity. Never recommend an unrelated later command.
    anchors = clock_candidates(question, bounds)
    if anchors:
        nearest = sorted(candidates, key=lambda row:
                         min(abs((row[0]-anchor).total_seconds())
                             for anchor in anchors))
        stamp,app_id,label,read = nearest[0]
        if min(abs((stamp-anchor).total_seconds()) for anchor in anchors)>1800:
            return None
        selection = "user_incident_clock_nearest_command"
    else:
        # Without a clock, there is no verified exact incident moment.
        # Return bounded source candidate only; the model still chooses.
        stamp,app_id,label,read = max(candidates,key=lambda x:x[0])
        selection = "latest_source_command_no_incident_clock"
    for w in witnesses:
        if w.get("operation") != "hub_get_logs":
            continue
        filters = w.get("read_filters",{})
        if str(filters.get("appId")) != app_id:
            continue
        # Any attempt at app-specific logs is evidence of an inspection,
        # even if empty; do not send model into a retry loop.
        return None
    since=(stamp-timedelta(minutes=12)).isoformat()
    until=(stamp+timedelta(minutes=12)).isoformat()
    return {
        "status":"upstream_decision_unverified",
        "issuer_selection_basis":selection,
        "observed_issuer_app_id":app_id,
        "observed_issuer_label":label,
        "command_source_read":read,
        "proposed_read":{"operation":"hub_get_logs",
                         "args":{"mode":"past","appId":app_id,
                                 "since":since,"until":until,"limit":100}},
        "read_permission":"model_must_select_a_live_advertised_read; host_guard_still_applies",
        "purpose":"Find source-reported app decision inputs, thresholds, timing and triggering sensors; not just a device command.",
        "alternative":"If app logs are unavailable, inspect independently related input-device history and state or report what is unverified.",
        "limitations":"Source-log availability, source timezone and which input caused the action remain unverified.",
    }


def scoped_app_execution_lines(data: Any, app_id: str) -> list[dict[str,Any]]:
    """Expose bounded INFO decision messages only for an exact verified app.

    Never reuse arbitrary app names, messages or log entry IDs as source
    authority. Source log identity must match structured provenance.
    """
    if not isinstance(app_id,str) or not app_id.isdecimal():
        return []
    lines: list[dict[str,Any]]=[]
    for row in (log_rows(data) or [])[:250]:
        kind, ident, label = log_source(row)
        if kind != "app" or ident != app_id:
            continue
        level=str(row.get("level") or row.get("severity") or "").upper()
        if level not in ("INFO","WARN","WARNING","ERROR"):
            continue
        date=safe_string(row.get("time") or row.get("date") or row.get("timestamp") or "",65)
        raw=str(row.get("message") or row.get("msg") or row.get("description") or "")
        # Strip the *already-verified* structured prefix; it is not part of
        # the readable decision message and can mislead the model.
        prefix=f"app|{app_id}|{label}|"
        if raw.startswith(prefix):
            raw=raw[len(prefix):]
        message=safe_string(raw,230)
        if not date or not message:
            continue
        lines.append({"date":date, "level":level, "source_name":label,
                      "source_app_id":app_id, "message":message})
    return lines[:16]


def controller_decision_evidence(
    witnesses: Sequence[Mapping[str,Any]],
    focus_ids: Sequence[str],
    incident: Mapping[str,Any] | None,
) -> list[dict[str,Any]]:
    """Connect per-app INFO log messages to attested target command history.

    Separate source facts, not independently confirmed causal mechanisms.
    Hub log clocks can be naive; compare UTC and UTC+1 *only* for bounded
    proximity, retaining the explicit unverified clock flag.
    """
    if incident is None or len(set(focus_ids)) != 1:
        return []
    focus=str(focus_ids[0])
    refs: dict[str,list[datetime]]={}
    for witness in witnesses[:20]:
        if (witness.get("operation")!="hub_list_device_events"
                or str(witness.get("read_filters",{}).get("deviceId"))!=focus):
            continue
        for event in witness.get("source_data",{}).get("events",[])[:90]:
            if not isinstance(event,Mapping) or not str(event.get("name","")).startswith("command-"):
                continue
            issuer=event.get("producedBy")
            if not isinstance(issuer,Mapping):
                continue
            app=str(issuer.get("appId") or "")
            dt=_time(event.get("date"))
            if app.isdecimal() and dt:
                refs.setdefault(app,[]).append(dt)
    result: list[dict[str,Any]]=[]
    seen=set()
    for witness in witnesses[:20]:
        if witness.get("operation")!="hub_get_logs":
            continue
        read=witness.get("read")
        if type(read) is not int:
            continue
        app=str(witness.get("read_filters",{}).get("appId") or "")
        if app not in refs:
            continue
        for row in witness.get("source_data",{}).get("app_execution_lines",[])[:16]:
            if not isinstance(row,Mapping) or str(row.get("source_app_id"))!=app:
                continue
            raw_date=row.get("date")
            if not isinstance(raw_date,str) or len(raw_date)>65:
                continue
            try:
                stamp=datetime.fromisoformat(raw_date.replace("Z","+00:00"))
            except ValueError:
                continue
            if stamp.tzinfo is None:
                candidates=[stamp.replace(tzinfo=timezone.utc)-timedelta(hours=h)
                            for h in (0,1)]
            else:
                candidates=[stamp.astimezone(timezone.utc)]
            if not any(abs((candidate-other).total_seconds())<=1800
                       for candidate in candidates for other in refs[app]):
                continue
            message=row.get("message")
            if not isinstance(message,str) or not message:
                continue
            key=(read,raw_date,message)
            if key in seen:
                continue
            seen.add(key)
            result.append({
                "read":read,"name":"app_log","date":raw_date,
                "value":message[:230],
                "source_name":safe_string(row.get("source_name"),80),
                "source_kind":"issuing_app",
                "source_clock_verified":False,
            })
            if len(result)>=12:
                return result
    return result


__all__=["controller_decision_followup","scoped_app_execution_lines",
         "controller_decision_evidence"]
