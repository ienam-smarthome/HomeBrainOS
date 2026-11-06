#!/usr/bin/env python3
"""Q2: pair *human source-reviewed* answers against exact first-run SHA metadata.

This is an offline, metadata-only report, not an automated truth judge or
a model-call runner. The two raw answers and supporting private evidence must
be retained outside the repository and independently inspected by reviewers.
No cloud, network, Hubitat, HA or model tools are called.
"""
from __future__ import annotations

import argparse
import json
import re
from statistics import median
from pathlib import Path
from typing import Any

from answer_quality_fixed_packets import (
    SHA256_RE, ScorecardInputError, build_fixed_packets,
    pair_metadata, validate_run_manifest,
)
from answer_quality_scorecard import REVIEW_KEYS, build_scorecard, load_catalog

REVIEW_SCHEMA = "homebrain-answer-quality-paired-reviews.v1"
REPORT_SCHEMA = "homebrain-answer-quality-paired-review-report.v1"
REVIEW_ENTRY_FIELDS = frozenset({
    "case_id", "baseline_answer_sha256", "candidate_answer_sha256",
    "reviewer", "evidence_reference_sha256", "baseline_review",
    "candidate_review",
})
REVIEW_FIELDS = frozenset({
    "grounding", "causal_calibration", "useful_first_attempt",
    "clarity", "safety", "grounded_factual_conclusions",
    "factual_conclusions_evaluated", "unsupported_definitive_causal_claims",
})
REVIEWER_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,80}$")


def _bind_arm(
    run: dict, item: dict, *, side: str, catalog: dict,
) -> dict[str, Any]:
    digest = item[side + "_answer_sha256"]
    if (not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)
            or digest != run["answer_sha256"]):
        raise ScorecardInputError(
            f"{item['case_id']}: {side} review is not bound to the exact recorded answer"
        )
    grade = item[side + "_review"]
    if not isinstance(grade, dict) or set(grade) != REVIEW_FIELDS:
        raise ScorecardInputError("Review must contain exactly the fixed rubric fields")
    return {
        "case_id": item["case_id"],
        "model": run["model"],
        "build_sha": run["build_sha"],
        "reviewer": item["reviewer"],
        # No private source references, URLs, tool payloads or raw responses.
        "evidence_reference": item["evidence_reference_sha256"],
        "review": grade,
        "metrics": {"latency_seconds": run["elapsed_ms"] / 1000},
    }


def _one_arm_identity(runs: dict, side: str) -> tuple[str, str, str] | None:
    identities = {
        (row["provider"], row["model"], row["build_sha"])
        for row in runs.values()
    }
    if len(identities) > 1:
        raise ScorecardInputError(
            f"{side} must keep a single disclosed provider/model/build across cases"
        )
    return next(iter(identities)) if identities else None


