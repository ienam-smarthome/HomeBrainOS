"""Bounded, privacy-safe app decision archive correlation for group incidents.

Read only app IDs independently confirmed as issued-command producers in
successful, named device histories. Archived /logsocket rows are received
time evidence, NOT proof of source emission time or that the app initiated
a preceding switch transition. The raw message stays in the local journal;
no raw log text is injected into public MCP diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from archived_app_decision_evidence import archived_app_decision_evidence
from group_journal_recovery import journal_incident_bounds
from unified_investigation_bridge import collect_unified_evidence


async def recover_group_app_decisions(
    *, journal: Any, recorder: Any, question: str,
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "not-needed", "app_queries": 0,
        "app_log_rows": 0, "decision_declarations": 0,
    }
    facts = collect_unified_evidence(receipts, question)
    if facts is None:
        report["status"] = "no-verified-device-source"
        return report
    # NEVER accept unverified app IDs invented in the user's question or by
    # an LLM. Extract only concrete issuer appIds in observed command records.
    source_ids = sorted({
        str(row.get("app_id") or "")
        for row in facts.get("incident_ledger", [])
        if (str(row.get("event_class") or "").startswith("issued_")
            and str(row.get("app_id") or "").isdigit())
    }, key=int)[:8]
    if not source_ids:
        report["status"] = "no-recorded-app-issuer"
        return report
    scope = journal_incident_bounds(question, receipts)
    if scope is None:
        report["status"] = "incident-window-unverified"
        return report
    since, until, zone = scope
    if (journal is None or not getattr(journal, "enabled", False)
            or not getattr(journal, "_started", False)):
        report["status"] = "journal-unavailable"
        return report
    report["status"] = "checked"
    report["app_ids"] = source_ids
    already = {
        str((r.get("arguments") or {}).get("app_id") or "")
        for r in receipts if r.get("evidence_kind") == "group_archived_app_decisions"
    }
    for app_id in source_ids:
        if app_id in already:
            continue
        result = await archived_app_decision_evidence(
            journal, app_id=app_id, since=since, until=until)
        rows = result.get("returnedRows")
        decision_rows = result.get("reportedDecisionRows")
        report["app_queries"] += 1 if result.get("querySucceeded") else 0
        report["app_log_rows"] += rows if type(rows) is int and rows >= 0 else 0
        report["decision_declarations"] += len(decision_rows or [])
        # Only structured source metadata: original messages remain on
        # local disk, never in public evidence or model prompts.
        recorder.record(
            "homebrain_evidence_journal",
            {"app_id": app_id, "since": since, "until": until},
            success=bool(result.get("querySucceeded")),
            elapsed_ms=0,
            summary="Archived app " + app_id + ": " + str(result.get("status")),
            supports_live_claim=bool(result.get("reportedDecisionRows")),
            evidence_kind="group_archived_app_decisions",
            effect="read", mutates=False,
            details={
                "appId": app_id,
                "status": result.get("status"),
                "configuredToCaptureApp": result.get("configuredToCaptureApp", False),
                "returnedRows": result.get("returnedRows"),
                "reportedDecisionRows": (decision_rows or [])[:12],
                "decisionDeclarations": result.get("textualDecisionDeclarations", 0),
                "gapCount": result.get("logCaptureGapWindows", 0),
                "collectorTimestampIsNotSourceEmissionClock": True,
                "historicalExecutionVerified": False,
                "captureCompletenessVerified": False,
                "window": {"since": since, "until": until, "zone": zone},
            },
        )
    return report


__all__ = ["recover_group_app_decisions"]
