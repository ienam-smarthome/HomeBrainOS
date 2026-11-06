#!/usr/bin/env python3
"""Reconcile recorded Q2 first-answer metadata against immutable source packets.

No network, model, live Hubitat/HA read/write, answer text or automatic grades.
Historical user-supplied manifests identify local checkout SHAs, NOT
independently authenticated model builds or provider prompt delivery.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any

from answer_quality_fixed_packets import (
    ScorecardInputError, build_fixed_packets, pair_metadata,
    validate_run_manifest,
)

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = REPO / "tests/fixtures/answer_quality_q2_recorded_pairs_v1.json"
SCHEMA = "homebrain-answer-quality-q2-recorded-pairs.v1"
OUTPUT_SCHEMA = "homebrain-answer-quality-q2-recorded-pair-audit.v1"


def audit_recorded_pairs(
    payload: Any, packets: list[dict] | None = None,
) -> dict[str, Any]:
    """Check historical source/answer *metadata*, not the original answer bytes.

    Pair individually: the four actual Q2 sessions used different checkout
    SHAs, so a single-build aggregate would incorrectly certify comparability.
    """
    if (not isinstance(payload, dict)
            or set(payload) != {"schema", "description", "review_status", "pairs"}
            or payload.get("schema") != SCHEMA
            or payload.get("review_status") != "qualitative_only_not_measured"
            or not isinstance(payload.get("description"), str)
            or not isinstance(payload.get("pairs"), list)
            or not payload["pairs"]):
        raise ScorecardInputError("Invalid recorded Q2 metadata archive")

    packets = build_fixed_packets() if packets is None else packets
    rows: list[dict] = []
    ids: set[str] = set()
    builds: set[str] = set()
    providers: set[tuple[str, str]] = set()
    baseline_times: list[int | float] = []
    candidate_times: list[int | float] = []
    differences: list[float] = []
    for pair in payload["pairs"]:
        if not isinstance(pair, dict) or set(pair) != {"case_id", "baseline", "candidate"}:
            raise ScorecardInputError("Recorded pair must contain metadata only")
        case_id = pair["case_id"]
        if not isinstance(case_id, str) or case_id in ids:
            raise ScorecardInputError("Missing or duplicate recorded case ID")
        ids.add(case_id)
        before = pair["baseline"]
        after = pair["candidate"]
        # Reuse production Q1 packet fingerprint and strict metadata-only gates.
        before_manifest = {"schema": "homebrain-answer-quality-offline-run.v1", "runs": [before]}
        after_manifest = {"schema": "homebrain-answer-quality-offline-run.v1", "runs": [after]}
        checked = pair_metadata(before_manifest, after_manifest, packets)
        if checked["paired_case_ids"] != [case_id]:
            raise ScorecardInputError("Recorded case does not match exact frozen packet")
        b = validate_run_manifest(before_manifest, packets)[case_id]
        c = validate_run_manifest(after_manifest, packets)[case_id]
        if b["build_sha"] != c["build_sha"]:
            raise ScorecardInputError("A recorded pair must use one checkout SHA")
        if (b["provider"], b["model"]) == (c["provider"], c["model"]):
            raise ScorecardInputError("A recorded pair must compare distinct model identities")
        builds.add(b["build_sha"])
        providers.add((b["provider"], c["provider"]))
        baseline_times.append(b["elapsed_ms"])
        candidate_times.append(c["elapsed_ms"])
        differences.append(float(c["elapsed_ms"] - b["elapsed_ms"]))
        rows.append({
            "case_id": case_id,
            "packet_hash_matches_frozen_fixture": True,
            "recorded_first_attempt_metadata": True,
            "same_checkout_sha_within_pair": True,
            "baseline_model": b["model"],
            "candidate_model": c["model"],
            "baseline_elapsed_ms": b["elapsed_ms"],
            "candidate_elapsed_ms": c["elapsed_ms"],
            "candidate_minus_baseline_ms": c["elapsed_ms"] - b["elapsed_ms"],
            "human_review_grade": None,
            "source_truth_attested_by_digest": False,
            "model_input_delivery_attested": False,
        })
    return {
        "schema": OUTPUT_SCHEMA,
        "measurement_status": "observed_local_request_timing_only",
        "official_quality_measurement": "not_measured",
        "recorded_pairs": len(rows),
        "validated_frozen_packet_hash_pairs": len(rows),
        "recorded_checkout_sha_count": len(builds),
        "cross_session_builds_identical": len(builds) == 1,
        "per_pair_checkout_consistency": True,
        "model_provider_pairs": len(providers),
        "timing_scope": "offline_model_request_only_not_homebrain_live_latency",
        "observed_baseline_median_ms": median(baseline_times),
        "observed_candidate_median_ms": median(candidate_times),
        "observed_paired_candidate_minus_baseline_median_ms": median(differences),
        "observed_candidate_faster_cases": sum(value < 0 for value in differences),
        "reviewed_human_pairs": 0,
        "formal_accuracy_percentage": None,
        "source_review_status": "historical_qualitative_only",
        "limitations": [
            "Historical user-supplied manifests are not independently authenticated provider records",
            "Recorded first attempt metadata does not prove actual model first-attempt status",
            "Answer digests were compared against some previously pasted originals in private reviews; this audit does not access or rehash those files",
            "Frozen packet hashes do not prove model input ingestion or source correctness",
            "Different local checkout SHAs prohibit a same-build four-case accuracy score",
            "No blinded human review grades or official Q4 acceptance claims are generated",
        ],
        "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = audit_recorded_pairs(json.loads(args.archive.read_text(encoding="utf-8")))
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
