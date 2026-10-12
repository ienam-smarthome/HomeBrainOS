"""Small, source-linked runtime evidence packets for retrospective investigations.

Read-only app logs must be usable by the synthesis model, not represented
only as 'N returned rows'. Keep *message bodies* out of public evidence
receipts; supply strictly bounded model-only excerpts with source IDs and
explicit scope/timestamp provenance. Neither a log row nor event trigger
metadata is an execution-decision proof without content supporting that fact.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import json
import re

_IDENTIFIER = re.compile(r"(?:app[:|]\s*|^app\s+)(\d+)(?:[:|]|\b)", re.I)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_SECRETS = re.compile(
    r"\b((?:token|password|api[_ -]?key|secret|pin)\s*[:=]\s*)"
    r"([^\s,;]+)", re.I,
)


def _source_id(row: dict[str, Any]) -> str:
    for key in ("appId", "app_id"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    for key in ("source", "sourceName"):
        raw = row.get(key)
        if isinstance(raw, str):
            found = _IDENTIFIER.search(raw)
            if found:
                return found.group(1)
    return ""


def _timestamp(row: dict[str, Any]) -> tuple[str, bool]:
    raw = row.get("date") or row.get("timestamp") or row.get("time")
    if raw in (None, ""):
        return "", False
    value = str(raw)[:64]
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value, stamp.tzinfo is not None
    except (ValueError, TypeError):
        return value, False


def bounded_app_log_evidence(
    data: dict[str, Any] | None, app_id: str, *, limit: int = 12,
    message_limit: int = 240,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return model-only excerpts + safe, count-only receipt metadata.

    Caller has already requested the bounded app-specific backend filter.
    If an explicit row ID conflicts with that filter, never show/count the
    row as belonging to the target. If a row lacks its own app ID, retain
    it with 'server-filter-only' provenance rather than asserting proof.
    """
    logs = data.get("logs") if isinstance(data, dict) else None
    if not isinstance(logs, list):
        return [], {
            "returnedRows": None, "reviewableRows": 0, "sourceIdVerifiedRows": 0,
            "scopeUnverifiedRows": 0, "mismatchedRowsExcluded": 0,
            "rowContentsIncludedInPublicEvidence": False,
        }
    app_id = str(app_id)
    selected: list[dict[str, Any]] = []
    exact_ids = unverified = mismatched = 0
    for row in logs:
        if not isinstance(row, dict):
            continue
        found = _source_id(row)
        if found and found != app_id:
            mismatched += 1
            continue
        if found:
            exact_ids += 1
        else:
            unverified += 1
        raw = row.get("message") or row.get("msg") or row.get("description")
        if not isinstance(raw, str) or not raw.strip() or len(selected) >= limit:
            continue
        # These excerpts enter the current request's *model context* only;
        # never copy any excerpt into the returned technical JSON.
        scrubbed = _EMAIL.sub("[email]", raw)
        scrubbed = _SECRETS.sub(r"\1[redacted]", scrubbed)
        time_str, offset_verified = _timestamp(row)
        selected.append({
            "sourceRowId": f"app-log-{len(selected)+1}",
            "appId": app_id,
            "scopeBasis": (
                "explicit-app-id" if found else "requested-backend-filter-only"
            ),
            "timestamp": time_str,
            "timestampOffsetVerified": offset_verified,
            "level": str(row.get("level") or "")[:16],
            "message": scrubbed[:message_limit],
        })
    return selected, {
        "returnedRows": len(logs),
        "reviewableRows": len(selected),
        "sourceIdVerifiedRows": exact_ids,
        "scopeUnverifiedRows": unverified,
        "mismatchedRowsExcluded": mismatched,
        "sampleTruncated": len(selected) < exact_ids + unverified,
        "rowContentsIncludedInPublicEvidence": False,
    }


def event_handler_associations(
    data: dict[str, Any], *, focal_off: datetime, app_id: str,
) -> list[dict[str, str]]:
    """Find explicitly named *event-handler associations*, not decisions.

    The Hubitat 'triggered' field on a state event identifies recipients /
    associated handlers. It is not an execution log of a branch or action.
    """
    candidates = (
        data.get("events") or data.get("correlationEvents")
        or data.get("observedEvents") or data.get("boundaryEvents") or []
    )
    if not isinstance(candidates, list):
        return []
    found: dict[str, dict[str, str]] = {}
    for row in candidates:
        if not isinstance(row, dict) or str(row.get("value") or "").lower() != "off":
            continue
        when, aware = _timestamp(row)
        if not aware:
            continue
        try:
            seconds = abs(
                (datetime.fromisoformat(when.replace("Z", "+00:00"))
                 - focal_off).total_seconds()
            )
        except (TypeError, ValueError):
            continue
        if seconds > 0.005:
            continue
        for handler in row.get("triggered") or []:
            if not isinstance(handler, dict):
                continue
            if str(handler.get("appId") or "") != str(app_id):
                continue
            name = str(handler.get("handler") or "").strip()[:90]
            if name:
                found[name] = {
                    "appId": str(app_id), "handler": name,
                    "evidenceKind": "state-event-triggered-handler-reference",
                    "handlerExecutionVerified": "false",
                    "lockoutDecisionVerified": "false",
                }
    return list(found.values())[:8]


def model_only_log_packet(rows: list[dict[str, Any]], app_id: str) -> str:
    """Explain data semantics without supplying any synthetic conclusions."""
    return (
        "BOUNDED APP EXECUTION LOG EVIDENCE — current request only\n"
        f"Requested appId: {app_id}. The following rows are bounded excerpts "
        "of returned backend log data; an unverified per-row app ID or a "
        "timestamp lacking a UTC offset does NOT prove app execution at the "
        "focal moment. Cite row IDs when drawing a positive conclusion. "
        "Distinguish handler entry, state change, lockout activation, "
        "suppressed motion activation, and unrelated diagnostic activity. "
        "Do not infer either execution or non-execution from an empty/ambiguous "
        "result. The packet does not prove complete log capture.\n"
        + json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    )


__all__ = [
    "bounded_app_log_evidence", "event_handler_associations",
    "model_only_log_packet",
]
