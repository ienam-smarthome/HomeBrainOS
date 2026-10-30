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


def cross_source_discovery_checkpoint(
    receipts: Sequence[Mapping[str, Any]], question: str,
) -> str | None:
    """Describe one unchecked, discriminating source after journal recovery."""
    facts = collect_unified_evidence(receipts, question)
    if not facts or not (facts.get("journal_source_observations")
                         or facts.get("archived_input_source_observations")):
        return None
    source_choices = build_source_feasibility_choices(facts, receipts)
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
        + " Use the sourceFeasibility packet to avoid checked/duplicated "
          "reads and select only a concrete new source that could answer an "
          "open discriminator. Candidate leaf tools are ADVISORY: verify "
          "against your currently authorized READ tool catalog before "
          "calling anything. A checked-empty history is not evidence that "
          "no historic command existed. If no meaningful source is available, "
          "stop with the exact missing upstream execution evidence. "
          "Do not invent IDs, external initiation or a new tool name, "
          "assert complete history or modify devices."
    )


__all__ = ["cross_source_discovery_checkpoint"]
