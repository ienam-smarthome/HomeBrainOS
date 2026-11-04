#!/usr/bin/env python3
"""Compare two live HomeBrain technical receipts without scoring model claims.

This is a Q1 performance and source-execution comparison. It intentionally
does NOT read/grade answer text, assert first-attempt quality or treat tool
success as proof of the answer's factual conclusions.

Usage:
  python scripts/answer_quality_live_receipt_diff.py \
    --before /private/v389.json --after /private/v390.json \
    --output /private/paired_receipt_metrics.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "homebrain-live-receipt-diff.v1"
_HASH = re.compile(r"^[0-9a-f]{64}$")


class LiveReceiptError(ValueError):
    """Receipt is malformed or insufficient for a safe comparison."""


def _nonnegative_number(value: Any, *, field: str) -> int | float:
    if (isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value < 10**12):
        raise LiveReceiptError(f"Invalid nonnegative numeric metric: {field}")
    return value


def _counter(metrics: dict[str, Any], name: str) -> int:
    raw = metrics.get("counters")
    if not isinstance(raw, dict):
        raise LiveReceiptError("Expected metrics.counters object")
    value = raw.get(name, 0)
    if type(value) is not int or not 0 <= value < 10**9:
        raise LiveReceiptError("Invalid counter: " + name)
    return value


def _timing(metrics: dict[str, Any], name: str) -> int | float:
    raw = metrics.get("timings_ms")
    if not isinstance(raw, dict) or name not in raw:
        raise LiveReceiptError("Missing timing: " + name)
    return _nonnegative_number(raw[name], field=name)


def _prompt_digest(receipt: dict[str, Any]) -> str | None:
    provenance = receipt.get("request_provenance")
    if not isinstance(provenance, dict):
        return None
    if (provenance.get("source") != "api_ask_request"
            or provenance.get("normalization") != "collapse-whitespace-v1"):
        return None
    value = provenance.get("normalized_prompt_sha256")
    return value if isinstance(value, str) and _HASH.fullmatch(value) else None


def _flag(receipt: dict[str, Any], name: str) -> bool:
    provenance = receipt.get("request_provenance")
    return isinstance(provenance, dict) and provenance.get(name) is True


def _arm(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise LiveReceiptError("Expected a HomeBrain JSON response object")
    metrics = receipt.get("metrics")
    evidence = receipt.get("evidence")
    if not isinstance(metrics, dict) or not isinstance(evidence, list):
        raise LiveReceiptError("Response requires metrics and evidence list")
    if any(not isinstance(row, dict) for row in evidence):
        raise LiveReceiptError("Malformed evidence receipt")
    if not isinstance(receipt.get("model"), str) or not receipt["model"]:
        raise LiveReceiptError("Missing model identity")
    if not isinstance(receipt.get("version"), str) or not receipt["version"]:
        raise LiveReceiptError("Missing add-on version")
    outcome = metrics.get("outcome")
    if outcome not in {"success", "unresolved", "failed", "refused", "cancelled", "needs_input"}:
        raise LiveReceiptError("Missing/unsupported request outcome")
    if type(receipt.get("success")) is not bool:
        raise LiveReceiptError("Missing API transport success flag")
    # An MCP source receipt can prove that a read was executed. It cannot,
    # without source values and scope review, prove any model-authored claim.
    completed_reads = sum(
        row.get("success") is True
        and row.get("mutates") is False
        and row.get("effect") == "read"
        for row in evidence
    )
    observed_writes = sum(
        row.get("mutates") is True or row.get("effect") in {
            "routine_write", "sensitive_write", "destructive_write", "write",
        }
        for row in evidence
    )
    return {
        "_model": receipt["model"],
        "_digest": _prompt_digest(receipt),
        "version": receipt["version"],
        "request_class": receipt.get("request_class"),
        "transport_success": receipt["success"],
        "outcome": outcome,
        "duration_ms": _timing(metrics, "total"),
        "provider_ms": _timing(metrics, "provider"),
        "model_rounds": _counter(metrics, "model_rounds"),
        "tool_calls_reported": _counter(metrics, "tool_calls"),
        "successful_read_receipts": completed_reads,
        "observed_write_receipts": observed_writes,
        "blocked_unauthorized_model_batches": _counter(
            metrics, "read_only_model_write_blocked"
        ),
        "recovery_view_activations": _counter(
            metrics, "read_only_write_recovery_view"
        ),
        "model_delivery_flag": _flag(receipt, "model_delivery_verified"),
        "first_attempt_flag": _flag(receipt, "first_attempt_verified"),
        "deployed_sha_flag": _flag(receipt, "deployed_build_sha_verified"),
    }


def compare_live_receipts(before: Any, after: Any) -> dict[str, Any]:
    """Return privacy-safe observed metrics; never copy prompt, answer or IDs."""
    old, new = _arm(before), _arm(after)
    same_hash = (old["_digest"] is not None
                 and old["_digest"] == new["_digest"])
    same_model = old["_model"] == new["_model"]
    same_class = (
        old["request_class"] == new["request_class"] == "live-read"
    )
    comparable = same_hash and same_model and same_class
    # Version strings are displayed only as bounded numeric release versions,
    # never as arbitrary user-controlled values.
    def safe_version(value: str) -> str | None:
        return value if re.fullmatch(r"[0-9]+(?:\.[0-9]+){2,3}", value) else None

    exposed = ("request_class", "transport_success", "outcome",
               "duration_ms", "provider_ms", "model_rounds",
               "tool_calls_reported", "successful_read_receipts",
               "observed_write_receipts", "blocked_unauthorized_model_batches",
               "recovery_view_activations", "model_delivery_flag",
               "first_attempt_flag", "deployed_sha_flag")
    def view(arm: dict[str, Any]) -> dict[str, Any]:
        return {"version": safe_version(arm["version"]),
                **{key: arm[key] for key in exposed}}

    delta = None
    if comparable:
        duration = old["duration_ms"]
        change = new["duration_ms"] - duration
        delta = {
            "duration_ms": change,
            "duration_reduction_percent": (
                round((duration - new["duration_ms"]) * 100 / duration, 1)
                if duration > 0 else None
            ),
            "provider_ms": new["provider_ms"] - old["provider_ms"],
            "model_rounds": new["model_rounds"] - old["model_rounds"],
            "tool_calls_reported": (
                new["tool_calls_reported"] - old["tool_calls_reported"]
            ),
            "successful_read_receipts": (
                new["successful_read_receipts"] - old["successful_read_receipts"]
            ),
            "blocked_unauthorized_model_batches": (
                new["blocked_unauthorized_model_batches"]
                - old["blocked_unauthorized_model_batches"]
            ),
        }
    reasons = []
    if not same_hash:
        reasons.append("api_prompt_digest_missing_or_different")
    if not same_model:
        reasons.append("model_identity_differs")
    if not same_class:
        reasons.append("not_two_live_read_requests")
    return {
        "schema": SCHEMA,
        "comparison": "same_api_prompt_and_model" if comparable else "not_comparable",
        "comparability_gaps": reasons,
        "api_prompt_digest_equal": same_hash,
        "api_prompt_identity_scope": (
            "api_boundary_only_not_proof_of_provider_delivery"
        ),
        "model_identity_equal": same_model,
        "before": view(old),
        "after": view(new),
        "observed_delta": delta,
        "observed_read_only_safety": (
            "no_write_receipts_in_supplied_trace"
            if old["observed_write_receipts"] == new["observed_write_receipts"] == 0
            else "write_receipt_present_or_unverified"
        ),
        "answer_claim_grounding": "not_measured",
        "question_resolution_verified": "not_measured",
        "first_attempt_accuracy": "not_measured",
        "sample_count": 1 if comparable else 0,
        "limitations": [
            "Metrics describe one pair, not latency medians, p95 or population accuracy",
            "Source tool execution is not proof of the model's claimed source values",
            "The API prompt digest does not authenticate delivery to the model",
            "User-supplied version and verification flags do not authenticate deployed Git SHA",
            "The absence of write receipts does not independently audit the physical hub",
            "Raw answer text, exact argument values, household identifiers and logs are omitted",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = compare_live_receipts(
        json.loads(args.before.read_text(encoding="utf-8")),
        json.loads(args.after.read_text(encoding="utf-8")),
    )
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
