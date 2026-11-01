#!/usr/bin/env python3
"""Extract a privacy-minimal, UNGRADED HomeBrain answer-quality run record.

Never copies the natural-language answer, source event values, app/device IDs,
full tool arguments, URLs or private logs. It only records audited-safe
metadata and hashes. A captured run is not a human review or a model score.

Usage:
  python scripts/answer_quality_capture.py --case-id causal_light2_off \
    --input /private/homebrain-response.json \
    --question-file /private/actual-question.txt --output /private/run.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from answer_quality_scorecard import load_catalog, ScorecardInputError


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalized_prompt(prompt: str) -> str:
    return " ".join(prompt.strip().split())


def _finite_nonnegative(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 3) if math.isfinite(value) and value >= 0 else None


def _safe_str(value: Any, allowlist: set[str]) -> str | None:
    return value if isinstance(value, str) and value in allowlist else None


def _case_definition(case_id: str, *, root: Path) -> tuple[dict, str]:
    catalog = load_catalog(
        root / "tests/fixtures/homebrain_golden_tasks_v1.json",
        root / "tests/fixtures/answer_quality_cases_v1.json",
    )
    if case_id not in catalog:
        raise ScorecardInputError(f"Unknown benchmark case {case_id!r}")
    old = json.loads((root / "tests/fixtures/homebrain_golden_tasks_v1.json").read_text())
    new = json.loads((root / "tests/fixtures/answer_quality_cases_v1.json").read_text())
    item = next(
        (record for record in old["tasks"] if record["key"] == case_id), None
    )
    if item is not None:
        return item, "live_task"
    return next(record for record in new["cases"] if record["id"] == case_id), "offline_source_packet"


def extract_capture(
    response: Any, *, case_id: str, actual_question: str | None,
    root: Path,
) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ScorecardInputError("HomeBrain response must be an object")
    case, kind = _case_definition(case_id, root=root)
    reference_prompt = case["prompt"]
    normalized_reference = _normalized_prompt(reference_prompt)
    normalized_actual = (
        _normalized_prompt(actual_question) if isinstance(actual_question, str)
        else None
    )
    if normalized_actual is None:
        match = "not_checked"
    elif normalized_actual == normalized_reference:
        match = "exact"
    else:
        match = "different"

    message = response.get("message")
    if not isinstance(message, str):
        raise ScorecardInputError("HomeBrain response has no string message")
    metrics = response.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    counters = metrics.get("counters")
    counters = counters if isinstance(counters, dict) else {}
    evidence = response.get("evidence")
    evidence = evidence if isinstance(evidence, list) else []
    evidence_objects = [e for e in evidence if isinstance(e, dict)]
    coverage = response.get("investigation_coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    comparisons = coverage.get("hypothesisComparisons")
    comparisons = comparisons if isinstance(comparisons, list) else []
    timed = metrics.get("timings_ms")
    timed = timed if isinstance(timed, dict) else {}
    model_runs = metrics.get("model_round_details")
    model_runs = model_runs if isinstance(model_runs, list) else []
    providers = {
        item.get("provider") for item in model_runs
        if isinstance(item, dict) and isinstance(item.get("provider"), str)
    }
    provider = providers.pop() if len(providers) == 1 else None
    provider = _safe_str(provider, {"ollama-cloud", "ollama-local", "openai", "anthropic"})
    version = response.get("version")
    model = response.get("model")
    # The version/model values are for private local analysis only, never
    # raw strings of arbitrary content in a publication fixture.
    def bounded_identity(value: Any) -> str | None:
        if not isinstance(value, str) or len(value) > 48:
            return None
        return value if all(ch.isascii() and (ch.isalnum() or ch in ".:-_") for ch in value) else None

    read_mutations = sum(item.get("mutates") is True for item in evidence_objects)
    unknown_effects = sum(
        item.get("mutates") is not False or item.get("effect") != "read"
        for item in evidence_objects
    )
    report = {
        "schema": "homebrain-answer-quality-capture.v1",
        "case_id": case_id,
        "case_origin": kind,
        "capture_is_quality_review": False,
        "matches_registered_live_question": kind == "live_task" and match == "exact",
        "model": bounded_identity(model),
        "provider": provider,
        "add_on_version": bounded_identity(version),
        "model_tier": _safe_str(response.get("model_tier_requested"), {"free", "paid", "local"}),
        "prompt_match": match,
        "registered_prompt_sha256": _sha256(normalized_reference),
        "actual_prompt_sha256": _sha256(normalized_actual) if normalized_actual is not None else None,
        "answer_sha256": _sha256(message),
        "answer_character_count": len(message),
        "technical_outcome": _safe_str(metrics.get("outcome"), {"success", "unresolved", "failed", "refused", "cancelled"}),
        "wall_elapsed_ms": _finite_nonnegative(response.get("elapsed_ms")),
        "agent_elapsed_ms": _finite_nonnegative(timed.get("total")),
        "tool_calls_reported": _finite_nonnegative(counters.get("tool_calls")),
        "model_rounds_reported": _finite_nonnegative(counters.get("model_rounds")),
        "evidence_receipt_count": len(evidence_objects),
        "evidence_read_only_observed": bool(evidence_objects) and unknown_effects == 0,
        "read_only_classification_unknown_count": unknown_effects,
        "mutating_receipt_count": read_mutations,
        "hypothesis_checks_reported": len([item for item in comparisons if isinstance(item, dict)]),
        "hypotheses_explicitly_unverified": sum(
            item.get("hypothesis_verdict") == "unverified"
            for item in comparisons if isinstance(item, dict)
        ),
        "causal_verification_reported": (
            coverage.get("rootCauseVerified")
            if isinstance(coverage.get("rootCauseVerified"), bool) else None
        ),
        "question_resolution_reported": (
            coverage.get("questionResolved")
            if isinstance(coverage.get("questionResolved"), bool) else None
        ),
        "review": {
            "status": "pending_independent_source_review",
            "grounding": None,
            "causal_calibration": None,
            "useful_first_attempt": None,
            "clarity": None,
            "safety": None,
        },
        "limitations": [
            "No natural-language answer text or private event payload is exported",
            "No correctness, causal conclusion or first-attempt status is inferred",
            "Model/provider and times are as reported, not independently authenticated",
            "Exact live prompt and real source evidence must be reviewed separately",
            "A clean mutating-receipt count is not an independently proven safety audit",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--question-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    response = json.loads(args.input.read_text(encoding="utf-8"))
    question = args.question_file.read_text(encoding="utf-8") if args.question_file else None
    packet = extract_capture(response, case_id=args.case_id, actual_question=question, root=root)
    result = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
