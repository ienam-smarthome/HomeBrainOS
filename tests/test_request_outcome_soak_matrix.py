from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_outcome  # noqa: E402


@pytest.mark.parametrize(
    ("counter", "expected_outcome", "expected_label", "expected_tone"),
    [
        (None, "success", "Success", "positive"),
        ("device_resolution_ambiguous", "unresolved", "Unresolved", "warning"),
        ("device_resolution_missing", "unresolved", "Unresolved", "warning"),
        ("grounding_refusals", "refused", "Refused", "warning"),
        ("mutation_verification_failures", "failed", "Failed", "critical"),
        ("confirmation_expired", "unresolved", "Unresolved", "warning"),
        ("request_cancellations", "cancelled", "Cancelled", "neutral"),
    ],
)
def test_completed_request_outcome_soak_matrix(
    counter: str | None,
    expected_outcome: str,
    expected_label: str,
    expected_tone: str,
) -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        if counter is not None:
            metrics.increment(counter)

        outcome = metrics.completed_outcome()
        snapshot = metrics.finish(outcome)
        presentation = present_request_outcome(snapshot["outcome"])

        assert snapshot["outcome"] == expected_outcome
        assert presentation == {
            "value": expected_outcome,
            "label": expected_label,
            "tone": expected_tone,
        }
    finally:
        metrics.reset(token)


def test_outcome_precedence_is_stable_when_multiple_failures_are_recorded() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("device_resolution_missing")
        metrics.increment("request_cancellations")
        metrics.increment("mutation_verification_failures")
        metrics.increment("grounding_refusals")

        assert metrics.completed_outcome() == "refused"
    finally:
        metrics.reset(token)


def test_verification_failure_precedes_cancellation_and_unresolved() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("confirmation_expired")
        metrics.increment("request_cancellations")
        metrics.increment("mutation_verification_failures")

        assert metrics.completed_outcome() == "failed"
    finally:
        metrics.reset(token)


def test_cancellation_precedes_unresolved_resolution_failures() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("device_resolution_ambiguous")
        metrics.increment("device_resolution_missing")
        metrics.increment("confirmation_expired")
        metrics.increment("request_cancellations")

        assert metrics.completed_outcome() == "cancelled"
    finally:
        metrics.reset(token)
