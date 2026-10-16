"""Bounded, evidence-derived next reads when an exact historical state is unavailable.

No new authority or free-form tool choices. The focal plan supplies the only
producer app ID, the declared MCP catalog gates reads, and archived app logs
are examined only if collection was explicitly allowlisted. This module
never upgrades collector reception into proof of physical actuation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import re
import time
from typing import Any, Callable

from causal_rule_decision_context import configuration_text
from skill_secret_guard import redact_secrets


def _time(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def _arguments(receipt: dict[str, Any]) -> dict[str, Any]:
    raw = receipt.get("arguments") or {}
    if not isinstance(raw, dict):
        return {}
    return raw.get("args") if isinstance(raw.get("args"), dict) else raw


def plan_unverified_next_reads(
    focal: dict[str, Any],
    receipts: list[dict[str, Any]],
    *,
    app_source_available: bool,
    archive: Any = None,
) -> list[dict[str, Any]]:
    """Plan at most one current app-config and one allowlisted archived log read.

    Neither current app configuration nor an empty log is historical execution
    evidence. Never guess an app ID from a listener, device label or chat text.
    """
    app_id = str(focal.get("producerAppId") or "")
    target_id = str(focal.get("deviceId") or "")
    command = _time(focal.get("commandTime"))
    requested = _time(focal.get("requestedOn"))
    if not (app_id.isdigit() and target_id.isdigit() and command and requested):
        return []
    if command.date() != requested.date() or not 0 <= (requested-command).total_seconds() <= 120:
        return []
    # A source-timestamped focal ON should go through normal causal
    # investigation, not the missing-boundary recovery path.
    if any(
        row.get("success") is True and
        (row.get("details") or {}).get("sourceVerifiedOn") is True and
        row.get("evidence_kind") in {
            "focal_exact_state_history", "focal_archived_state_history"
        }
        for row in receipts if isinstance(row, dict)
    ):
        return []
    attempted = set()
    for row in receipts:
        if not isinstance(row, dict):
            continue
        args = _arguments(row)
        if str(args.get("appId") or "") != app_id:
            continue
        leaf = str(row.get("sub_tool") or
                   (row.get("arguments") or {}).get("tool") or "")
        if leaf == "hub_get_app_config" or row.get("evidence_kind") == "investigator_producer_config":
            attempted.add("config")
        if row.get("evidence_kind") == "investigator_archived_producer_logs":
            attempted.add("archive_logs")
    planned: list[dict[str, Any]] = []
    if app_source_available and "config" not in attempted:
        planned.append({
            "kind": "producer_config", "appId": app_id,
            "gateway": "hub_read_apps_code", "leaf": "hub_get_app_config",
            "arguments": {"appId": app_id, "includeSettings": False},
            "purpose": "Map current command-producing app topology; not historical execution",
        })
    if (
        archive is not None
        and getattr(archive, "enabled", False)
        and getattr(archive, "_started", False)
        and getattr(archive, "capture_logs", False)
        and app_id in set(getattr(archive, "log_app_ids", set()))
        and "archive_logs" not in attempted
    ):
        window = focal.get("journalWindow") or focal.get("sourceWindow") or {}
        if _time(window.get("since")) and _time(window.get("until")):
            planned.append({
                "kind": "archived_logs", "appId": app_id,
                "since": window["since"], "until": window["until"],
                "purpose": "Check retained allowlisted producer logs in incident window",
            })
    return planned[:2]


def _safe_topology_excerpts(data: dict[str, Any]) -> list[str]:
    """Only short redacted, noncredential UI configuration descriptions."""
    excerpts, _ = configuration_text(data)
    result = []
    for line in excerpts:
        if re.search(r"(?i)password|passphrase|token|secret|api.?key|credential|authorization|https?://", line):
            continue
        if len(line) > 240:
            continue
        safe = redact_secrets(line)
        if safe and safe not in result:
            result.append(safe)
    return result[:4]


async def execute_unverified_next_reads(
    focal: dict[str, Any],
    *,
    receipts: list[dict[str, Any]],
    catalog: Any,
    mcp: Any,
    journal: Any,
    recorder: Any,
    tool_succeeded: Callable[[Any], bool],
    increment_metric: Callable[[str], Any],
) -> dict[str, str]:
    """Execute only host-selected, source-scoped, read-only follow-ups."""
    available = (
        callable(getattr(mcp, "call_tool", None))
        and catalog is not None
        and callable(getattr(catalog, "available_tool", None))
        and catalog.available_tool("hub_read_apps_code") is not None
    )
    steps = plan_unverified_next_reads(
        focal, receipts, app_source_available=available, archive=journal,
    )
    outcomes: dict[str, str] = {}
    for step in steps:
        app_id = step["appId"]
        if step["kind"] == "producer_config":
            request = {"tool": step["leaf"], "args": step["arguments"]}
            start = time.monotonic()
            result = None
            try:
                result = await mcp.call_tool(step["gateway"], request)
                successful = bool(tool_succeeded(result))
            except Exception:
                successful = False
            data = (
                result.data if successful and isinstance(getattr(result, "data", None), dict)
                else {}
            )
            app = data.get("app") if isinstance(data.get("app"), dict) else {}
            identity_verified = str(app.get("id") or "") == app_id
            descriptions = _safe_topology_excerpts(data) if identity_verified else []
            recorder.record(
                step["gateway"], request,
                success=successful,
                elapsed_ms=round((time.monotonic()-start)*1000),
                summary="Read current command producer topology"
                        if successful else "Command producer topology unavailable",
                supports_live_claim=False,
                evidence_kind="investigator_producer_config",
                mutates=False, effect="read",
                details={
                    "appId": app_id, "currentOnly": True,
                    "identityVerified": identity_verified,
                    "configured": descriptions,
                    "historicalExecutionNotProven": True,
                } if successful else {"appId": app_id, "unavailable": True},
            )
            outcomes["producer_config"] = (
                "configuration-checked" if successful and identity_verified
                else "unavailable-or-unverified"
            )
            increment_metric("investigator_producer_config_read")
        elif step["kind"] == "archived_logs":
            start = time.monotonic()
            stored = None
            try:
                stored = await asyncio.to_thread(
                    journal.query, app_id=app_id,
                    since=step["since"], until=step["until"], limit=40,
                )
            except (OSError, ValueError, TypeError):
                pass
            matching = (
                [row for row in stored.get("events", []) if
                 isinstance(row, dict) and row.get("stream") == "logs"
                 and str(row.get("app_id") or "") == app_id]
                if isinstance(stored, dict) else []
            )
            recorder.record(
                "homebrain_evidence_journal",
                {"app_id": app_id, "since": step["since"], "until": step["until"]},
                success=isinstance(stored, dict),
                elapsed_ms=round((time.monotonic()-start)*1000),
                summary="Bounded allowlisted producer app-log archive checked"
                        if stored is not None else "Archived producer logs unavailable",
                supports_live_claim=False,
                evidence_kind="investigator_archived_producer_logs",
                effect="read", mutates=False,
                details={
                    "appId": app_id, "retainedLogCount": len(matching),
                    "queryTruncated": bool(stored.get("truncated")),
                    "gapCount": len(stored.get("gaps") or []),
                    "historicalExecutionNotProven": True,
                    "redactedMessageBodiesNotReturned": True,
                } if isinstance(stored, dict) else {
                    "appId": app_id, "unavailable": True,
                },
            )
            outcomes["archived_logs"] = (
                "queried" if isinstance(stored, dict) else "unavailable"
            )
            increment_metric("investigator_archived_producer_log_read")
    return outcomes


def render_followup_findings(receipts: list[dict[str, Any]], app_id: str) -> str:
    """Explain what additional investigation established, without inference."""
    relevant = [
        row.get("details") or {}
        for row in receipts if isinstance(row, dict)
        and row.get("evidence_kind") == "investigator_producer_config"
        and str(_arguments(row).get("appId") or "") == app_id
    ]
    archived = [
        row.get("details") or {}
        for row in receipts if isinstance(row, dict)
        and row.get("evidence_kind") == "investigator_archived_producer_logs"
        and str(_arguments(row).get("app_id") or "") == app_id
    ]
    paragraphs = []
    if relevant:
        current = relevant[-1]
        if current.get("identityVerified"):
            description = current.get("configured") or []
            paragraphs.append(
                "**Producer topology follow-up (current configuration only):** "
                + ("; ".join(description[:4]) if description
                   else "The verified producer app configuration was checked, "
                        "but it contained no safe, relevant topology excerpts.")
                + " This does not establish the historical command input."
            )
        else:
            paragraphs.append(
                "**Producer topology follow-up:** The app configuration could "
                "not be independently matched to the recorded command producer."
            )
    if archived:
        item = archived[-1]
        if "retainedLogCount" in item:
            paragraphs.append(
                "**Archived producer app logs:** "
                + str(item["retainedLogCount"])
                + " retained allowlisted log row(s) in the scoped window"
                + (" (query capped)." if item.get("queryTruncated") else ".")
                + " This count does not prove that an action did or did not execute."
            )
        else:
            paragraphs.append("**Archived producer app logs:** Source unavailable.")
    return "\n\n".join(paragraphs)


__all__ = [
    "plan_unverified_next_reads", "execute_unverified_next_reads",
    "render_followup_findings",
]
