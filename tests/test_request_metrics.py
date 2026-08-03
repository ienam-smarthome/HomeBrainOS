from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_metrics import RequestMetrics  # noqa: E402


def test_request_metrics_collect_only_fixed_privacy_safe_keys() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("model_rounds")
        metrics.increment("tool_calls", 2)
        metrics.observe_ms("provider", 12.6)
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["outcome"] == "success"
    assert snapshot["counters"] == {"model_rounds": 1, "tool_calls": 2}
    assert snapshot["timings_ms"]["provider"] == 13
    assert snapshot["timings_ms"]["total"] >= 0


def test_request_metrics_reject_dynamic_or_private_labels() -> None:
    metrics = RequestMetrics()

    with pytest.raises(ValueError, match="Unsupported metric counter"):
        metrics.increment("Bedroom 1 Light")
    with pytest.raises(ValueError, match="Unsupported metric timing"):
        metrics.observe_ms("hubitat_token", 1)
    with pytest.raises(ValueError, match="Unsupported request outcome"):
        metrics.finish("device-name")


def test_request_metrics_are_isolated_and_resettable() -> None:
    metrics = RequestMetrics()
    first = metrics.begin()
    metrics.increment("tool_calls")
    first_snapshot = metrics.snapshot()
    metrics.reset(first)

    second = metrics.begin()
    try:
        second_snapshot = metrics.snapshot()
    finally:
        metrics.reset(second)

    assert first_snapshot["counters"] == {"tool_calls": 1}
    assert second_snapshot == {"outcome": None, "counters": {}, "timings_ms": {}}


def test_request_metrics_ignore_events_outside_request_context() -> None:
    metrics = RequestMetrics()

    metrics.increment("request_cancellations")
    metrics.observe_ms("mcp", 20)

    assert metrics.snapshot() == {"outcome": None, "counters": {}, "timings_ms": {}}


def test_expired_confirmation_finishes_unresolved() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("confirmation_expired")
        outcome = metrics.completed_outcome()
        snapshot = metrics.finish(outcome)
    finally:
        metrics.reset(token)

    assert outcome == "unresolved"
    assert snapshot["outcome"] == "unresolved"
    assert snapshot["counters"]["confirmation_expired"] == 1


def test_refusal_and_verification_failure_precede_expired_confirmation() -> None:
    metrics = RequestMetrics()

    refused = metrics.begin()
    try:
        metrics.increment("confirmation_expired")
        metrics.increment("grounding_refusals")
        assert metrics.completed_outcome() == "refused"
    finally:
        metrics.reset(refused)

    failed = metrics.begin()
    try:
        metrics.increment("confirmation_expired")
        metrics.increment("mutation_verification_failures")
        assert metrics.completed_outcome() == "failed"
    finally:
        metrics.reset(failed)
