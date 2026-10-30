"""General purpose evidence checkpoint for a bounded MCP investigation.

The checkpoint is independent of specific rooms/devices/apps or installed MCP
leaf names. The available catalog controls source selection. No raw tool
payload, app settings, MQTT credentials or historic conclusions are imported
into model guidance; only read receipts and coverage limitations.
"""
from __future__ import annotations

import json
import re
from typing import Any

from investigation_policy import is_causal_investigation, is_history_investigation
from investigation_intelligence import plan_investigation
from causal_initiator_provenance_guard import build_state_report_provenance
from general_evidence_completion import assess_task_source_coverage, EVIDENCE_KINDS
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
                                              "motion", "lockout", "occupancy",
                                              "light", "scheduled", "offline"))
        )
    )


def requests_explicit_hypothesis_comparison(question: str) -> bool:
    """Opt-in deep comparison, not a general causal/history fast-path override.

    The request must be investigative AND explicitly ask for contrasting
    hypotheses. It never supplies permissions, tools or causal conclusions.
    """
    text = " ".join(str(question or "").casefold().split())
    return bool(
        is_investigative_question(question)
        and re.search(
            r"\b(?:competing|hypothes(?:is|es)|"
            r"compare (?:the )?(?:(?:most |three |two |several )?"
            r"(?:possible |plausible |likely |competing )?)?"
            r"(?:root )?(?:causes|explanations)|"
            r"distinguish (?:between |among )?(?:possible |plausible )?"
            r"(?:causes|explanations))\b",
            text,
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
    candidate_hypotheses: tuple[Any, ...] = (),
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
    # Model-proposed alternatives are questions, never source-supported
    # conclusions. Check ONLY the declared read-source class, not a hypothesis
    # truth value. A checked-empty source still cannot exclude a candidate.
    comparisons: list[dict[str, str]] = []
    for candidate in candidate_hypotheses[:3]:
        kind = getattr(candidate, "evidence_kind", None)
        explanation = getattr(candidate, "explanation", None)
        discriminator = getattr(candidate, "distinguishing_question", None)
        if (kind not in EVIDENCE_KINDS
                or not isinstance(explanation, str)
                or not isinstance(discriminator, str)):
            continue
        checked = assess_task_source_coverage((kind,), receipts).sources_checked
        required_origin = getattr(candidate, "required_origin", "unspecified")
        if required_origin not in ("hubitat", "upstream", "physical", "unspecified"):
            required_origin = "unspecified"
        # The current Hubitat MCP inventory cannot independently prove an
        # upstream broker packet or physical endpoint response. Do not mark
        # the discriminator answered merely because a Hubitat source class
        # was queried successfully. A later trusted origin-specific source
        # receipt contract can extend this conservatively.
        origin_state = (
            f"{required_origin}-origin-not-independently-verified"
            if required_origin in ("upstream", "physical")
            else "hubitat-source-class-observed" if required_origin == "hubitat" and checked
            else "origin-not-established"
        )
        comparisons.append({
            "candidate": explanation[:140],
            "discriminating_question": discriminator[:180],
            "source_kind": kind,
            "source_state": ("source-class-checked-verdict-unverified"
                             if checked else "source-class-not-checked"),
            "required_origin": required_origin,
            "origin_state": origin_state,
            "discriminator_verified": False,
            "hypothesis_verdict": "unverified",
        })
    provenance = build_state_report_provenance(receipts)
    state_reported = provenance["state_report_count"] > 0
    # A source-reported state and its bridge/listeners are evidence-discovery
    # leads, not proof of the command origin. Keep missing causal links as
    # model-selectable investigative questions rather than a fixed tool route.
    provenance_discriminators = (
        ["For the observed state transitions, which independently logged "
         "command (including timestamp and issuer) preceded each transition?",
         "Which source-attested controller/input dependencies and execution "
         "decisions can distinguish the remaining candidate initiators?"]
        if state_reported else []
    )
    return {
        "schema": "homebrain-evidence-checkpoint/v1",
        "state_report_provenance": provenance if state_reported else None,
        "objective": str(objective or "")[:400],
        "sources": evidence[-max(1, min(30, max_receipts)):],
        "open_questions": list(dict.fromkeys(gaps))[:8],
        "competing_hypothesis_checks": comparisons,
        "next_unchecked_discriminators": (
            provenance_discriminators + [
                row["discriminating_question"] for row in comparisons
                if (row["source_state"] == "source-class-not-checked"
                    or row["required_origin"] in ("upstream", "physical"))
            ]
        )[:4],
        "declared_read_tools": list(available_read_tools)[:24],
        "source_success_is_not_causal_proof": True,
        "no_source_is_proof_of_inactivity": False,
    }


def render_investigation_checkpoint(
    objective: str,
    receipts: list[dict[str, Any]],
    *,
    available_read_tools: tuple[str, ...] = (),
    candidate_hypotheses: tuple[Any, ...] = (),
) -> str:
    packet = build_evidence_checkpoint(
        objective, receipts, available_read_tools=available_read_tools,
        candidate_hypotheses=candidate_hypotheses,
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
          "Compare only model-proposed competing hypotheses as UNVERIFIED "
          "questions, never findings. A checked source class cannot establish "
          "or refute one without matching scoped evidence. An upstream MQTT "
          "broker or physical-packet requirement is not met by Hubitat's "
          "cached status, logs or driver source alone. Prioritize a "
          "still-unchecked discriminator when a safe relevant read exists. "
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
    "is_investigative_question", "requests_explicit_hypothesis_comparison",
    "build_evidence_checkpoint",
    "render_investigation_checkpoint",
]
