"""Stage 6.6 safe final-answer validation diagnostics.

The category comes only from *our own* fixed validator error strings, never
raw model content or provider responses. Failed authored prose is NOT published.
Preserves only bounded fictional source IDs and independently held synthetic
source scores so a paid multi-step test isn't wholly opaque after step 4.
"""
from __future__ import annotations

import json
from typing import Any

from cloud_benchmark import BenchmarkError

# These are the exact static messages emitted by _json_object and
# _validate_answer, deliberately not passed through to the public API.
_CODES = {
    "missing or excessive response": "empty_or_oversize_model_answer",
    "invalid JSON fence": "malformed_json_fence",
    "JSON object required": "json_top_level_not_object",
    "invalid answer structure": "answer_schema_or_top_level_fields",
    "invalid sentence count": "sentence_count_out_of_bounds",
    "sentence/claim alignment required": "sentence_fields_do_not_match_contract",
    "invalid sentence text": "sentence_text_invalid_or_too_long",
    "unsupported or unknown sentence citation": "unknown_or_malformed_evidence_citation",
    "missing or excessive atomic evidence assertions": "atomic_assertion_count_invalid",  # historical
    "invalid atomic assertion list": "atomic_assertion_list_not_array",
    "excessive atomic evidence assertions": "atomic_assertion_count_exceeds_limit",
    "invalid or uncited atomic assertion": "atomic_assertion_field_or_value_invalid",
    "duplicate atomic assertion": "duplicate_atomic_assertion",
    "response too long": "total_answer_too_long",
    "uncertainty required": "uncertainty_fields_invalid",
    "specific useful follow-up required": "next_evidence_field_invalid",
}


def answer_failure_category(exc: BaseException) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "model_answer_not_valid_json"
    # Static allow-list only: unexpected exception messages may contain
    # private content and must not be returned.
    if isinstance(exc, ValueError):
        return _CODES.get(str(exc), "unclassified_answer_validation_failure")
    if isinstance(exc, (TypeError, KeyError, IndexError, AttributeError)):
        return "malformed_nested_answer_structure"
    return "unclassified_answer_validation_failure"


class Stage6AnswerContractFailure(BenchmarkError):
    """Safe structured diagnostic for invalid final model JSON, no retry."""

    def __init__(self, *, category: str, progress: dict[str, Any]):
        self.category = category
        self.progress = progress
        super().__init__(
            502,
            f"Stage 6 independent explanation failed: {category}. "
            "The rejected answer was not published. No retry was attempted."
        )


def synthetic_planning_progress(
    case: dict[str, Any],
    selected: list[str],
    plan_reviews: list[dict],
    planning_issues: list[str],
    attempts_used: int,
) -> dict[str, Any]:
    """Exclude all authored prose, private auth, raw model replies and claims.

    Reference source labels are used solely for *post-run* synthetic
    evaluation, never to choose model reads or build follow-up prompts.
    """
    expected = set(case["gold_sources"])
    ids = tuple(selected[:3])
    relevant = len(expected.intersection(ids))
    return {
        "phase_completed": "model_evidence_selection",
        "final_answer_rejected": True,
        "model_answer_published": False,
        "attempted_cloud_requests": max(0, min(4, int(attempts_used))),
        "selected_source_ids": list(ids),
        "relevant_reference_sources_selected": relevant,
        "relevant_reference_sources_available": len(expected),
        "irrelevant_sources_selected": len(set(ids) - expected),
        "planning_rounds": min(3, len(plan_reviews)),
        "planning_contract_complete": (
            bool(plan_reviews) and not planning_issues and
            all(row.get("source_value_coverage_complete") is True
                for row in plan_reviews)
        ),
        "planning_contract_issue_codes": sorted(
            {issue for issue in planning_issues
             if isinstance(issue, str) and len(issue) <= 80}
        )[:15],
        "model_ranking_consistency_failures": sum(
            row.get("question_value_review", {}).get("model_ranking_consistent") is False
            for row in plan_reviews
        ),
        "source_relevance_is_synthetic_post_run_scoring_only": True,
        "prose_semantics_verified": False,
        "publisher_approval": False,
        "no_live_hub_or_device_calls": True,
    }


__all__ = [
    "Stage6AnswerContractFailure", "answer_failure_category",
    "synthetic_planning_progress",
]
