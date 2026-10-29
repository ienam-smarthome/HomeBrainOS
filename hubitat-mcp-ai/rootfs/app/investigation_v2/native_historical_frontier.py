"""Historical evidence frontier for an AI investigating automation decisions.

A controller-issued actuator command is not the controller's decision input.
If the source app's currently returned logs do not cover the incident,
the next useful read must be from another source, not another overlapping
query of the same log feed.

No keyword routing, tool execution, identity promotion or permissions here.
All claims refer to actual read receipts with explicit coverage limitations.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Mapping, Sequence

from .native_controller_decision import controller_decision_followup
from .native_event_relevance import clock_candidates


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _possible_instants(value: Any) -> list[datetime]:
    if not isinstance(value, str):
        return []
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError):
        return []
    if dt.tzinfo is not None:
        return [dt.astimezone(timezone.utc)]
    return [dt.replace(tzinfo=timezone.utc) - timedelta(hours=h) for h in (0, 1)]


def historical_controller_frontier(
    question: str,
    witnesses: Sequence[Mapping[str, Any]],
    focus_ids: Sequence[str],
    coverage: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Ground a source-window gap from incident issuer plus app-log receipts.

    Does not assert the historical log never existed. A returned bounded
    source window cannot prove completeness or a universal retention limit.
    """
    if coverage is None or len(set(focus_ids)) != 1:
        return None
    period = coverage.get("incident_period")
    if not isinstance(period, Mapping):
        return None
    anchors = clock_candidates(question, period)
    if not anchors:
        return None
    # Reuse source-ID and incident-clock verification, while excluding the
    # existing app reads so the candidate issuer can still be recovered.
    target_reads = [w for w in witnesses if
                    w.get("operation") == "hub_list_device_events"]
    issuer = controller_decision_followup(
        target_reads, focus_ids, coverage,
        app_logs_offered=True, question=question)
    if issuer is None:
        return None
    app_id = issuer["observed_issuer_app_id"]
    app_label = issuer["observed_issuer_label"]
    app_reads = [w for w in witnesses
                 if w.get("operation") == "hub_get_logs"
                 and str(w.get("read_filters", {}).get("appId")) == app_id
                 and isinstance(w.get("source_data"), Mapping)]
    if not app_reads:
        return None
    oldest = []
    newest = []
    inspected = []
    any_incident_rows = False
    for w in app_reads:
        data = w["source_data"]
        summary = data.get("log_summary")
        if not isinstance(summary, Mapping):
            continue
        for field, destination in (("oldest_returned", oldest),
                                   ("newest_returned", newest)):
            times = _possible_instants(summary.get(field))
            if times:
                destination.extend(times)
        inspected.append({
            "read": w.get("read"),
            "returned_rows": summary.get("returned_rows"),
            "oldest_returned": summary.get("oldest_returned"),
            "newest_returned": summary.get("newest_returned"),
            "total_reported_by_gateway": summary.get("total_reported_by_gateway"),
            "source_complete": False,
        })
        for row in data.get("app_execution_lines", [])[:20]:
            if not isinstance(row, Mapping):
                continue
            dates = _possible_instants(row.get("date"))
            if dates and any(
                abs((dt - anchor).total_seconds()) <= 1800
                for dt in dates for anchor in anchors
            ):
                any_incident_rows = True
    if not inspected:
        return None
    if any_incident_rows or coverage.get("controller_decision_log_count", 0):
        return {
            "status": "incident_decision_logs_observed",
            "app_id": app_id,
            "app_label": app_label,
            "read_receipts": inspected[-4:],
            "timestamps_verified_as_utc": False,
        }
    # Do not declare historical coverage definitively missing from one
    # empty filtered read. Require a second source observation showing the
    # feed currently returns only later events (even though older archives
    # may exist elsewhere).
    later_only = bool(oldest) and all(
        dt > anchor + timedelta(minutes=30)
        for dt in oldest for anchor in anchors
    )
    status = (
        "incident_not_in_returned_app_log_window" if later_only
        else "incident_not_observed_in_scoped_app_log_reads")
    return {
        "status": status,
        "app_id": app_id,
        "app_label": app_label,
        "read_receipts": inspected[-4:],
        "earliest_source_log_timestamp": min(
            (w["oldest_returned"] for w in inspected
             if w["oldest_returned"]), default=None),
        "incident_time_zone_verified": False,
        "source_history_complete": False,
        "next_evidence": (
            "Do not reinterpret later unrelated controller decisions as "
            "this incident. Use a different independent historical source "
            "such as the actual input sensors' dated events (resolve their "
            "names against live identity), or an independently retained "
            "app execution archive; otherwise report the missing cause."),
    }


def reject_redundant_controller_logs(
    operation: str, filters: Mapping[str, Any],
    frontier: Mapping[str, Any] | None,
) -> bool:
    """Prevent further same-feed queries only after later-only coverage.

    Other logs, different apps, independent device history, and genuine
    uninspected scopes are unaffected.
    """
    return (
        operation == "hub_get_logs"
        and frontier is not None
        and frontier.get("status") == "incident_not_in_returned_app_log_window"
        and str(filters.get("appId")) == str(frontier.get("app_id"))
    )


__all__ = ["historical_controller_frontier",
           "reject_redundant_controller_logs"]
