"""Stage 7.2 benchmark-only, independent question-to-answer review obligations.

The fixed reference rubric is revealed to *a human reviewer only after*
the model's selected-source and authored-answer rounds have completed.
It is NOT added to Ollama prompts, agent routing, or the production publisher.

An exact record citation means that a source was cited; it does not establish
that the prose answers the question, states a justified causal relation, or
properly scopes negative evidence. Only an independent sentence/answer review
can judge those qualities.
"""
from __future__ import annotations

from typing import Any

# Synthetic evaluation references, not model-facing prompts or templates for
# published prose. All cases are static and the answer's semantics remain
# independently *unrated* until an explicit human review.
_REFERENCE_OBLIGATIONS: dict[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    "clock_conflict": (
        ("report_order", "critical",
         "Explain the inversion between device-source event order and collector receipt order; do not equate receipt order with physical sequence.",
         ("E2", "E3")),
        ("command_history", "critical",
         "Account for the app brightness command and distinguish a recorded command from independent proof that the lamp physically changed state.",
         ("E1",)),
        ("causal_answer", "critical",
         "Answer whether the light really turned OFF after ON: source timestamps suggest the earlier OFF report predates ON, but a physical event sequence and clock accuracy are not independently proven.",
         ("I1", "E2", "E3")),
    ),
    "competing_commands": (
        ("opposing_issuers", "critical",
         "Identify both issuing applications, their different commands and the observed time order.",
         ("E1", "E2")),
        ("reported_outcome", "supporting",
         "Distinguish the reported OFF state from command acknowledgement or proven actuator operation.",
         ("I1",)),
        ("causal_answer", "critical",
         "Explicitly answer whether the OFF report identifies which application caused it: the supplied observations do not establish a unique responsible command.",
         ("I1", "E1", "E2", "E3")),
        ("negative_scope", "critical",
         "Limit any missing-acknowledgement claim to the examined evidence; do not claim a command never executed or that acknowledgements cannot exist elsewhere.",
         ("E1", "E2", "E3")),
    ),
    "stale_connectivity": (
        ("reported_offline", "supporting",
         "Identify the reported offline state and its watchdog reporting basis; do not mistake it for a device-origin timestamp.",
         ("I1",)),
        ("broker_vs_device", "critical",
         "Differentiate the MQTT driver's broker connection from independent confirmation that the physical plug is online.",
         ("E1",)),
        ("last_genuine_packet", "critical",
         "Establish the last independently sourced plug telemetry separately from watchdog activity and the broker session.",
         ("E2",)),
        ("causal_answer", "critical",
         "Explain that proximity of the scheduled OFF command to the last contact does not establish why the plug went offline.",
         ("E2", "E3", "I1")),
    ),
}


def build_answer_coverage_review(
    case_id: str, case: dict[str, Any],
    selected: list[str], draft: dict[str, Any],
) -> dict[str, Any]:
    """Preserve independent after-the-fact obligations, never certify prose."""
    if case_id not in _REFERENCE_OBLIGATIONS:
        raise ValueError("unknown synthetic review scenario")
    if type(case) is not dict or type(selected) is not list or type(draft) is not dict:
        raise ValueError("invalid review packet inputs")
    sources = case["catalog"]
    known_ids = {s["id"] for s in sources}
    if (len(known_ids) != len(sources)
            or len(selected) > 3 or len(selected) != len(set(selected))
            or any(type(s) is not str or s not in known_ids for s in selected)):
        raise ValueError("invalid selected synthetic source IDs")
    initial = case["initial"]
    source_map = {
        s["id"]: {r["id"] for r in s["records"]}
        for s in sources
    }
    all_records = {initial["id"]}
    for source_records in source_map.values():
        all_records.update(source_records)
    inspected_records = {initial["id"]}
    for sid in selected:
        inspected_records.update(source_map[sid])
    sentences = draft["sentences"]
    cited = set()
    for sentence in sentences:
        cited.update(sentence["evidence_ids"])
    if not cited <= inspected_records:
        raise ValueError("answer cites unseen source records")
    obligations = []
    for obligation_id, importance, expectation, references in _REFERENCE_OBLIGATIONS[case_id]:
        if not set(references) <= all_records:
            raise ValueError("synthetic rubric refers to missing fixture record")
        obligations.append({
            "id": obligation_id,
            "importance": importance,
            "independent_reviewer_question": expectation,
            "reference_evidence_record_ids": list(references),
            "reference_records_available_to_model": sorted(
                set(references) & inspected_records),
            "reference_records_not_examined_by_model": sorted(
                set(references) - inspected_records),
            "reference_records_cited_by_model": sorted(
                set(references) & cited),
            "source_overlap_is_not_prose_support": True,
            "reviewer_verdict": "not_reviewed",
        })
    return {
        "schema": "homebrain-stage72-answer-coverage.v1",
        "original_question": case["question"],
        "obligations": obligations,
        "reviewer_verdict_options": [
            "addressed_with_evidence", "explicitly_unresolved",
            "omitted", "overclaimed", "unclear",
        ],
        "reference_rubric_not_sent_to_model": True,
        "reference_evidence_revealed_only_postrun": True,
        "answer_directness_verified_automatically": False,
        "full_sentence_semantics_verified_automatically": False,
        "human_review_required": True,
        "publisher_approval": False,
    }


__all__ = ["build_answer_coverage_review"]
