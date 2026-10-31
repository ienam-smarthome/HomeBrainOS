"""Stage 4H: independent-reference scoring of complete, offline investigation answers.

A full answer can contain true cited sentences AND an invented cause,
or it can be factually cautious but omit the evidence necessary to answer
the question. Stage 4H keeps three independent measurements:
  1. host-owned cited source IDs and expected fact coverage;
  2. two model reviewer judgments for EVERY complete sentence;
  3. separately authored, fixed reference labels (never sent to models).

These are CURATED CONSTRUCTED answers, not independently adjudicated real
model-authored prose. Reviewer concordance is not independent truth.
No production answer publication, MCP calls, networking or private output.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Callable, Mapping, Sequence

from stage4_full_answer_evaluation import validate_stage4g_proposal
from stage4_semantic_sufficiency import build_stage4_semantic_review_request, _review_votes

_REVIEWERS = ("qwen2.5:3b", "llama3.2:3b")
_MAX_CASES = 8
_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_DOMAINS = frozenset(("lighting", "heating", "ventilation", "history"))
_ANSWER_LABELS = frozenset(("adequate", "unsupported", "incomplete"))
_SENTENCE_LABELS = frozenset(("entailed", "not-entailed"))


def _validate_case(case: Any, seen: set[str]) -> dict[str, Any]:
    if not isinstance(case, Mapping) or set(case) != {
        "case_id", "domain", "question", "packet", "proposal",
        "required_fact_ids", "sentence_oracle", "answer_oracle",
    }:
        raise ValueError("invalid reference case")
    ident = case["case_id"]
    if not isinstance(ident, str) or not _ID_RE.fullmatch(ident) or ident in seen:
        raise ValueError("unsafe or duplicate reference ID")
    seen.add(ident)
    if case["domain"] not in _DOMAINS or not isinstance(case["question"], str):
        raise ValueError("unsupported reference domain")
    if not 1 <= len(case["question"]) <= 240:
        raise ValueError("invalid reference question")
    packet = case["packet"]
    if (not isinstance(packet, Mapping)
            or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"
            or packet.get("shadow_only") is not True
            or packet.get("is_publisher_input_not_publication") is not True
            or packet.get("upstream_root_cause_proven") is not False
            or packet.get("physical_acknowledgement_proven") is not False
            or packet.get("claims_about_absence_authorised") is not False
            or not isinstance(packet.get("facts"), list)
            or not 1 <= len(packet["facts"]) <= 8):
        raise ValueError("invalid source packet")
    required = case["required_fact_ids"]
    if (not isinstance(required, list) or not 1 <= len(required) <= 3
            or len(required) != len(set(str(v) for v in required))):
        raise ValueError("invalid independent expected source IDs")
    facts = {f.get("fact_id") for f in packet["facts"] if isinstance(f, Mapping)}
    if any(not isinstance(fid, str) or fid not in facts for fid in required):
        raise ValueError("expected source ID absent from packet")
    proposal = validate_stage4g_proposal(case["proposal"], packet)
    if proposal is None:
        raise ValueError("not a source-valid complete answer")
    rows = proposal["sections"][0]["sentences"]
    labels = case["sentence_oracle"]
    label = case["answer_oracle"]
    if (not isinstance(labels, list) or len(labels) != len(rows)
            or any(v not in _SENTENCE_LABELS for v in labels)
            or label not in _ANSWER_LABELS):
        raise ValueError("invalid independent reference labels")
    cited = {fid for row in rows for fid in row["citations"]}
    covers_all = set(required).issubset(cited)
    if (label == "adequate" and (not covers_all or "not-entailed" in labels)
            or label == "unsupported" and "not-entailed" not in labels
            or label == "incomplete" and (covers_all or "not-entailed" in labels)):
        raise ValueError("reference labels contradict source coverage/entailment")
    return proposal


def evaluate_stage4h_full_answer_references(
    cases: Sequence[Mapping[str, Any]],
    *,
    reviewer_models: Sequence[str],
    invoke: Callable[[str, Mapping[str, Any]], Any],
) -> dict[str, Any]:
    """Evaluate host-labelled FULL answers with actual caller-supplied reviewers.

    The reference labels, question, ID, and whole answer are never sent as a
    reviewer job. A reviewer sees only ONE sentence and its selected facts.
    Complete-answer quality remains a separately held reference judgment.
    """
    if (not isinstance(cases, (list, tuple)) or len(cases) != _MAX_CASES
            or tuple(reviewer_models) != _REVIEWERS or not callable(invoke)):
        raise ValueError("exactly eight constructed cases and two local reviewers required")
    seen: set[str] = set()
    valid = [_validate_case(case, seen) for case in cases]

    totals: Counter[str] = Counter()
    model_counts: dict[str, Counter[str]] = {m: Counter() for m in _REVIEWERS}
    label_counts: Counter[str] = Counter()
    for case, draft in zip(cases, valid):
        label = case["answer_oracle"]
        label_counts[label] += 1
        needed = set(case["required_fact_ids"])
        selected = {fid for sec in draft["sections"] for row in sec["sentences"]
                    for fid in row["citations"]}
        covers = needed.issubset(selected)
        totals["reference_facts_required"] += len(needed)
        totals["reference_facts_selected"] += len(needed & selected)
        totals["answers_with_full_fact_coverage"] += int(covers)
        request = build_stage4_semantic_review_request(draft, case["packet"])
        if not request["ready"]:
            raise ValueError("source-valid drafts must be reviewer-ready")
        sentences = request["sentences"]
        separate_model_accepted = {model: True for model in _REVIEWERS}
        complete = True
        for sentence, true_label in zip(sentences, case["sentence_oracle"]):
            totals["reference_sentences"] += 1
            totals["reference_supported_sentences"] += int(true_label == "entailed")
            totals["reference_unsupported_sentences"] += int(true_label != "entailed")
            # Normalize schema-local s001 to review isolated sentences, as in
            # Stage 4G; never rewrite sentence text or its source citations.
            isolated = {**sentence, "sentence_id": "s001"}
            expected = {"s001": frozenset(isolated["cited_fact_ids"])}
            decisions: list[bool | None] = []
            for model in _REVIEWERS:
                scores = model_counts[model]
                totals["review_attempts"] += 1
                scores["attempts"] += 1
                try:
                    response = invoke(model, {
                        "task": "review",
                        "schema": "homebrain-stage4h-sentence-review.v1",
                        "sentences": [isolated],
                        "source_facts_may_be_truncated": bool(
                            case["packet"].get("facts_omitted")
                            or case["packet"].get("receipts_omitted")),
                    })
                    totals["review_responses"] += 1
                    scores["responses"] += 1
                    votes, error = _review_votes(response, expected)
                except Exception:
                    totals["review_errors"] += 1
                    scores["errors"] += 1
                    votes, error = None, "invocation-error"
                if error:
                    complete = False
                    scores["invalid"] += 1
                    decisions.append(None)
                    separate_model_accepted[model] = False
                    continue
                passed = votes["s001"] == "entailed"
                decisions.append(passed)
                scores["valid"] += 1
                scores["reference_supported"] += int(true_label == "entailed")
                scores["reference_unsupported"] += int(true_label == "not-entailed")
                scores["false_rejects"] += int(true_label == "entailed" and not passed)
                scores["false_accepts"] += int(true_label == "not-entailed" and passed)
                separate_model_accepted[model] &= passed
            if None not in decisions:
                totals["valid_review_pairs"] += 1
                both = decisions == [True, True]
                if decisions[0] != decisions[1]:
                    totals["reviewer_disagreements"] += 1
                if true_label == "entailed":
                    totals["consensus_false_rejects"] += int(not both)
                else:
                    totals["consensus_false_accepts"] += int(both)
        if not complete:
            totals["unscored_incomplete_answers"] += 1
            continue
        totals["complete_reviewed_answers"] += 1
        # Answer acceptance requires ALL sentences accepted AND coverage.
        # The answer oracle is withheld from both models and used afterward.
        for model in _REVIEWERS:
            accepted = separate_model_accepted[model] and covers
            counts = model_counts[model]
            counts["complete_answers"] += 1
            counts["adequate_accepted"] += int(label == "adequate" and accepted)
            counts["adequate_rejected"] += int(label == "adequate" and not accepted)
            counts["unsafe_accepted"] += int(label == "unsupported" and accepted)
            counts["unsafe_rejected"] += int(label == "unsupported" and not accepted)
            counts["incomplete_accepted"] += int(label == "incomplete" and accepted)
        agreed = all(separate_model_accepted.values()) and covers
        totals["adequate_answers_accepted"] += int(label == "adequate" and agreed)
        totals["adequate_answers_rejected"] += int(label == "adequate" and not agreed)
        totals["unsupported_answers_accepted"] += int(label == "unsupported" and agreed)
        totals["unsupported_answers_rejected"] += int(label == "unsupported" and not agreed)
        totals["incomplete_answers_accepted"] += int(label == "incomplete" and agreed)
    models = {}
    for model in _REVIEWERS:
        scores = model_counts[model]
        models[model] = {
            k: scores[k] for k in (
                "attempts", "responses", "errors", "invalid", "valid",
                "false_accepts", "false_rejects", "complete_answers",
                "adequate_accepted", "adequate_rejected", "unsafe_accepted",
                "unsafe_rejected", "incomplete_accepted")
        }
    return {
        "schema": "homebrain-stage4h-reference-full-answer-evaluation.v1",
        "cases": len(cases),
        "reference_adequate_answers": label_counts["adequate"],
        "reference_unsupported_answers": label_counts["unsupported"],
        "reference_incomplete_answers": label_counts["incomplete"],
        "reference_facts_required": totals["reference_facts_required"],
        "reference_facts_selected": totals["reference_facts_selected"],
        "answers_with_full_fact_coverage": totals["answers_with_full_fact_coverage"],
        "reference_sentences": totals["reference_sentences"],
        "reference_supported_sentences": totals["reference_supported_sentences"],
        "reference_unsupported_sentences": totals["reference_unsupported_sentences"],
        "review_attempts": totals["review_attempts"],
        "review_responses": totals["review_responses"],
        "review_errors": totals["review_errors"],
        "valid_review_pairs": totals["valid_review_pairs"],
        "reviewer_disagreements": totals["reviewer_disagreements"],
        "consensus_false_accepts": totals["consensus_false_accepts"],
        "consensus_false_rejects": totals["consensus_false_rejects"],
        "complete_reviewed_answers": totals["complete_reviewed_answers"],
        "unscored_incomplete_answers": totals["unscored_incomplete_answers"],
        "adequate_answers_accepted": totals["adequate_answers_accepted"],
        "adequate_answers_rejected": totals["adequate_answers_rejected"],
        "unsupported_answers_accepted": totals["unsupported_answers_accepted"],
        "unsupported_answers_rejected": totals["unsupported_answers_rejected"],
        "incomplete_answers_accepted": totals["incomplete_answers_accepted"],
        "model_metrics": models,
        "reference_labels_host_curated_not_externally_authenticated": True,
        "cases_are_pre_authored_not_generated_in_this_run": True,
        "newly_generated_stage4g_answers_independently_scored": False,
        "live_homebrain_truth_established": False,
        "real_world_explanation_quality_established": False,
        "answer_publication_permitted": False,
        "production_code_or_devices_changed": False,
    }


__all__ = ["evaluate_stage4h_full_answer_references"]
