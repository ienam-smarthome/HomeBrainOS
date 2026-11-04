"""Q1 live paired diagnostics: metrics only, no fabricated answer score.

All input is synthetic. Tests never contact a hub, model or network.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "answer_quality_live_receipt_diff.py"
SPEC = importlib.util.spec_from_file_location("answer_quality_live_receipt_diff", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

compare_live_receipts = MODULE.compare_live_receipts
LiveReceiptError = MODULE.LiveReceiptError

HASH = "a" * 64


def receipt(version: str, *, hash_value: str = HASH, model: str = "mock-model",
            total: int = 25925, provider: int = 23042,
            rounds: int = 5, calls: int = 2, blocked: int = 2,
            recovery: int = 0, read_count: int = 2,
            outcome: str = "success"):
    return {
        "success": True,
        "request_class": "live-read",
        "model": model,
        "version": version,
        "message": (
            "A private family device at 192.168.1.200, token=not-to-publish. "
            "The model claims the switch turned OFF physically."
        ),
        "evidence": [
            {
                "tool": "hub_read_devices",
                "success": True,
                "mutates": False,
                "effect": "read",
                "arguments": {"args": {"labelFilter": "Family Device Private"}},
            }
            for _ in range(read_count)
        ],
        "metrics": {
            "outcome": outcome,
            "counters": {
                "model_rounds": rounds,
                "tool_calls": calls,
                "read_only_model_write_blocked": blocked,
                "read_only_write_recovery_view": recovery,
            },
            "timings_ms": {"total": total, "provider": provider},
        },
        "request_provenance": {
            "source": "api_ask_request",
            "normalization": "collapse-whitespace-v1",
            "normalized_prompt_sha256": hash_value,
            "model_delivery_verified": False,
            "first_attempt_verified": False,
            "deployed_build_sha_verified": False,
        },
    }


def test_same_api_prompt_reports_observed_deltas_without_claim_grading():
    before = receipt("0.18.389")
    after = receipt(
        "0.18.390", total=15168, provider=11238,
        rounds=4, calls=7, blocked=1, recovery=1, read_count=7,
        outcome="unresolved",
    )
    report = compare_live_receipts(before, after)
    assert report["comparison"] == "same_api_prompt_and_model"
    assert report["api_prompt_digest_equal"] is True
    assert report["sample_count"] == 1
    assert report["observed_delta"] == {
        "duration_ms": -10757,
        "duration_reduction_percent": 41.5,
        "provider_ms": -11804,
        "model_rounds": -1,
        "tool_calls_reported": 5,
        "successful_read_receipts": 5,
        "blocked_unauthorized_model_batches": -1,
    }
    assert report["before"]["outcome"] == "success"
    assert report["after"]["outcome"] == "unresolved"
    assert report["after"]["recovery_view_activations"] == 1
    assert report["answer_claim_grounding"] == "not_measured"
    assert report["first_attempt_accuracy"] == "not_measured"
    assert report["observed_read_only_safety"] == "no_write_receipts_in_supplied_trace"
    serialized = json.dumps(report)
    assert "192.168." not in serialized
    assert "Family Device" not in serialized
    assert "not-to-publish" not in serialized
    assert "switch turned OFF physically" not in serialized
    assert HASH not in serialized


@pytest.mark.parametrize(("change", "expected_gap"), [
    ({"hash_value": "b" * 64}, "api_prompt_digest_missing_or_different"),
    ({"hash_value": "malformed"}, "api_prompt_digest_missing_or_different"),
    ({"model": "other-model"}, "model_identity_differs"),
])
def test_different_or_unverified_identity_yields_no_before_after_delta(change, expected_gap):
    report = compare_live_receipts(
        receipt("0.18.389"), receipt("0.18.390", **change)
    )
    assert report["comparison"] == "not_comparable"
    assert report["observed_delta"] is None
    assert report["sample_count"] == 0
    assert expected_gap in report["comparability_gaps"]


def test_transport_success_is_distinct_from_answer_outcome():
    a = receipt("0.18.390", outcome="unresolved")
    assert a["success"] is True
    result = compare_live_receipts(receipt("0.18.389"), a)
    assert result["after"]["transport_success"] is True
    assert result["after"]["outcome"] == "unresolved"
    assert result["question_resolution_verified"] == "not_measured"


def test_missing_or_invalid_required_metric_is_rejected():
    a = receipt("0.18.389")
    a["metrics"]["timings_ms"]["total"] = -1
    with pytest.raises(LiveReceiptError, match="Invalid nonnegative"):
        compare_live_receipts(a, receipt("0.18.390"))
    b = receipt("0.18.390")
    b["metrics"]["counters"]["model_rounds"] = True
    with pytest.raises(LiveReceiptError, match="Invalid counter"):
        compare_live_receipts(receipt("0.18.389"), b)


def test_observed_write_evidence_is_not_silently_called_safe():
    after = receipt("0.18.390")
    after["evidence"].append({
        "success": True, "effect": "write", "mutates": True,
        "arguments": {"token": "secret"},
    })
    report = compare_live_receipts(receipt("0.18.389"), after)
    assert report["observed_read_only_safety"] == "write_receipt_present_or_unverified"
    assert report["after"]["observed_write_receipts"] == 1
    assert "secret" not in json.dumps(report)


def test_untrusted_version_is_never_published_in_comparison():
    report = compare_live_receipts(
        receipt("0.18.389"), receipt("private-token=123\n0.18.390")
    )
    assert report["after"]["version"] is None
    assert "private-token" not in json.dumps(report)


def test_missing_live_read_class_prevents_comparison():
    after = receipt("0.18.390")
    after["request_class"] = "write"
    report = compare_live_receipts(receipt("0.18.389"), after)
    assert report["comparison"] == "not_comparable"
    assert "not_two_live_read_requests" in report["comparability_gaps"]
