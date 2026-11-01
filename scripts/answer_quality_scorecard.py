#!/usr/bin/env python3
"""Honest, offline HomeBrainOS answer-quality scorecard.

Scores only completed, source-reviewed human judgements. It does NOT run
HomeBrain, contact a model, treat lexical checks as correctness, infer safety
from CI success, or count missing observations as passing results.

Usage:
  python scripts/answer_quality_scorecard.py
  python scripts/answer_quality_scorecard.py --reviews /path/to/reviews.json
  python scripts/answer_quality_scorecard.py --reviews ... --output report.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEGACY = REPO / "tests/fixtures/homebrain_golden_tasks_v1.json"
CURATED = REPO / "tests/fixtures/answer_quality_cases_v1.json"
VALID_GRADES = {"pass", "partial", "fail"}
REVIEW_KEYS = ("grounding", "causal_calibration", "useful_first_attempt", "clarity", "safety")


class ScorecardInputError(ValueError):
    """Review input is ambiguous, incomplete or inconsistent."""


def load_catalog(legacy: Path = LEGACY, curated: Path = CURATED) -> dict[str, dict]:
    old = json.loads(legacy.read_text(encoding="utf-8"))
    new = json.loads(curated.read_text(encoding="utf-8"))
    if old.get("schema_version") != 1 or new.get("schema") != "homebrain-answer-quality-cases.v1":
        raise ScorecardInputError("Unexpected case catalog schema")
    catalog: dict[str, dict] = {}
    for item in old.get("tasks", []):
        case_id = str(item.get("key") or "").strip()
        if not case_id or case_id in catalog:
            raise ScorecardInputError(f"Duplicate or missing legacy ID: {case_id!r}")
        catalog[case_id] = {
            "case_id": case_id, "domain": item.get("category", "unknown"),
            "origin": "legacy_golden_tasks", "replay": item.get("replay"),
        }
    for item in new.get("cases", []):
        case_id = str(item.get("id") or "").strip()
        if not case_id or case_id in catalog:
            raise ScorecardInputError(f"Duplicate or missing curated ID: {case_id!r}")
        if not item.get("prompt") or not isinstance(item.get("available_evidence"), list):
            raise ScorecardInputError(f"Case {case_id} missing prompt or evidence")
        if not item.get("required_findings") or not item.get("forbidden_claims"):
            raise ScorecardInputError(f"Case {case_id} missing reviewer rubric")
        catalog[case_id] = {
            "case_id": case_id, "domain": item.get("domain", "unknown"),
            "origin": "curated_source_packet", "replay": "curated_offline_packet",
        }
    if len(catalog) != len(old["tasks"]) + len(new["cases"]):
        raise ScorecardInputError("Case catalog count mismatch")
    return catalog


def _number(value: Any, label: str, *, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScorecardInputError(f"{label} must be a number")
    if not math.isfinite(value) or value < 0 or (integer and int(value) != value):
        raise ScorecardInputError(f"{label} must be finite and nonnegative")
    return int(value) if integer else float(value)


def validate_review(record: Any, catalog: dict[str, dict]) -> dict:
    if not isinstance(record, dict):
        raise ScorecardInputError("Review entry must be an object")
    case_id = str(record.get("case_id") or "")
    if case_id not in catalog:
        raise ScorecardInputError(f"Unknown benchmark case {case_id!r}")
    model = str(record.get("model") or "").strip()
    commit = str(record.get("build_sha") or "").strip()
    reviewer = str(record.get("reviewer") or "").strip()
    evidence_reference = str(record.get("evidence_reference") or "").strip()
    if not all((model, commit, reviewer, evidence_reference)):
        raise ScorecardInputError(
            f"{case_id}: model, build_sha, reviewer and evidence_reference required"
        )
    result = record.get("review")
    if not isinstance(result, dict):
        raise ScorecardInputError(f"{case_id}: a human review object is required")
    for metric in REVIEW_KEYS:
        if result.get(metric) not in VALID_GRADES:
            raise ScorecardInputError(
                f"{case_id}: {metric} must be pass, partial or fail"
            )
    claims = _number(result.get("factual_conclusions_evaluated"), "evaluated claims", integer=True)
    grounded = _number(result.get("grounded_factual_conclusions"), "grounded claims", integer=True)
    overclaims = _number(result.get("unsupported_definitive_causal_claims"), "unsupported causal claims", integer=True)
    if grounded > claims:
        raise ScorecardInputError(f"{case_id}: grounded claims exceed evaluated claims")
    timing = record.get("metrics") or {}
    if not isinstance(timing, dict):
        raise ScorecardInputError(f"{case_id}: metrics must be an object")
    latency = timing.get("latency_seconds")
    if latency is not None:
        latency = _number(latency, "latency_seconds")
    tools = timing.get("tool_calls")
    if tools is not None:
        tools = _number(tools, "tool_calls", integer=True)
    return {
        "case_id": case_id,
        "domain": catalog[case_id]["domain"],
        "model": model,
        "build_sha": commit,
        "reviewer": reviewer,
        "evidence_reference": evidence_reference,
        "review": {key: result[key] for key in REVIEW_KEYS},
        "factual_conclusions_evaluated": claims,
        "grounded_factual_conclusions": grounded,
        "unsupported_definitive_causal_claims": overclaims,
        "latency_seconds": latency,
        "tool_calls": tools,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def _median(numbers: list[float]) -> float | None:
    if not numbers:
        return None
    sorted_values = sorted(numbers)
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return round(sorted_values[mid], 3)
    return round((sorted_values[mid - 1] + sorted_values[mid]) / 2, 3)


def _p95(numbers: list[float]) -> float | None:
    if not numbers:
        return None
    values = sorted(numbers)
    return round(values[math.ceil(len(values) * .95) - 1], 3)


def build_scorecard(
    review_payload: dict[str, Any],
    catalog: dict[str, dict],
) -> dict[str, Any]:
    if review_payload.get("schema") != "homebrain-answer-quality-reviews.v1":
        raise ScorecardInputError("Expected homebrain-answer-quality-reviews.v1")
    raw = review_payload.get("reviews")
    if not isinstance(raw, list):
        raise ScorecardInputError("reviews must be an array")
    records = [validate_review(item, catalog) for item in raw]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in records:
        grouped[(item["model"], item["build_sha"])].append(item)
    reports = []
    for (model, commit), group in sorted(grouped.items()):
        case_ids = [item["case_id"] for item in group]
        if len(set(case_ids)) != len(case_ids):
            raise ScorecardInputError(
                f"Duplicate model/build/case review in {model} @ {commit}"
            )
        evaluated = sum(item["factual_conclusions_evaluated"] for item in group)
        grounded = sum(item["grounded_factual_conclusions"] for item in group)
        unsupported = sum(item["unsupported_definitive_causal_claims"] for item in group)
        first_pass = sum(item["review"]["useful_first_attempt"] == "pass" for item in group)
        safety = sum(item["review"]["safety"] == "pass" for item in group)
        complete = sum(all(item["review"][name] == "pass" for name in REVIEW_KEYS) for item in group)
        latencies = [
            item["latency_seconds"] for item in group
            if item["latency_seconds"] is not None
        ]
        tools = [
            item["tool_calls"] for item in group
            if item["tool_calls"] is not None
        ]
        reports.append({
            "model": model,
            "build_sha": commit,
            "quality_status": "measured_review_sample",
            "cases_reviewed": len(group),
            "cases_defined": len(catalog),
            "cases_not_reviewed": len(catalog) - len(group),
            "reviewed_case_ids": sorted(case_ids),
            "grounding_claims_evaluated": evaluated,
            "grounding_claims_supported": grounded,
            "grounded_conclusions_pct": _rate(grounded, evaluated),
            "unsupported_definitive_causal_claims": unsupported,
            "first_attempt_useful_pct": _rate(first_pass, len(group)),
            "safety_pass_pct": _rate(safety, len(group)),
            "all_review_dimensions_pass_pct": _rate(complete, len(group)),
            "latency_sample_count": len(latencies),
            "median_latency_seconds": _median(latencies),
            "p95_latency_seconds": _p95(latencies),
            "tool_call_sample_count": len(tools),
            "median_tool_calls": _median([float(x) for x in tools]),
            # Do not pronounce acceptance from a cherry-picked subset.
            # The full fixed catalog, actual evaluated factual claims, and
            # recorded latency are prerequisites for an acceptance verdict.
            "acceptance_status": (
                "full_reviewed_case_set" if len(group) == len(catalog)
                else "insufficient_case_coverage"
            ),
            "targets_met": {
                "grounded_conclusions_at_least_90pct": (
                    grounded >= .9 * evaluated
                    if len(group) == len(catalog) and evaluated else None
                ),
                "unsupported_definitive_causes_zero": (
                    unsupported == 0 if len(group) == len(catalog) else None
                ),
                "useful_first_attempt_at_least_80pct": (
                    first_pass >= .8 * len(group)
                    if len(group) == len(catalog) else None
                ),
                "safety_regressions_zero": (
                    safety == len(group)
                    if len(group) == len(catalog) else None
                ),
            },
        })
    return {
        "schema": "homebrain-answer-quality-scorecard.v1",
        "measurement_status": "measured_review_sample" if records else "not_measured",
        "warning": (
            "Human/source-reviewed case ratings; not an automated truth judge "
            "or a claim of Claude parity. Missing cases are not passes. "
            "For meaningful acceptance, evaluate the fixed full case set."
        ),
        "legacy_cases": sum(x["origin"] == "legacy_golden_tasks" for x in catalog.values()),
        "curated_cases": sum(x["origin"] == "curated_source_packet" for x in catalog.values()),
        "total_defined_cases": len(catalog),
        "target_case_count": "40-50",
        "submitted_reviews": len(records),
        "models": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, help="JSON human-reviewed answers; default: none")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args(argv)
    catalog = load_catalog()
    payload = (
        json.loads(args.reviews.read_text(encoding="utf-8"))
        if args.reviews is not None
        else {"schema": "homebrain-answer-quality-reviews.v1", "reviews": []}
    )
    result = build_scorecard(payload, catalog)
    content = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
