#!/usr/bin/env python3
"""Privacy-safe Q1 intake of ONE user-supplied HomeBrain read-only response.

Does not grade model prose, certify a first attempt, attest build identity,
or make any Hubitat/Home Assistant calls. Full answer, evidence arguments,
device names, local addresses and raw logs stay in the private input.

Usage:
    python scripts/answer_quality_live_sample.py \
        --case multi_device_named --receipt /private/homebrain-response.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tests/fixtures/homebrain_golden_tasks_v1.json"
CURATED = ROOT / "tests/fixtures/answer_quality_cases_v1.json"
SCHEMA = "homebrain-answer-quality-live-sample.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"\d+(?:\.\d+){2,3}\Z")
_MODEL = re.compile(r"[a-zA-Z0-9_:./-]{1,80}\Z")
_KNOWN_OUTCOMES = frozenset({
    "success", "unresolved", "failed", "refused", "cancelled", "needs_input",
})


class LiveSampleError(ValueError):
    """A capture cannot safely be treated as the selected benchmark case."""


def normalise(question: str) -> str:
    return " ".join(question.strip().split())


def registered_read_only_prompt(case_id: str) -> str:
    old = json.loads(LEGACY.read_text(encoding="utf-8"))
    new = json.loads(CURATED.read_text(encoding="utf-8"))
    if old.get("schema_version") != 1 or new.get("schema") != "homebrain-answer-quality-cases.v1":
        raise LiveSampleError("Unexpected frozen case catalog schema")
    cases = [
        (item.get("key"), item.get("prompt"), item.get("read_only"))
        for item in old.get("tasks", [])
    ] + [
        (item.get("id"), item.get("prompt"), item.get("read_only"))
        for item in new.get("cases", [])
    ]
    matches = [(prompt, read_only) for key, prompt, read_only in cases if key == case_id]
    if len(matches) != 1:
        raise LiveSampleError("Benchmark case must have one unique registered identity")
    prompt, read_only = matches[0]
    if read_only is not True or not isinstance(prompt, str) or not prompt.strip():
        raise LiveSampleError("This intake is restricted to registered read-only questions")
    return prompt


def _integer(data: dict[str, Any], name: str) -> int | None:
    value = data.get(name)
    return value if type(value) is int and 0 <= value < 10**9 else None


def _duration_ms(value: Any) -> float | None:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 10**9:
        return None
    return float(value)


def _public_model(raw: Any) -> str | None:
    return raw if isinstance(raw, str) and _MODEL.fullmatch(raw) else None


def _public_version(raw: Any) -> str | None:
    return raw if isinstance(raw, str) and _VERSION.fullmatch(raw) else None


def intake(receipt: Any, case_id: str) -> dict[str, Any]:
    """Return only counts/flags suitable for publication, not answer content.

    A valid API digest establishes exact prompt at /api/ask. It does NOT
    establish actual model delivery, first-turn identity or deployed SHA.
    An independently source-reviewed answer is required before scoring.
    """
    question = registered_read_only_prompt(case_id)
    if not isinstance(receipt, dict):
        raise LiveSampleError("The response must be a JSON object")
    evidence = receipt.get("evidence")
    metrics = receipt.get("metrics")
    if not isinstance(evidence, list) or not all(isinstance(x, dict) for x in evidence):
        raise LiveSampleError("Missing or malformed evidence receipts")
    if not isinstance(metrics, dict):
        raise LiveSampleError("Missing metrics object")
    counters, timings = metrics.get("counters"), metrics.get("timings_ms")
    if not isinstance(counters, dict) or not isinstance(timings, dict):
        raise LiveSampleError("Metrics must contain counters and timings objects")
    provenance = receipt.get("request_provenance")
    expected = hashlib.sha256(normalise(question).encode("utf-8")).hexdigest()
    digest_valid = (
        isinstance(provenance, dict)
        and provenance.get("source") == "api_ask_request"
        and provenance.get("normalization") == "collapse-whitespace-v1"
        and isinstance(provenance.get("normalized_prompt_sha256"), str)
        and _SHA.fullmatch(provenance["normalized_prompt_sha256"]) is not None
        and provenance["normalized_prompt_sha256"] == expected
    )
    request_is_read = receipt.get("request_class") == "live-read"
    observed_write_count = sum(
        row.get("mutates") is True or row.get("effect") in {
            "write", "routine_write", "sensitive_write", "destructive_write",
        } for row in evidence
    )
    verified_reads = sum(
        row.get("mutates") is False
        and row.get("effect") == "read"
        and row.get("success") is True
        for row in evidence
    )
    read_failures = sum(
        row.get("mutates") is False
        and row.get("effect") == "read"
        and row.get("success") is False
        for row in evidence
    )
    outcome = metrics.get("outcome")
    if outcome not in _KNOWN_OUTCOMES:
        raise LiveSampleError("Missing or unsupported request outcome")
    if type(receipt.get("success")) is not bool:
        raise LiveSampleError("Missing transport-success boolean")
    problems = []
    if not digest_valid:
        problems.append("registered_api_question_not_attested")
    if not request_is_read:
        problems.append("not_a_read_only_request")
    if observed_write_count:
        problems.append("write_receipts_present")
    if not verified_reads:
        problems.append("no_successful_source_read_receipts")
    if read_failures:
        problems.append("source_read_failures_require_review")
    if outcome != "success":
        problems.append("request_outcome_not_success")
    first_attempt_proven = (
        isinstance(provenance, dict)
        and provenance.get("first_attempt_verified") is True
    )
    build_attested = (
        isinstance(provenance, dict)
        and provenance.get("deployed_build_sha_verified") is True
    )
    model_attested = (
        isinstance(provenance, dict)
        and provenance.get("model_delivery_verified") is True
    )
    # Even first_attempt_verified=true is a self-reported field of the
    # supplied JSON, not independently authenticated proof.
    return {
        "schema": SCHEMA,
        "case_id": case_id,
        "registered_api_question_match": digest_valid,
        "request_class": "live-read" if request_is_read else "other_or_missing",
        "transport_success": receipt["success"],
        "outcome": outcome,
        "model_reported": _public_model(receipt.get("model")),
        "version_reported": _public_version(receipt.get("version")),
        "wall_time_ms": _duration_ms(receipt.get("elapsed_ms")),
        "agent_time_ms": _duration_ms(timings.get("total")),
        "provider_time_ms": _duration_ms(timings.get("provider")),
        "model_rounds_reported": _integer(counters, "model_rounds"),
        "tool_calls_reported": _integer(counters, "tool_calls"),
        "successful_read_receipts": verified_reads,
        "failed_read_receipts": read_failures,
        "observed_write_receipts": observed_write_count,
        "blocked_model_write_batches_reported": _integer(
            counters, "read_only_model_write_blocked"
        ),
        "api_provenance_flags": {
            "model_delivery_reported": model_attested,
            "first_attempt_reported": first_attempt_proven,
            "deployed_sha_reported": build_attested,
            "independently_authenticated": False,
        },
        "q1_observational_read_only_sample": not any(
            x in problems for x in (
                "registered_api_question_not_attested", "not_a_read_only_request",
                "write_receipts_present", "no_successful_source_read_receipts",
            )
        ),
        "q1_source_review": "pending_independent_review",
        "q1_first_attempt_accuracy": "not_measured",
        "q1_factual_grounding": "not_measured",
        "q1_question_resolution": "not_measured",
        "completeness_warnings": problems,
        "limitations": [
            "An API request digest does not prove model delivery or first-attempt status",
            "Model, version and verification flags are user-supplied, not independently authenticated",
            "A successful tool read is not proof of the values asserted in the answer",
            "The absence of a write receipt does not independently audit the physical hub",
            "The answer, device identities, exact arguments, logs and private evidence are not exported",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="Registered Q1 read-only case ID")
    parser.add_argument("--receipt", type=Path, required=True, help="Private full technical JSON")
    parser.add_argument("--output", type=Path, help="Optional public-safe summary JSON")
    args = parser.parse_args(argv)
    result = intake(json.loads(args.receipt.read_text(encoding="utf-8")), args.case)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
