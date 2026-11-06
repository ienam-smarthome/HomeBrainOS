#!/usr/bin/env python3
"""Read private original Q2 answers and bind optional human reviews per session.

Historical Q2 captures used different local checkout SHAs. Never combine them
into one falsely same-build review, never publish private answer bytes, and
never treat a source/answer digest match as a factual-quality judgement.

This script does not call a model, network, Hubitat, Home Assistant or MCP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from answer_quality_q2_recorded_pairs import ARCHIVE, audit_recorded_pairs
from answer_quality_paired_reviews import (
    REVIEW_SCHEMA, build_paired_review_report,
)
from answer_quality_scorecard import ScorecardInputError

REPO = Path(__file__).resolve().parents[1]
FILES_SCHEMA = "homebrain-answer-quality-q2-original-files.v1"
OUTPUT_SCHEMA = "homebrain-answer-quality-q2-original-review-audit.v1"
MAX_ANSWER_BYTES = 16384


def _read_original_digest(file_name: Any, case_id: str, side: str, repo: Path) -> str:
    """Hash actual saved bytes; never echo paths or raw content on an error."""
    label = f"{case_id}/{side}"
    if not isinstance(file_name, str) or not file_name.strip():
        raise ScorecardInputError(f"{label}: private original file path required")
    path = Path(file_name)
    if not path.is_absolute():
        raise ScorecardInputError(f"{label}: absolute private original file path required")
    try:
        root = repo.resolve(strict=True)
        candidate = path.resolve(strict=True)
        if (candidate == root or root in candidate.parents
                or path.is_symlink()
                or any(parent.is_symlink() for parent in path.parents)):
            raise ScorecardInputError(f"{label}: source checkout or symlink not allowed")
        if not candidate.is_file():
            raise ScorecardInputError(f"{label}: original is not a regular file")
        with candidate.open("rb") as source:
            raw = source.read(MAX_ANSWER_BYTES + 1)
        if len(raw) > MAX_ANSWER_BYTES:
            raise ScorecardInputError(f"{label}: private answer size exceeds limit")
        return hashlib.sha256(raw).hexdigest()
    except ScorecardInputError:
        raise
    except (OSError, RuntimeError, ValueError):
        # An OS exception may contain user profile paths, which are sensitive.
        raise ScorecardInputError(f"{label}: original private file unavailable") from None


def audit_original_source_reviews(
    archive: Any,
    file_manifest: Any,
    review_payload: Any | None = None,
    *,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Check original byte hashes and optionally bind *supplied* human grades.

    Every graded case is independently checked with the existing single-build
    paired-review function, preventing four historical checkout SHAs from
    being silently merged into one build-specific accuracy score.
    """
    audited = audit_recorded_pairs(archive)
    if (not isinstance(file_manifest, dict)
            or set(file_manifest) != {"schema", "cases"}
            or file_manifest["schema"] != FILES_SCHEMA
            or not isinstance(file_manifest["cases"], list)
            or not file_manifest["cases"]):
        raise ScorecardInputError("Invalid private Q2 original-file manifest")
    recorded = {pair["case_id"]: pair for pair in archive["pairs"]}
    verified: dict[str, dict] = {}
    for entry in file_manifest["cases"]:
        if not isinstance(entry, dict) or set(entry) != {
            "case_id", "baseline_file", "candidate_file",
        }:
            raise ScorecardInputError("Original-file manifest accepts file paths only")
        case_id = entry["case_id"]
        if not isinstance(case_id, str) or case_id not in recorded:
            raise ScorecardInputError("Unknown original-answer case")
        if case_id in verified:
            raise ScorecardInputError("Duplicate original-answer case")
        pair = recorded[case_id]
        for side in ("baseline", "candidate"):
            digest = _read_original_digest(entry[side + "_file"], case_id, side, repo)
            if digest != pair[side]["answer_sha256"]:
                raise ScorecardInputError(
                    f"{case_id}/{side}: actual original-answer bytes do not match recorded SHA-256"
                )
        verified[case_id] = pair

    if review_payload is None:
        review_payload = {"schema": REVIEW_SCHEMA, "pairs": []}
    if (not isinstance(review_payload, dict)
            or set(review_payload) != {"schema", "pairs"}
            or review_payload.get("schema") != REVIEW_SCHEMA
            or not isinstance(review_payload.get("pairs"), list)):
        raise ScorecardInputError("Invalid private paired-review manifest")

    reviews = {}
    for review in review_payload["pairs"]:
        case_id = review.get("case_id") if isinstance(review, dict) else None
        if not isinstance(case_id, str) or case_id not in verified:
            raise ScorecardInputError("Human review requires both verified original files")
        if case_id in reviews:
            raise ScorecardInputError("Duplicate source-reviewed Q2 case")
        reviews[case_id] = review

    rows = []
    for case_id in sorted(verified):
        pair = verified[case_id]
        row = {
            "case_id": case_id,
            "original_answer_bytes_verified": True,
            "same_checkout_sha_within_pair": True,
            "different_case_builds_not_combined": True,
            "baseline_model": pair["baseline"]["model"],
            "candidate_model": pair["candidate"]["model"],
            "human_review_status": "not_measured",
            "review_dimension_changes": None,
            "unsupported_definitive_cause_counts": None,
        }
        if case_id in reviews:
            # One pair per call: never override the same-build guard to accept
            # multiple different historical local checkouts as one experiment.
            left = {"schema": "homebrain-answer-quality-offline-run.v1",
                    "runs": [pair["baseline"]]}
            right = {"schema": "homebrain-answer-quality-offline-run.v1",
                     "runs": [pair["candidate"]]}
            source_review = {
                "schema": REVIEW_SCHEMA, "pairs": [reviews[case_id]],
            }
            result = build_paired_review_report(left, right, source_review)
            if result["human_reviewed_pairs"] != 1:
                raise ScorecardInputError("Expected a single source-reviewed case")
            row["human_review_status"] = (
                "human_review_submitted_answer_bound_not_independently_authenticated"
            )
            row["review_dimension_changes"] = result["paired_review_dimension_changes"]
            row["unsupported_definitive_cause_counts"] = (
                result["paired_unsupported_definitive_causes"]
            )
        rows.append(row)

    return {
        "schema": OUTPUT_SCHEMA,
        "official_acceptance_gate_passed": False,
        "formal_cross_build_accuracy_pct": None,
        "measurement_status": (
            "individual_user_submitted_human_reviews" if reviews else "not_measured"
        ),
        "archive_case_count": audited["recorded_pairs"],
        "originals_verified_pairs": len(verified),
        "originals_verified_answer_files": len(verified) * 2,
        "human_reviewed_individual_pairs": len(reviews),
        "unverified_original_case_ids": sorted(set(recorded) - set(verified)),
        "reviewed_case_ids": sorted(reviews),
        "cases": rows,
        "provenance": {
            "original_bytes": "sha256_matched_locally_supplied_raw_files",
            "human_review": "user_supplied_not_independently_authenticated",
            "provider_input_delivery": "not_independently_authenticated",
            "first_attempt_status": "recorded_manifest_only_not_independently_verified",
            "cross_case_checkout": "different_builds_kept_separate",
        },
        "limitations": [
            "A byte digest match does not prove provider delivery or model identity",
            "No reviewer grades are generated, inferred or corrected by this script",
            "Human reviews require independent verification of source and claims",
            "Historic sessions used distinct checkout SHAs; no pooled same-build accuracy",
            "No production HomeBrain latency or Claude comparison is established",
            "Answer bytes, original file locations, reviewer identities and digests never appear in output",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--files", type=Path, required=True,
                        help="Private local JSON file with paths to original first answers")
    parser.add_argument("--reviews", type=Path,
                        help="Optional completed private, answer-SHA-bound human reviews")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = audit_original_source_reviews(
        json.loads(args.archive.read_text(encoding="utf-8")),
        json.loads(args.files.read_text(encoding="utf-8")),
        json.loads(args.reviews.read_text(encoding="utf-8"))
        if args.reviews is not None else None,
    )
    content = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
