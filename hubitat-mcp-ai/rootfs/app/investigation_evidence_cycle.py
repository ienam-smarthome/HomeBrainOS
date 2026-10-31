"""Read-choice checkpoints after cross-source evidence recovery.

The original unified MCP agent remains the only tool selector. This module
does no MCP calls, introduces no implicit device IDs and never interprets
source-timed state reports as verification of a causal initiating controller.

It turns a verified, bounded journal recovery into *new model-visible
evidence* before the model's next opportunity to choose an authorized read.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from unified_investigation_bridge import collect_unified_evidence
from causal_source_feasibility import build_source_feasibility_choices
from causal_claim_pilot import render_shadow_claim_pilot


def cross_source_discovery_checkpoint(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    """Describe one unchecked, discriminating source after journal recovery."""
    facts = collect_unified_evidence(receipts, question)
    if not facts or not (facts.get("journal_source_observations")
                         or facts.get("archived_input_source_observations")):
        return None
    source_choices = build_source_feasibility_choices(facts, receipts)
    # Explicitly elevate the strongest independently justified *next READ*
    # without routing or executing it. The model still checks live schemas.
    ranked_reads = (
        [x for x in (source_choices.get("candidate_reads") or [])
         if x.get("priority") == "evidence-ranked"]
        if isinstance(source_choices, Mapping) else []
    )
    claim_pilot = render_shadow_claim_pilot(facts)
    checked_inputs = facts.get("independently_read_input_ids") or []
    coverage = facts.get("target_coverage") or []
    recovered = [
        {"deviceId": str(row.get("device_id") or ""),
         "name": str(row.get("device_name") or "")[:90],
         "sourceTimedOn": row.get("journal_source_on", 0),
         "sourceTimedOff": row.get("journal_source_off", 0),
         "nativeOn": row.get("reported_switch_on", 0),
         "nativeOff": row.get("reported_switch_off", 0),
         "issuedOff": row.get("issued_off", 0)}
        for row in coverage
    ]
    # Strongly typed per-target evidence, not a room name heuristic or an
    # inferred automation. Journal gaps prevent negative historical proofs.
    summary = {
        "verifiedTargets": recovered[:8],
        "historicalJournalSourceTimeReports": facts["journal_source_observations"],
        "historicalJournalReceptionOnlyReports": facts["journal_collector_observations"],
        "journalGapCount": facts["journal_gap_count"],
        "archivedInputSourceReports": facts.get("archived_input_source_observations", 0),
        "archivedInputReceptionOnlyReports":
            facts.get("archived_input_collector_observations", 0),
        "archivedInputJournalGaps": facts.get("archived_input_gap_count", 0),
        "receptionOnlyInputCooccurrence":
            facts.get("archived_input_reception_patterns", [])[:6],
        "archivedInputTruncatedIds":
            facts.get("archived_input_truncated_ids", []),
        "independentInputHistoryIdsChecked": checked_inputs[:12],
        "independentInputObservations": facts.get("independent_input_observations", [])[:12],
        "inputAppRelationships": facts.get("input_app_relationships", [])[:10],
        "targetObservedCommandAppIds":
            facts.get("target_observed_command_app_ids", [])[:12],
        "eventReadsWithoutUsableRows":
            facts.get("additional_event_reads_without_usable_rows", [])[:12],
        "sourceContinuityEstablished": False,
        "upstreamInitiatorEstablished": False,
        "sourceFeasibility": source_choices,
        "highestPriorityUpstreamRead": ranked_reads[0] if ranked_reads else None,
    }
    if not checked_inputs:
        discriminator = (
            "Which independently discovered occupancy, motion, button, or "
            "controller input actually changed around these source-timed "
            "transitions? Discover a small relevant set from current "
            "source-attested room/app/device relationships, then choose "
            "their bounded incident-time histories. Prefer a verified "
            "input/controller event to another read of the same lights. "
            "A journal entry alone cannot identify who issued the command."
        )
    else:
        discriminator = (
            "The independently observed inputs are temporal correlations. "
            "Which unqueried app/rule dependencies, historical execution "
            "decisions, or original command producers can discriminate "
            "the remaining upstream causes? Prefer a source-attested "
            "controller read; do not repeat input histories. "
            "If no additional source is accessible, retain the uncertainty."
        )
    return (
        "HOST CROSS-SOURCE DISCOVERY CHECKPOINT (verified observations; "
        "NOT evidence that a cause was proven): "
        + json.dumps(summary, ensure_ascii=True, separators=(",", ":"))
        + "\nThe user asked WHY, not just for a switch-event list. "
        + discriminator
        + (" A source-qualified upstream lead is available: prefer "
           "highestPriorityUpstreamRead over repeating target histories or "
           "uncorrelated scans, unless new evidence rules it out. "
           if ranked_reads else "")
        + " Choose only available, authorized READ tools through the "
          "current model tool catalog. "
          "Use the sourceFeasibility packet to avoid checked/duplicated "
          "reads and select only a concrete new source that could answer an "
          "open discriminator. Candidate leaf tools are ADVISORY: verify "
          "against your currently authorized READ tool catalog before "
          "calling anything. A checked-empty history is not evidence that "
          "no historic command existed. If no meaningful source is available, "
          "stop with the exact missing upstream execution evidence. "
          "Do not invent sensor IDs, external initiation or a new tool name, "
          "assert complete history or modify devices."
        + claim_pilot
    )


def ranked_upstream_continuation_checkpoint(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> tuple[str, str] | None:
    """Offer one *newly feasible* evidence-ranked read in the active tool loop.

    Journal recovery can occur before a single dependency leaf has succeeded.
    The original recovery checkpoint is intentionally idempotent; the host
    must separately detect when subsequent model-chosen reads make a higher
    quality source path feasible. This function never selects or invokes tools.
    """
    facts = collect_unified_evidence(receipts, question)
    if not facts or not facts.get("journal_source_observations"):
        return None
    feasibility = build_source_feasibility_choices(facts, receipts)
    if not isinstance(feasibility, Mapping):
        return None
    ranked = next((
        row for row in feasibility.get("candidate_reads") or []
        if isinstance(row, Mapping) and row.get("priority") == "evidence-ranked"
    ), None)
    if ranked is None:
        return None
    # The concrete leaf and arguments were admitted by the source feasibility
    # module. Never construct another operation or introduce an input ID here.
    key = json.dumps(
        [ranked.get("leaf"), ranked.get("args")],
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    )
    content = (
        "HOST RANKED UPSTREAM EVIDENCE CONTINUATION (advisory, READ-only): "
        + json.dumps({
            "strongestSourceQualifiedRead": ranked,
            "evidenceRankedUpstreamLead":
                feasibility.get("evidence_ranked_upstream_lead"),
            "verifiedTargetCount": feasibility.get("verified_target_count"),
            "priorSuccessfulExactDuplicates":
                feasibility.get("successful_exact_duplicate_read_count"),
        }, ensure_ascii=True, separators=(",", ":"))[:3600]
        + "\nThis suggestion is newly feasible after current-turn evidence was "
          "read. It is a more discriminating source path than rereading the "
          "target devices or unrelated old log pages. The ORIGINAL model "
          "decides whether it is useful and verifies the leaf against its "
          "CURRENT authorized READ catalog before any call. A shared current "
          "app dependency is not proof of historical app execution, an "
          "issuing controller, source-clock sensor order or physical cause. "
          "Do not repeat previously attempted operations, invent IDs or "
          "modify anything. If the required source is inaccessible, state "
          "the precise gap and finish the investigation."
    )
    return key, content


__all__ = ["cross_source_discovery_checkpoint", "ranked_upstream_continuation_checkpoint"]
