"""Stage 4C controlled offline evaluator for ACTUAL caller-invoked model responses.

A host-supplied synchronous model adapter can generate a candidate answer and
two separately requested semantic reviews. A local Ollama adapter is provided
only by the separate explicitly invoked CLI. Neither this module nor the CLI
is imported by the production agent or publisher.

Never pass benchmark reference labels to a model. A model-generated answer
without an independently adjudicated post-generation oracle is UNSCORED;
reviewer agreement and distinct model names are not truth/independence proofs.
No source text, device IDs, model output or input labels leave this aggregate
report.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Mapping, Sequence

from stage4_narrative_contract import (
    stage4_model_authoring_instructions,
    validate_stage4_model_draft,
)
from stage4_semantic_sufficiency import (
    _DOMAINS,
    assess_stage4_semantic_sufficiency,
    benchmark_stage4_semantic_reviews,
    build_stage4_semantic_review_request,
)

_MAX_CASES = 8
_MAX_SENTENCES = 16
_MAX_INVOCATIONS = _MAX_CASES * 3
_PROVENANCE = frozenset(("constructed-fixture", "owner-labelled-redacted"))
_MODEL_ERROR = "model-response-unavailable-or-invalid"


def _safe_model_name(model: Any) -> bool:
    return (isinstance(model, str) and 1 <= len(model) <= 80
            and all(c.isascii() and (c.isalnum() or c in "._:-")
                    for c in model)
            and "cloud" not in model.casefold())


def _input_cases(cases: Any, author_model: Any,
                 reviewer_models: Any) -> None:
    if not isinstance(cases, (list, tuple)) or not 1 <= len(cases) <= _MAX_CASES:
        raise ValueError("cases must be a bounded nonempty list")
    if (not isinstance(reviewer_models, (list, tuple))
            or len(reviewer_models) != 2
            or not all(_safe_model_name(x) for x in reviewer_models)
            or reviewer_models[0] == reviewer_models[1]):
        raise ValueError("two distinct reviewer model identifiers required")
    if author_model is not None and (
        not _safe_model_name(author_model) or author_model in reviewer_models
    ):
        raise ValueError("author must be distinct from reviewers")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("invalid case")
        ident = case.get("case_id")
        if (not isinstance(ident, str) or not 1 <= len(ident) <= 48
                or not all(x.isascii() and (x.islower() or x.isdigit()
                                            or x in "_-") for x in ident)
                or ident in seen or case.get("domain") not in _DOMAINS
                or case.get("trace_origin") not in _PROVENANCE):
            raise ValueError("invalid, duplicated or unlabelled case")
        seen.add(ident)
        packet = case.get("packet")
        if (not isinstance(packet, Mapping)
                or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"
                or packet.get("shadow_only") is not True
                or not isinstance(packet.get("facts"), list)
                or len(packet["facts"]) > 80):
            raise ValueError("invalid or unbounded evidence packet")
        if "draft" not in case and author_model is None:
            raise ValueError("missing offline draft and author model")
        if "oracle" in case:
            oracle = case["oracle"]
            if (not isinstance(oracle, list)
                    or not 1 <= len(oracle) <= _MAX_SENTENCES
                    or any(label not in ("entailed", "not-entailed")
                           for label in oracle)):
                raise ValueError("invalid independent oracle labels")
            if "draft" not in case:
                # A fresh model-authored sentence MUST be adjudicated *after*
                # generation. Never re-use an oracle from some other draft.
                raise ValueError("pre-labelled oracle cannot score generated text")


def run_stage4c_offline_model_evaluation(
    cases: Sequence[Mapping[str, Any]],
    *,
    reviewer_models: Sequence[str],
    invoke: Callable[[str, Mapping[str, Any]], Any],
    author_model: str | None = None,
) -> dict[str, Any]:
    """Run caller-provided local model calls; no network or file IO here.

    Pre-authored, independently labelled drafts support measured reference
    accuracy. For fresh model-authored drafts, only reviewer concordance and
    structural validity can be assessed, not correctness/real-world quality.

    Payloads intentionally exclude an oracle and any other case metadata.
    They contain sensitive sentence/fact data and must stay in a local
    consented inference environment. No prompt or response is returned.
    """
    _input_cases(cases, author_model, reviewer_models)
    if not callable(invoke):
        raise ValueError("explicit synchronous local model adapter required")
    counts: Counter[str] = Counter()
    reviewed_for_reference: list[dict[str, Any]] = []
    calls_attempted = 0
    for case in cases:
        packet = case["packet"]
        draft = case.get("draft")
        if draft is None:
            calls_attempted += 1
            counts["author_attempted"] += 1
            try:
                draft = invoke(author_model, {
                    "task": "author",
                    "schema": "homebrain-stage4c-author-request.v1",
                    "instructions": stage4_model_authoring_instructions(packet),
                    "packet": packet,
                })
            except Exception:
                # Not even exception strings (which may contain prompts/IDs).
                counts["model_invocation_errors"] += 1
                continue
            counts["author_responses_received"] += 1
        typed = validate_stage4_model_draft(draft, packet)
        if not typed["structured_claims_valid"]:
            counts["typed_drafts_invalid"] += 1
            continue
        counts["typed_drafts_valid"] += 1
        request = build_stage4_semantic_review_request(draft, packet)
        if not request["ready"]:
            counts["review_requests_invalid"] += 1
            continue
        envelopes = []
        for reviewer in reviewer_models:
            calls_attempted += 1
            counts["review_calls_attempted"] += 1
            try:
                response = invoke(reviewer, {
                    "task": "review",
                    "schema": "homebrain-stage4c-reviewer-request.v1",
                    "instructions": request["review_instructions"],
                    "sentences": request["sentences"],
                    "source_coverage_cannot_establish_absence": True,
                    "source_facts_may_be_truncated":
                        request["source_facts_may_be_truncated"],
                })
            except Exception:
                counts["model_invocation_errors"] += 1
                response = None
            if response is not None:
                counts["review_responses_received"] += 1
            envelopes.append(response)
        verdict = assess_stage4_semantic_sufficiency(
            draft, packet, reviewer_envelopes=envelopes,
        )
        if verdict["fully_reviewed_sentences"] != verdict["sentence_count"]:
            counts["invalid_or_incomplete_review_sets"] += 1
            continue
        counts["completed_review_sets"] += 1
        counts["sentences_reviewed"] += verdict["sentence_count"]
        counts["reviewer_concordant_entailed_sentences"] += (
            verdict["reviewers_concordant_entailment_count"])
        counts["reviewer_disagreed_sentences"] += verdict["reviewers_disagreed_count"]
        counts["reviewers_both_rejected_sentences"] += verdict["not_entailed_count"]
        if "oracle" not in case:
            counts["generated_or_unlabelled_cases_unscored"] += 1
            counts["generated_or_unlabelled_sentences_unscored"] += verdict["sentence_count"]
            continue
        if len(case["oracle"]) != verdict["sentence_count"]:
            counts["oracle_count_mismatch"] += 1
            continue
        reviewed_for_reference.append({
            "case_id": case["case_id"],
            "domain": case["domain"],
            "packet": packet,
            "draft": draft,
            "oracle": case["oracle"],
            "reviewer_envelopes": envelopes,
        })
    scores = (benchmark_stage4_semantic_reviews(reviewed_for_reference)
              if reviewed_for_reference else None)
    if calls_attempted > _MAX_INVOCATIONS:
        raise RuntimeError("model invocation budget exceeded")
    return {
        "schema": "homebrain-stage4c-offline-model-evaluation.v1",
        "case_count": len(cases),
        "call_budget": _MAX_INVOCATIONS,
        "model_invocations_attempted": calls_attempted,
        "author_invocations_attempted": counts["author_attempted"],
        "author_responses_received": counts["author_responses_received"],
        "typed_drafts_valid": counts["typed_drafts_valid"],
        "typed_drafts_invalid": counts["typed_drafts_invalid"],
        "review_calls_attempted": counts["review_calls_attempted"],
        "review_responses_received": counts["review_responses_received"],
        "completed_review_sets": counts["completed_review_sets"],
        "invalid_or_incomplete_review_sets": counts["invalid_or_incomplete_review_sets"],
        "reviewed_sentence_count": counts["sentences_reviewed"],
        "reviewer_concordant_entailed_sentences":
            counts["reviewer_concordant_entailed_sentences"],
        "reviewer_disagreed_sentences": counts["reviewer_disagreed_sentences"],
        "reviewers_both_rejected_sentences": counts["reviewers_both_rejected_sentences"],
        "generated_or_unlabelled_sentences_unscored":
            counts["generated_or_unlabelled_sentences_unscored"],
        "unscored_oracle_mismatch_cases": counts["oracle_count_mismatch"],
        "model_invocation_errors": counts["model_invocation_errors"],
        "reference_scored_cases": scores["case_count"] if scores else 0,
        "reference_scored_sentences": scores["sentence_count"] if scores else 0,
        "reference_unsupported_sentences":
            scores["reference_unsupported_sentences"] if scores else 0,
        "false_accept_count": scores["false_accept_count"] if scores else None,
        "false_reject_count": scores["false_reject_count"] if scores else None,
        "false_accept_rate": scores["false_accept_rate"] if scores else None,
        "false_reject_rate": scores["false_reject_rate"] if scores else None,
        "reference_labels_never_sent_to_models": True,
        "model_names_are_not_independence_proof": True,
        "reference_labels_user_supplied_not_authenticated": True,
        "semantic_ground_truth_independently_verified": False,
        "safe_to_publish": False,
        "author_or_reviewer_model_quality_proven": False,
        "live_homebrain_evaluation_performed": False,
        "tool_or_device_commands_executed": False,
        "production_model_or_publisher_changed": False,
    }


__all__ = ["run_stage4c_offline_model_evaluation"]
