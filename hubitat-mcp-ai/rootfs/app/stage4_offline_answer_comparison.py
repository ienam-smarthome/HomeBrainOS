"""Stage 4D offline paired-answer evaluation, never an answer publisher.

Compare an existing HomeBrain answer with a Stage 4A model-authored draft
over the SAME evidence packet. Typed citation validity, Stage 4B reviewer
concordance, and independently supplied quality preferences are three
SEPARATE observations. No phrase-matching "hallucination detector", model
call, tool execution, file/network IO, or production-path integration.

Private answer text and source facts are processed only in memory and never
returned; reports contain fixed-key aggregate counts only. Supplied human
ratings or review votes are NOT independently authenticated as genuine.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence
import re

from stage4_narrative_contract import validate_stage4_model_draft
from stage4_semantic_sufficiency import (
    _DOMAINS, assess_stage4_semantic_sufficiency,
)

_MAX_PAIRS = 12
_MAX_BASELINE_CHARACTERS = 12000
_MAX_FACTS = 80
_SAFE_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_ORIGINS = frozenset(("constructed-fixture", "owner-labelled-redacted"))
_RATING_ORIGINS = frozenset(("constructed-reference", "owner-labelled-offline"))
_DIMENSIONS = (
    "factual_fidelity", "question_coverage", "causal_calibration",
    "clarity", "actionability",
)
_PREFERENCES = frozenset(("candidate", "baseline", "tie", "unresolved"))
_METRIC_KEYS = ("candidate", "baseline", "tie", "unresolved")


def _check_case(case: Any, seen: set[str]) -> None:
    """Reject unbounded/ambiguous input before evaluating any pair."""
    if not isinstance(case, Mapping):
        raise ValueError("case must be a mapping")
    name = case.get("case_id")
    if (not isinstance(name, str) or not _SAFE_CASE_ID.fullmatch(name)
            or name in seen):
        raise ValueError("case IDs must be unique, non-private and bounded")
    seen.add(name)
    domain = case.get("domain")
    if not isinstance(domain, str) or domain not in _DOMAINS:
        raise ValueError("invalid allowlisted domain")
    if case.get("trace_origin") not in _ORIGINS:
        raise ValueError("missing or unsupported case provenance label")
    baseline = case.get("baseline_answer")
    if (not isinstance(baseline, str) or not baseline.strip()
            or len(baseline) > _MAX_BASELINE_CHARACTERS):
        raise ValueError("invalid or over-limit baseline answer")
    packet = case.get("packet")
    if (not isinstance(packet, Mapping)
            or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"
            or packet.get("shadow_only") is not True
            or packet.get("is_publisher_input_not_publication") is not True
            or packet.get("physical_acknowledgement_proven") is not False
            or packet.get("upstream_root_cause_proven") is not False
            or packet.get("claims_about_absence_authorised") is not False
            or not isinstance(packet.get("facts"), list)
            or len(packet["facts"]) > _MAX_FACTS):
        raise ValueError("not a bounded, shadow-only Stage 4A evidence packet")
    if not isinstance(case.get("candidate_draft"), Mapping):
        raise ValueError("candidate must be a Stage 4A model draft")
    assessments = case.get("pair_assessment")
    if assessments is not None:
        if (not isinstance(assessments, Mapping)
                or set(assessments) != {"origin", "ratings"}
                or assessments.get("origin") not in _RATING_ORIGINS
                or not isinstance(assessments.get("ratings"), Mapping)
                or set(assessments["ratings"]) != set(_DIMENSIONS)
                or any(not isinstance(x, str) or x not in _PREFERENCES
                       for x in assessments["ratings"].values())):
            raise ValueError("pair ratings need fixed dimensions and provenance")
    # Reviewer vote structure is validated by Stage 4B only. Never silently
    # convert an absent reviewer into a positive score.


def compare_stage4d_offline_answers(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Produce only bounded aggregate comparisons, leaving baseline unchanged.

    Pair labels must be authored *after* both actual answers exist. This
    function cannot verify that timing or rater independence; report always
    states both limits. A reviewer vote of entailed is NOT a truth oracle.
    """
    if not isinstance(cases, (list, tuple)) or not 1 <= len(cases) <= _MAX_PAIRS:
        raise ValueError("cases must contain 1-12 in-memory pairs")
    seen: set[str] = set()
    for case in cases:
        _check_case(case, seen)
    counts: Counter[str] = Counter()
    ratings: dict[str, Counter[str]] = {
        dimension: Counter() for dimension in _DIMENSIONS
    }
    ratings_origin = Counter()
    for case in cases:
        verdict = validate_stage4_model_draft(
            case["candidate_draft"], case["packet"]
        )
        if verdict["structured_claims_valid"]:
            counts["typed_valid"] += 1
        else:
            counts["typed_invalid"] += 1
        review = assess_stage4_semantic_sufficiency(
            case["candidate_draft"], case["packet"],
            reviewer_envelopes=case.get("reviewer_envelopes"),
        )
        if (review["fully_reviewed_sentences"] > 0
                and review["fully_reviewed_sentences"] == review["sentence_count"]):
            counts["completed_review_sets"] += 1
            counts["reviewed_sentences"] += review["sentence_count"]
            counts["reviewer_concordant_entailed"] += (
                review["reviewers_concordant_entailment_count"])
            counts["reviewer_disagreements"] += review["reviewers_disagreed_count"]
            counts["reviewers_rejected"] += review["not_entailed_count"]
            if review["all_reviewers_propose_entailed"]:
                counts["unanimous_reviewer_proposals"] += 1
        else:
            counts["incomplete_or_unavailable_review_sets"] += 1
        if (case["packet"].get("facts_omitted", 0)
                or case["packet"].get("receipts_omitted", 0)):
            counts["partial_source_packets"] += 1
        assessment = case.get("pair_assessment")
        if assessment is None:
            counts["pairs_without_independent_labels"] += 1
        else:
            counts["pairs_with_supplied_labels"] += 1
            ratings_origin[assessment["origin"]] += 1
            for dimension in _DIMENSIONS:
                ratings[dimension][assessment["ratings"][dimension]] += 1

    return {
        "schema": "homebrain-stage4d-offline-answer-comparison.v1",
        "offline_only": True,
        "pair_count": len(cases),
        "candidate_typed_claims_valid_pairs": counts["typed_valid"],
        "candidate_typed_claims_invalid_pairs": counts["typed_invalid"],
        "candidate_complete_review_pairs": counts["completed_review_sets"],
        "candidate_incomplete_review_pairs": counts[
            "incomplete_or_unavailable_review_sets"],
        "candidate_reviewed_sentences": counts["reviewed_sentences"],
        "candidate_concordant_entailed_sentences":
            counts["reviewer_concordant_entailed"],
        "candidate_disputed_sentences": counts["reviewer_disagreements"],
        "candidate_rejected_sentences": counts["reviewers_rejected"],
        "candidate_unanimous_reviewer_proposal_pairs":
            counts["unanimous_reviewer_proposals"],
        "evidence_packets_with_known_omissions": counts["partial_source_packets"],
        "pair_quality_labels_supplied": counts["pairs_with_supplied_labels"],
        "pairs_quality_unscored": counts["pairs_without_independent_labels"],
        "label_provenance": {
            "constructed_reference": ratings_origin["constructed-reference"],
            "owner_labelled_offline": ratings_origin["owner-labelled-offline"],
        },
        "quality_dimensions": {
            name: {label: ratings[name][label] for label in _METRIC_KEYS}
            for name in _DIMENSIONS
        },
        "model_answer_semantically_proven": False,
        "quality_labels_independently_authenticated": False,
        "rater_independence_or_blinding_verified": False,
        "existing_answer_factually_verified": False,
        "reviewer_concordance_is_not_truth": True,
        "winner_selected": False,
        "publisher_replacement_authorised": False,
        "production_answer_changed": False,
        "mcp_or_device_actions_executed": False,
        "private_answer_text_or_source_ids_exported": False,
    }


__all__ = ["compare_stage4d_offline_answers"]
