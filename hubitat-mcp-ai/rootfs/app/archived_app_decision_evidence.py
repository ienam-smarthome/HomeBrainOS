"""Read-only, source-typed archived app decision evidence.

The opt-in journal can capture Hubitat /logsocket app messages, but device
history and journal event reads do not reveal those messages. Query the exact
app/time window when a historical investigation already has a focal UTC
clock. Return only privacy-safe metadata to public evidence receipts: never
persist message content in the investigation technical response.

A message that says "lockout enabled" is a recorded textual declaration,
not proof that motion was eligible or an ON command was prevented.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
from typing import Any

from scoped_execution_evidence import bounded_app_log_evidence
from decision_claim_reconciliation import reconcile_decision_claims


_LOCKOUT = re.compile(r"\block[\s-]?out\b|inhibit|suppress", re.I)
_MOTION = re.compile(r"\bmotion\b|occupancy|presence", re.I)
_ACTION = re.compile(
    r"start|engag|activat|enable|block|ignor|skip|cancel|clear|expir|end|"
    r"prevent|suppress|set|inhibit", re.I,
)
_BUTTON_DECLARATION = re.compile(r"\\bbutton\\b.{0,65}\\b(?:push(?:ed)?|press(?:ed)?|held|released)\\b", re.I)
_OFF_DECLARATION = re.compile(r"\\b(?:off\\(\\)|turn(?:ing)?\\s+off|switch(?:ed)?\\s+off|request(?:ed)?\\s+off)\\b", re.I)
_ON_DECLARATION = re.compile(r"\\b(?:on\\(\\)|turn(?:ing)?\\s+on|switch(?:ed)?\\s+on|request(?:ed)?\\s+on)\\b", re.I)
_LEVEL_DECLARATION = re.compile(r"\\b(?:setLevel\\(|brightness|dimmer\\s+level)\\b", re.I)
_MODE_DECLARATION = re.compile(r"\\b(?:mode\\s+change|mode\\s+(?:set|became|changed)|school run)\\b", re.I)


def _decision_stage(message: str) -> str | None:
    if _BUTTON_DECLARATION.search(message):
        return "reported-button-action"
    if _OFF_DECLARATION.search(message):
        return "reported-off-request"
    if _ON_DECLARATION.search(message):
        return "reported-on-request"
    if _LEVEL_DECLARATION.search(message):
        return "reported-brightness-handling"
    if _LOCKOUT.search(message) and _ACTION.search(message):
        return "reported-lockout-handling"
    if _MOTION.search(message) and (_ACTION.search(message) or re.search(r"\\b(?:active|inactive|detected)\\b", message, re.I)):
        return "reported-motion-handling"
    if _MODE_DECLARATION.search(message):
        return "reported-mode-handling"
    return None


def _aware(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def _empty(reason: str, app_id: str) -> dict[str, Any]:
    return {
        "schema": "archived-app-log-evidence-v1",
        "appId": str(app_id),
        "status": reason,
        "configuredToCaptureApp": False,
        "logSocketConnectedAtRead": False,
        "querySucceeded": False,
        "returnedRows": None,
        "reportedDecisionRows": [],
        "captureCompletenessVerified": False,
        "textExcerptsInPublicEvidence": False,
        "historicalExecutionVerified": False,
        "effectiveInhibitionVerified": False,
        "collectorTimestampIsNotSourceEmissionClock": True,
    }


async def archived_app_decision_evidence(
    journal: Any, *, app_id: str, since: str, until: str,
) -> dict[str, Any]:
    """Check capture readiness and read bounded persisted app messages."""
    result = _empty("journal-unavailable", app_id)
    if journal is None or not getattr(journal, "enabled", False):
        return result
    if not getattr(journal, "_started", False):
        result["status"] = "journal-not-started"
        return result
    configured = (
        bool(getattr(journal, "capture_logs", False))
        and (str(app_id) in getattr(journal, "log_app_ids", frozenset())
             or "*" in getattr(journal, "log_app_ids", frozenset()))
    )
    result["configuredToCaptureApp"] = configured
    connected = getattr(journal, "_connected", {})
    result["logSocketConnectedAtRead"] = (
        connected.get("logs") is True
        if isinstance(connected, dict) else False
    )
    if not configured:
        result["status"] = "app-log-capture-not-enabled-for-app"
        return result

    try:
        data = await asyncio.to_thread(
            journal.query, since=since, until=until,
            app_id=str(app_id), limit=100,
        )
    except Exception:
        result["status"] = "journal-app-log-query-failed"
        return result

    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        result["status"] = "journal-app-log-query-failed"
        return result
    result["querySucceeded"] = True
    rows = []
    rejected = 0
    for item in data["events"]:
        if not isinstance(item, dict):
            continue
        if str(item.get("stream") or "") != "logs":
            rejected += 1
            continue
        if str(item.get("app_id") or "") != str(app_id):
            rejected += 1
            continue
        rows.append(item)

    log_gaps = [
        gap for gap in data.get("gaps") or []
        if isinstance(gap, dict) and gap.get("stream") == "logs"
    ]
    result["logCaptureGapWindows"] = len(log_gaps)
    result["excludedMismatchedRows"] = rejected
    result["returnedRows"] = len(rows)
    result["status"] = (
        "archived-app-log-rows-observed" if rows
        else "no-app-log-rows-in-requested-window"
    )

    focal = _aware(since)
    packaged = []
    safe_candidates = []
    for index, row in enumerate(rows):
        recv = _aware(row.get("received_at") or row.get("observed_at"))
        if recv is None:
            continue
        message = str(row.get("message") or "")
        packed = {
            "appId": str(app_id), "timestamp": recv.isoformat(),
            "level": str(row.get("attribute") or "")[:16],
            "message": message,
        }
        packaged.append(packed)
        stage = _decision_stage(message)
        if stage is None:
            continue
        safe_candidates.append({
            "rowId": f"journal-log-{index+1}",
            "stage": stage,
            "collectorReceivedAtUtc": recv.isoformat(timespec="milliseconds"),
            "sourceTimestampBasis": "collector-received",
            "logTextOmitted": True,
            "declaredEffectNotIndependentlyVerified": True,
        })

    excerpts, summary = bounded_app_log_evidence(
        {"logs": packaged}, str(app_id),
    )
    # Reuse the existing typed textual-decision detector. Its results cannot
    # upgrade proof of native motion-activation eligibility or effective
    # suppression of a subsequent light ON.
    reconciled = reconcile_decision_claims("", excerpts, focal_off=focal)
    result["reportedDecisionRows"] = safe_candidates[:12]
    result["reviewableRows"] = summary["reviewableRows"]
    result["textualDecisionDeclarations"] = len(
        reconciled["logDeclarationCandidates"]
    )
    result["reportedHistoricalLockoutStatement"] = any(
        row["stage"] == "reported-lockout-handling"
        for row in safe_candidates
    )
    result["historicalExecutionVerified"] = False
    result["effectiveInhibitionVerified"] = False
    result["captureCompletenessVerified"] = False
    return result


__all__ = ["archived_app_decision_evidence"]
