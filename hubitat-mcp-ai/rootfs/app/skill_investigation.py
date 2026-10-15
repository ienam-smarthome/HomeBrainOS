"""Reusable evidence-to-hypotheses projection for the investigator skill.

The output contains only source-derived facts, scoped gaps and candidate
hypotheses. It deliberately does not declare a causal verdict.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from causal_evidence_graph import build_causal_evidence_graph
from causal_command_provenance import preceding_command_candidates


def _time(value: Any) -> datetime | None:
    try:
        item = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return item if item.tzinfo else None
    except (ValueError, TypeError):
        return None


def _event_rows(evidence: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    """Collect only actual subject state events, de-duplicate overlapping views."""
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for receipt in evidence:
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            continue
        details = receipt.get("details")
        if not isinstance(details, dict):
            continue
        if str(details.get("label") or "").casefold() != subject.casefold():
            continue
        for field in ("correlationEvents", "boundaryEvents", "observedEvents", "events"):
            rows = details.get(field)
            if not isinstance(rows, list):
                continue
            for ev in rows:
                if not isinstance(ev, dict) or str(ev.get("name") or "") != "switch":
                    continue
                stamp = str(ev.get("date") or "")
                state = str(ev.get("value") or "").casefold()
                if _time(stamp) is not None and state in ("on", "off"):
                    found[(stamp, state)] = {"date": stamp, "state": state}
    return sorted(found.values(), key=lambda row: _time(row["date"]))


def build_skill_investigation(
    evidence: list[dict[str, Any]], user_request: str,
) -> dict[str, Any] | None:
    """Build a compact typed timeline and ranked possibilities from receipts."""
    graph = build_causal_evidence_graph(evidence, user_request)
    if graph.get("scope") != "single-observed-event":
        return None
    focus = graph.get("focus") or {}
    subject = str(focus.get("subject") or "")
    boundary = str(focus.get("on") or "")
    if not subject or _time(boundary) is None:
        return None
    clue_rows = preceding_command_candidates(
        evidence, subject=subject, transition="on",
        requested_boundary=boundary, lookback_seconds=30,
    )
    # Strict matched commands are independent of longer preceding clues.
    direct = graph.get("directCommand") or {}
    hypotheses: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = [
        {"kind": "reported_switch_on", "subject": subject, "time": boundary,
         "confidence": "verified-observation"},
    ]
    if direct:
        hypotheses.append({
            "kind": "aligned_hubitat_command", "status": "recorded-command",
            "causation": "not-proven-by-command-alone",
            "producer": (direct.get("producer") or {}).get("label"),
        })
    if clue_rows:
        clue = clue_rows[0]
        facts.append({
            "kind": "preceding_hubitat_command",
            "producer": clue.get("producer", {}).get("label"),
            "producerId": clue.get("producer", {}).get("id"),
            "command": clue.get("command"),
            "time": clue.get("commandTime"),
            "delaySeconds": clue.get("delaySeconds"),
            "confidence": "verified-command-invocation-not-delivery",
        })
        hypotheses.append({
            "kind": "prior_hubitat_command_effect",
            "rank": "leading-recorded-candidate",
            "status": "plausible-unverified",
            "why": "Targeted command recorded before observed switch boundary",
            "missing": "transport acknowledgement or source-side execution corroboration",
        })
    boundary_at = _time(boundary)
    earliest = _time(clue_rows[0].get("commandTime")) if clue_rows else None
    intervening = [
        event for event in _event_rows(evidence, subject)
        if earliest is not None and earliest < _time(event["date"]) < boundary_at
    ]
    if intervening:
        facts.append({
            "kind": "intervening_state_changes",
            "events": intervening[:8],
            "interpretation": "Sequence anomaly; does not prove external initiation",
        })
        hypotheses.append({
            "kind": "state_resynchronisation_or_independent_action",
            "status": "plausible-not-proven",
            "why": "Observed state change between preceding command and focal state",
        })
    # Always retain bridge-side possibility without treating a bridge report
    # as evidence of a Hue-app or physical controller command.
    hypotheses.append({
        "kind": "independent_bridge_or_physical_input",
        "status": "not-established",
        "why": "Requires bridge-side controller/command evidence",
    })
    missing = []
    if clue_rows and not (graph.get("configuration") or {}).get("checked"):
        missing.append("Inspect command producer app configuration and upstream input")
    if clue_rows:
        missing.append("Check source-side command/MQTT provenance and delivery at command timestamp")
    if intervening:
        missing.append("Explain intervening state reports and compare typical command response timing")
    if not (graph.get("executionLogs") or {}).get("checked"):
        missing.append("Check available bounded producer execution logs; if expired say unavailable")
    return {
        "schema": "homebrain-skill-investigation/v1",
        "subject": subject,
        "focusTime": boundary,
        "status": "source-ranked-hypotheses-not-causal-proof",
        "facts": facts,
        "hypotheses": hypotheses,
        "nextEvidence": missing[:4],
        "provenanceRules": {
            "reportedByIsNotInitiatedBy": True,
            "eventListenersAreDownstream": True,
            "boundedNoEventsNotExhaustive": True,
            "sourceAgeMayPreventHistoricalVerification": True,
        },
    }


def render_skill_investigation(
    evidence: list[dict[str, Any]], user_request: str,
) -> str | None:
    projection = build_skill_investigation(evidence, user_request)
    if projection is None:
        return None
    return (
        "HOST INVESTIGATION SKILL EVIDENCE (typed, read-only; not a cause verdict):\n"
        + json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
        + "\nUse these ranked hypotheses as a working plan. A leading recorded "
          "command can be the strongest candidate even if its causal delivery "
          "is unverified. Investigate the counterevidence; do not promote bridge "
          "reporting to proof of an external initiator."
    )


__all__ = ["build_skill_investigation", "render_skill_investigation"]
