from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_ambiguous_device_soak import validate_ambiguous_device_result  # noqa: E402


def result(*, outcome: str = "unresolved", counter: int = 1) -> dict:
    return {
        "success": True,
        "message": "The device name is ambiguous.",
        "evidence": [
            {
                "tool": "homebrain_resolve_device",
                "success": True,
                "mutates": False,
                "effect": "read",
            }
        ],
        "metrics": {
            "outcome": outcome,
            "counters": {"device_resolution_ambiguous": counter},
            "timings_ms": {"total": 120},
        },
        "metric_rows": [
            {"label": "Ambiguous resolutions", "value": str(counter)},
            {"label": "Outcome", "value": outcome},
        ],
    }


def test_accepts_unresolved_ambiguous_device_result() -> None:
    assert validate_ambiguous_device_result(result()) == []


def test_rejects_success_outcome() -> None:
    errors = validate_ambiguous_device_result(result(outcome="success"))
    assert "expected unresolved outcome, got 'success'" in errors


def test_requires_ambiguity_counter() -> None:
    errors = validate_ambiguous_device_result(result(counter=0))
    assert "ambiguous resolution counter was not recorded" in errors


def test_requires_resolver_evidence() -> None:
    payload = result()
    payload["evidence"] = []
    errors = validate_ambiguous_device_result(payload)
    assert "homebrain_resolve_device evidence is missing" in errors


def test_rejects_mutating_evidence() -> None:
    payload = result()
    payload["evidence"][0]["mutates"] = True
    payload["evidence"][0]["effect"] = "write"
    errors = validate_ambiguous_device_result(payload)
    assert "ambiguous-device probe attempted a mutation" in errors


def test_reuses_privacy_safe_metrics_validation() -> None:
    payload = result()
    payload["metrics"]["device_name"] = "Bedroom Light"
    errors = validate_ambiguous_device_result(payload)
    assert any("privacy-sensitive metric key" in error for error in errors)