def build_paired_review_report(
    baseline: Any, candidate: Any, review_payload: Any, *,
    packets: list[dict] | None = None, catalog: dict | None = None,
) -> dict[str, Any]:
    """Require exact run and answer identity before comparing manual reviews.

    First-attempt, exact packet-hash compatibility is checked by existing Q1
    preflight. No grade is inferred for a missing answer or missing review.
    """
    packets = build_fixed_packets() if packets is None else packets
    catalog = load_catalog() if catalog is None else catalog
    preflight = pair_metadata(baseline, candidate, packets)
    before = validate_run_manifest(baseline, packets)
    after = validate_run_manifest(candidate, packets)
    before_identity = _one_arm_identity(before, "baseline")
    after_identity = _one_arm_identity(after, "candidate")
    if (before_identity is not None and after_identity is not None
            and before_identity == after_identity):
        raise ScorecardInputError(
            "Comparison arms have identical provider/model/build identity"
        )
    if (not isinstance(review_payload, dict)
            or set(review_payload) != {"schema", "pairs"}
            or review_payload["schema"] != REVIEW_SCHEMA
            or not isinstance(review_payload["pairs"], list)):
        raise ScorecardInputError("Invalid paired human-review manifest")

    eligible = set(preflight["paired_case_ids"])
    seen = set()
    left, right = [], []
    wins = losses = ties = 0
    # Ordinal changes are reviewer judgements, never lexical model scores.
    grade_rank = {"fail": 0, "partial": 1, "pass": 2}
    dimension_changes = {
        dimension: {"candidate_better": 0, "baseline_better": 0, "tied": 0}
        for dimension in REVIEW_KEYS
    }
    paired_latency_deltas: list[float] = []
    baseline_overclaims = candidate_overclaims = 0
    for item in review_payload["pairs"]:
        if not isinstance(item, dict) or set(item) != REVIEW_ENTRY_FIELDS:
            raise ScorecardInputError("Paired review fields must be metadata-only")
        case_id = item["case_id"]
        if not isinstance(case_id, str) or case_id not in eligible:
            raise ScorecardInputError(
                "Review case is absent from exact same-packet first-run pair"
            )
        if case_id in seen:
            raise ScorecardInputError("Duplicate paired review for case")
        seen.add(case_id)
        reviewer = item["reviewer"]
        receipt_hash = item["evidence_reference_sha256"]
        if (not isinstance(reviewer, str)
                or not REVIEWER_RE.fullmatch(reviewer)
                or not isinstance(receipt_hash, str)
                or not SHA256_RE.fullmatch(receipt_hash)
                or receipt_hash == "0" * 64):
            raise ScorecardInputError(
                "Review requires bounded reviewer pseudonym and evidence digest"
            )
        for side in ("baseline", "candidate"):
            # The shared human source-evidence reference is an attestation,
            # not independently verified proof that the reviewer saw evidence.
            item_grade = _bind_arm(
                before[case_id] if side == "baseline" else after[case_id],
                item, side=side, catalog=catalog,
            )
            (left if side == "baseline" else right).append(item_grade)

        earlier = item["baseline_review"]["useful_first_attempt"] == "pass"
        later = item["candidate_review"]["useful_first_attempt"] == "pass"
        wins += int(later and not earlier)
        losses += int(earlier and not later)
        ties += int(earlier == later)
        for dimension in REVIEW_KEYS:
            baseline_grade = grade_rank[item["baseline_review"][dimension]]
            candidate_grade = grade_rank[item["candidate_review"][dimension]]
            outcome = (
                "candidate_better" if candidate_grade > baseline_grade
                else "baseline_better" if baseline_grade > candidate_grade
                else "tied"
            )
            dimension_changes[dimension][outcome] += 1
        baseline_overclaims += item["baseline_review"]["unsupported_definitive_causal_claims"]
        candidate_overclaims += item["candidate_review"]["unsupported_definitive_causal_claims"]
        paired_latency_deltas.append(
            (after[case_id]["elapsed_ms"] - before[case_id]["elapsed_ms"]) / 1000
        )

    # Reuse the permanent source-reviewed rubric and data validation.
    # Separate arm calls ensure the scorecard does not conflate model/build
    # identity and never count an unrelated legacy task as a reviewed packet.
    left_card = build_scorecard({
        "schema": "homebrain-answer-quality-reviews.v1", "reviews": left,
    }, catalog)
    right_card = build_scorecard({
        "schema": "homebrain-answer-quality-reviews.v1", "reviews": right,
    }, catalog)
    lhs = left_card["models"][0] if left else None
    rhs = right_card["models"][0] if right else None
    reviewed = len(seen)
    return {
        "schema": REPORT_SCHEMA,
        "measurement_status": (
            "human_review_sample_reported" if reviewed else "not_measured"
        ),
        "scope": "curated-offline-packets-only",
        "defined_curated_cases": len(packets),
        "eligible_same_packet_first_run_pairs": preflight["paired_cases"],
        "human_reviewed_pairs": reviewed,
        "reviewed_case_ids": sorted(seen),
        "unreviewed_paired_case_ids": sorted(eligible - seen),
        "baseline_identity": (
            dict(zip(("provider", "model", "build_sha"), before_identity))
            if before_identity else None
        ),
        "candidate_identity": (
            dict(zip(("provider", "model", "build_sha"), after_identity))
            if after_identity else None
        ),
        "baseline_reviewed_scorecard": lhs,
        "candidate_reviewed_scorecard": rhs,
        "candidate_useful_first_attempt_wins": wins if reviewed else None,
        "candidate_useful_first_attempt_losses": losses if reviewed else None,
        "candidate_useful_first_attempt_ties": ties if reviewed else None,
        "paired_review_dimension_changes": dimension_changes if reviewed else None,
        "paired_unsupported_definitive_causes": ({
            "baseline_count": baseline_overclaims,
            "candidate_count": candidate_overclaims,
            "candidate_minus_baseline": candidate_overclaims - baseline_overclaims,
        } if reviewed else None),
        "paired_latency_delta": ({
            "sample_count": reviewed,
            "median_candidate_minus_baseline_seconds": round(median(paired_latency_deltas), 3),
            "negative_means_candidate_faster": True,
            "scope": "offline_model_request_timing_not_homebrain_live_latency",
        } if reviewed else None),
        "completeness": (
            "curated_cohort_reviewed_not_independently_audited"
            if reviewed == len(packets) else "partial_or_unmeasured"
        ),
        "acceptance_gate_passed": False,
        "review_blinding": "not_independently_verified",
        "source_evidence_attestation": "reviewer_supplied_not_independently_authenticated",
        "actual_model_input_delivery": "not_independently_authenticated",
        "answer_authenticity": "hash_bound_to_user_supplied_run_not_independently_authenticated",
        "cloud_usage_and_costs": "not_recorded_in_run_manifest",
        "limitations": [
            "A human review is asserted, not independently authenticated by this script",
            "Both raw answers and complete source citations require private evidence review",
            "No unreviewed cases contribute to factual or first-attempt percentages",
            "Paired grade changes are ordinal human judgements, not causal estimates of model quality",
            "Paired latency differences describe these same offline cases only, not production timing",
            "A matching frozen hash does not prove what prompt the provider actually received",
            "The 13 legacy live tasks remain outside this offline paired sample",
            "No Claude equivalence or production HomeBrain answer improvement is established",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = build_paired_review_report(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
        json.loads(args.reviews.read_text(encoding="utf-8")),
    )
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
