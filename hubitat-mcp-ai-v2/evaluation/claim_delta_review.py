"""Validate private, manually graded frozen-replay stage deltas; no model or MCP.

The browser's AI Evaluation tab creates PRIVATE-homebrain-v2-reviewed.json.
This offline checker can independently validate those exports and print only
aggregate scores and human-labelled claim-change counts (never source prose).

Usage: python hubitat-mcp-ai-v2/evaluation/claim_delta_review.py private1.json [private2.json ...]
Do not commit source captures or reviewed exports.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "homebrain-v2-manual-claim-delta.v1"
STAGES = ("single_answer", "source_review", "source_review_and_audit")
CRITERIA = ("factual_grounding", "source_completeness",
            "causal_calibration", "usefulness")
KINDS = frozenset(("unsupported_introduced", "unsupported_corrected",
                   "supported_fact_lost", "supported_fact_recovered",
                   "source_scope_changed", "neutral_wording"))
TRANSITIONS = ("source_review", "final_audit")
ROLES = frozenset(("fresh_case", "regression_control", "unspecified"))
MAX_FILE_BYTES = 3 * 1024 * 1024


class ClaimDeltaError(ValueError):
    pass


def _score(raw: object) -> tuple[int, int]:
    if not isinstance(raw, dict) or set(raw) != set(CRITERIA):
        raise ClaimDeltaError("Four manual criteria required per stage")
    if any((type(val) is not int or val not in (0, 1, 2))
           for key, val in raw.items()
           if not (key == "causal_calibration" and val is None)):
        raise ClaimDeltaError("Scores must be 0/1/2, with causal N/A only")
    applicable = [v for v in raw.values() if v is not None]
    return sum(applicable), 2 * len(applicable)


def validate(document: object) -> dict:
    """Validate *human-provided* claims; no attempt to adjudicate their truth."""
    if not isinstance(document, dict):
        raise ClaimDeltaError("Expected private evaluated JSON object")
    result = document.get("result")
    review = document.get("manual_review")
    if not isinstance(result, dict) or not isinstance(review, dict):
        raise ClaimDeltaError("Both frozen model results and human review are required")
    if (review.get("schema") != SCHEMA
            or review.get("evidence_sha256") != result.get("evidence_sha256")):
        raise ClaimDeltaError("Review must match this frozen evidence fingerprint")
    evidence_hash = result.get("evidence_sha256")
    if (not isinstance(evidence_hash, str) or len(evidence_hash) != 64
            or any(c not in "0123456789abcdef" for c in evidence_hash)):
        raise ClaimDeltaError("Invalid frozen receipt hash")
    if review.get("case_role") not in ROLES:
        raise ClaimDeltaError("Case role must be stated")
    if (result.get("mcp_calls_executed") != 0
            or result.get("hubitat_writes_executed") != 0
            or result.get("model_rounds") != 3):
        raise ClaimDeltaError("Only completed read-only, tool-free 3-stage replays")

    stages = result.get("stages")
    if (not isinstance(stages, list) or len(stages) != 3
            or [s.get("stage") if isinstance(s, dict) else None
                for s in stages] != list(STAGES)):
        raise ClaimDeltaError("Expected original, review, final audit stages")
    times = [s.get("cumulative_elapsed_ms") for s in stages]
    if any(type(t) not in (int, float) or t < 0 for t in times):
        raise ClaimDeltaError("Cumulative model times required")
    if not times[0] <= times[1] <= times[2]:
        raise ClaimDeltaError("Cumulative model times must be monotonic")

    raw_scores = review.get("stage_scores")
    if not isinstance(raw_scores, dict) or set(raw_scores) != set(STAGES):
        raise ClaimDeltaError("All three answers require manual scores")
    totals = {stage: _score(raw_scores[stage]) for stage in STAGES}
    if len({v[1] for v in totals.values()}) != 1:
        raise ClaimDeltaError("The same applicable criteria required at each stage")

    changes = review.get("claim_changes")
    if not isinstance(changes, list) or len(changes) > 32:
        raise ClaimDeltaError("Expected 0-32 manually reviewed claim changes")
    kinds = {transition: {kind: 0 for kind in KINDS} for transition in TRANSITIONS}
    for item in changes:
        if not isinstance(item, dict):
            raise ClaimDeltaError("Invalid claim change")
        transition, kind = item.get("transition"), item.get("kind")
        if transition not in TRANSITIONS or kind not in KINDS:
            raise ClaimDeltaError("Unrecognized claim delta classification")
        if (not isinstance(item.get("claim"), str)
                or not 5 <= len(item["claim"].strip()) <= 500
                or not isinstance(item.get("receipt_reference"), str)
                or not 3 <= len(item["receipt_reference"].strip()) <= 500):
            raise ClaimDeltaError("Each claim requires text and a source pointer")
        kinds[transition][kind] += 1

    full_max = totals[STAGES[0]][1]
    return {
        "evidence_sha256": evidence_hash,
        "case_role": review["case_role"],
        "score_total_by_stage": {
            name: {"score": totals[name][0], "max": totals[name][1]}
            for name in STAGES
        },
        "delta_review_vs_initial": totals[STAGES[1]][0] - totals[STAGES[0]][0],
        "delta_final_vs_review": totals[STAGES[2]][0] - totals[STAGES[1]][0],
        "delta_final_vs_initial": totals[STAGES[2]][0] - totals[STAGES[0]][0],
        "additional_review_ms": times[2] - times[0],
        "claim_change_counts": kinds,
        "claim_change_records": len(changes),
        "claim_change_completeness": (
            "annotated" if changes else "not assessed; empty is not proof of no changes"
        ),
        "max_score": full_max,
        "note": (
            "Scores and claim labels were supplied by a human reviewer. "
            "They have NOT been machine-checked against private source receipts, "
            "and stage comparison does not measure end-to-end source discovery."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", nargs="+", type=Path)
    args = parser.parse_args()
    summaries = []
    seen_hashes = set()
    try:
        for file in args.exports:
            if not file.is_file() or not 0 < file.stat().st_size <= MAX_FILE_BYTES:
                raise ClaimDeltaError("Missing or oversized private review file")
            summary = validate(json.loads(file.read_text(encoding="utf-8")))
            if summary["evidence_sha256"] in seen_hashes:
                raise ClaimDeltaError("Duplicate evidence bundle; not independent case")
            seen_hashes.add(summary["evidence_sha256"])
            summaries.append(summary)
    except (ClaimDeltaError, OSError, ValueError, TypeError):
        parser.exit(2, "Invalid private claim-delta review; no source data displayed.\n")
    print(json.dumps({"schema": SCHEMA, "count": len(summaries),
                      "fresh_count": sum(x["case_role"] == "fresh_case"
                                         for x in summaries),
                      "regression_count": sum(x["case_role"] == "regression_control"
                                              for x in summaries),
                      "results": summaries}, indent=2))


if __name__ == "__main__":
    main()
