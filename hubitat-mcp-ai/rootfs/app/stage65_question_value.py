"""Stage 6.5 model-authored question coverage and value-of-information ledger.

This is *not* an oracle: models author all question statuses and source ranks,
the host checks structural completeness, consistency and exact unread IDs.
Gold relevance remains separate in Stage 6 source-recall scoring. No ranking
may be used by the host to substitute another source for the model's choice.
"""
from __future__ import annotations

import re
from typing import Any

_ALLOWED_GAINS = {"none": 0, "context": 1, "material": 2}
_ALLOWED_STATUSES = {"unresolved", "addressed", "unverifiable"}


def evaluate_question_value_ledger(
    plan: dict[str, Any], remaining: set[str]
) -> tuple[list[str], dict[str, Any]]:
    """Return safe static issue codes and non-authoritative quality metadata.

    Essential READ/STOP controls are validated by the Stage 6 caller first.
    Any malformed optional ledger remains an UNVERIFIED benchmark outcome.
    Explicit STOP/material contradictions are returned as a distinct
    disallowing issue. Never hallucinate missing entries or gold labels.
    """
    issues: set[str] = set()
    questions = plan.get("questions")
    question_ids: set[str] = set()
    question_reviews = []
    if not isinstance(questions, list) or not 1 <= len(questions) <= 4:
        issues.add("questions_missing_or_invalid")
    else:
        for row in questions:
            if (not isinstance(row, dict)
                    or set(row) != {"id", "text", "status"}
                    or type(row["id"]) is not str
                    or not re.fullmatch(r"Q[1-4]", row["id"])
                    or row["id"] in question_ids
                    or type(row["text"]) is not str
                    or not 10 <= len(row["text"].strip()) <= 180
                    or row["status"] not in _ALLOWED_STATUSES):
                issues.add("questions_missing_or_invalid")
                break
            question_ids.add(row["id"])
            question_reviews.append({
                "id": row["id"], "question": row["text"], "status": row["status"],
            })
    if "questions_missing_or_invalid" in issues:
        question_ids = set()
        question_reviews = []

    evaluations = plan.get("source_evaluations")
    source_reviews = []
    seen: set[str] = set()
    valid_ranks: dict[str, int] = {}
    if not isinstance(evaluations, list) or len(evaluations) != len(remaining):
        issues.add("source_review_coverage_incomplete")
    if isinstance(evaluations, list) and len(evaluations) <= 25:
        for row in evaluations:
            if (not isinstance(row, dict)
                    or set(row) != {"source_id", "question_ids", "gain", "why"}
                    or type(row["source_id"]) is not str
                    or row["source_id"] not in remaining
                    or row["source_id"] in seen
                    or type(row["gain"]) is not str
                    or row["gain"] not in _ALLOWED_GAINS
                    or type(row["question_ids"]) is not list
                    or len(row["question_ids"]) > 4
                    or any(type(q) is not str or q not in question_ids
                           for q in row["question_ids"])
                    or len(row["question_ids"]) != len(set(row["question_ids"]))
                    or type(row["why"]) is not str
                    or not 8 <= len(row["why"].strip()) <= 220):
                issues.add("source_review_invalid")
                continue
            seen.add(row["source_id"])
            valid_ranks[row["source_id"]] = _ALLOWED_GAINS[row["gain"]]
            source_reviews.append({
                "source_id": row["source_id"],
                "gain": row["gain"],
                "question_ids": row["question_ids"],
                "reason": row["why"],
            })
    else:
        issues.add("source_review_invalid")
    if seen != remaining:
        issues.add("source_review_coverage_incomplete")

    action = plan["action"]
    chosen = plan["source_id"]
    # Reject an explicit STOP when ANY safely parsed entry admits the
    # existence of an unread *material* source, including partial ledgers.
    stop_conflict = action == "stop" and (
        any(value == 2 for value in valid_ranks.values())
        or (isinstance(evaluations, list) and any(
            isinstance(item, dict)
            and type(item.get("source_id")) is str
            and item.get("source_id") in remaining
            and item.get("gain") == "material"
            for item in evaluations))
    )
    if stop_conflict:
        issues.add("self_contradictory_stop")
    max_gain = max(valid_ranks.values(), default=None)
    selected_gain = valid_ranks.get(chosen)
    ranking_consistent = None
    if action == "read" and selected_gain is not None and max_gain is not None:
        ranking_consistent = selected_gain == max_gain and selected_gain > 0
        if not ranking_consistent:
            issues.add("selected_source_below_model_rank")
    if action == "stop" and max_gain is not None:
        ranking_consistent = max_gain < 2
    unresolved = sum(
        row["status"] == "unresolved" for row in question_reviews)
    return sorted(issues), {
        "model_questions": question_reviews,
        "model_unresolved_questions": unresolved,
        "model_source_ranks": source_reviews,
        "model_selected_source_rank": (
            next((row["gain"] for row in source_reviews
                  if row["source_id"] == chosen), None)
            if action == "read" else None),
        "model_ranking_consistent": ranking_consistent,
        "source_rankings_model_authored_not_verified": True,
        "source_utility_oracle_used_for_control": False,
    }


__all__ = ["evaluate_question_value_ledger"]
