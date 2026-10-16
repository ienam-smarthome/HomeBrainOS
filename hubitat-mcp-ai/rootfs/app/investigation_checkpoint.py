"""General purpose evidence checkpoint for a bounded MCP investigation.

The checkpoint is independent of specific rooms/devices/apps or installed MCP
leaf names. The available catalog controls source selection. No raw tool
payload, app settings, MQTT credentials or historic conclusions are imported
into model guidance; only read receipts and coverage limitations.
"""
from __future__ import annotations

import json
from typing import Any

from investigation_policy import is_causal_investigation, is_history_investigation
from investigation_intelligence import plan_investigation
from skill_secret_guard import redact_secrets


def is_investigative_question(question: str) -> bool:
    """Recognise investigative intent; excludes routine state/control answers."""
    text = " ".join(str(question or "").casefold().split())
    if not text:
        return False
    return bool(
        is_causal_investigation(question)
        or is_history_investigation(question)
        or plan_investigation(question) is not None
        or (
            any(word in text for word in ("investigat", "diagnos", "troubleshoot",
                                          "analyse", "analyze", "explain why"))
            and any(word in text for word in ("device", "app", "automation",
                                              "rule", "hub", "sensor", "mqtt",
                                              "light", "scheduled", "offline"))
        )
    )


def _source_name(row: dict[str, Any]) -> str:
    args = row.get("arguments") or {}
    leaf = row.get("sub_tool")
    if not leaf and isinstance(args, dict):
        leaf = args.get("tool")
    return str(leaf or row.get("tool") or "unknown")[:80]


def _source_scope(row: dict[str, Any]) -> dict[str, str]:
    args = row.get("arguments") or {}
    if isinstance(args, dict) and isinstance(args.get("args"), dict):
        args = args["args"]
    if not isinstance(args, dict):
        return {}
    keys = ("deviceId", "device_id", "appId", "app_id", "attribute",
            "since", "until", "hoursBack", "limit")
    return {key: str(args[key])[:100] for key in keys if args.get(key) is not None}


def build_evidence_checkpoint(
    objective: str,
    receipts: list[dict[str, Any]],
    *,
    available_read_tools: tuple[str, ...] = (),
    max_receipts: int = 18,
) -> dict[str, Any]:
    """Summarise source availability and uncertainty without copying log bodies."""
    evidence = []
    seen = set()
    gaps: list[str] = []
    for row in receipts:
        if not isinstance(row, dict):
            continue
        source = _source_name(row)
        scope = _source_scope(row)
        key = (source, json.dumps(scope, sort_keys=True),
               str(row.get("evidence_kind") or ""))
        if key in seen:
            continue
        seen.add(key)
        details = row.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        observed = None
        for count_key in ("returnedRowsInWindow", "retainedRows",
                          "sourceTimestampedCount", "collectorReceivedOnlyCount",
                          "eventCount", "logCount", "count"):
            if isinstance(details.get(count_key), int):
                observed = {count_key: details[count_key]}
                break
        if details.get("sourceVerifiedOn") is False:
            gaps.append("Exact historical state transition not verified")
        if details.get("sourceHistoryComplete") is False:
            gaps.append("Source event-history completeness unverified")
        if details.get("journalQueryTruncated") or details.get("eventsTruncated"):
            gaps.append("An evidence source was truncated")
        if row.get("success") is False:
            gaps.append("A requested source returned an error or was unavailable")
        if details.get("historicalExecutionNotProven"):
            gaps.append("Current app configuration does not prove past execution")
        evidence.append({
            "source": source,
            "scope": scope,
            "kind": str(row.get("evidence_kind") or "tool_result")[:90],
            "checked": row.get("success") is True,
            "recorded_count": observed,
        })
    return {
        "schema": "homebrain-evidence-checkpoint/v1",
        "objective": str(objective or "")[:400],
        "sources": evidence[-max(1, min(30, max_receipts)):],
        "open_questions": list(dict.fromkeys(gaps))[:8],
        "declared_read_tools": list(available_read_tools)[:24],
        "source_success_is_not_causal_proof": True,
        "no_source_is_proof_of_inactivity": False,
    }


def render_investigation_checkpoint(
    objective: str,
    receipts: list[dict[str, Any]],
    *,
    available_read_tools: tuple[str, ...] = (),
) -> str:
    packet = build_evidence_checkpoint(
        objective, receipts, available_read_tools=available_read_tools,
    )
    return (
        "HOST READ-ONLY INVESTIGATION CHECKPOINT (not a cause verdict):\n"
        + redact_secrets(json.dumps(packet, ensure_ascii=False, separators=(",", ":")))
        + "\nThe user's actual question controls the next step. Review the "
          "checked evidence and identify the most informative **unanswered** "
          "subquestion, regardless of device or domain. If an available "
          "read-only MCP gateway can distinguish the strongest competing "
          "explanations, call it with a bounded target and incident window. "
          "Use live MCP discovery/guide when the required leaf is unknown; "
          "never invent an operation or treat an event listener as an initiator. "
          "Do not repeat checked sources without a specific new field. "
          "Never send a write call, credentials, or unbounded inventory scan. "
          "If nothing accessible could materially improve the evidence, "
          "stop and explain the leading hypothesis, contradiction, and "
          "exact remaining source limitations. Reception-only reports remain "
          "separate from source-event timestamps and physical actuation. "
          "Keep this evidence decision applicable to lighting, heating, "
          "device health, MQTT, rules, scheduler and energy questions."
    )


__all__ = [
    "is_investigative_question", "build_evidence_checkpoint",
    "render_investigation_checkpoint",
]
