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
    # Model may pick a different attested app; this guidance only proposes
    # the latest relevant command issuer (near the actual source incident).
    stamp,app_id,label,read = max(candidates,key=lambda x:x[0])
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


__all__=["controller_decision_followup","scoped_app_execution_lines"]
