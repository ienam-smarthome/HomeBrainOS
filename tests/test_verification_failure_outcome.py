from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_metrics import RequestMetrics  # noqa: E402


def _finish_with(*counters: str) -> dict[str, object]:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        for counter in counters:
            metrics.increment(counter)
        return metrics.finish(metrics.completed_outcome())
    finally:
        metrics.reset(token)


def test_verification_failure_finishes_as_failed() -> None:
    snapshot = _finish_with("mutation_verification_failures")

    assert snapshot["outcome"] == "failed"
    assert snapshot["counters"] == {"mutation_verification_failures": 1}


def test_grounding_refusal_keeps_precedence() -> None:
    snapshot = _finish_with(
        "mutation_verification_failures",
        "grounding_refusals",
    )

    assert snapshot["outcome"] == "refused"


def test_verification_failure_precedes_unresolved() -> None:
    snapshot = _finish_with(
        "device_resolution_ambiguous",
        "mutation_verification_failures",
    )

    assert snapshot["outcome"] == "failed"


def test_normal_completion_remains_success() -> None:
    snapshot = _finish_with()

    assert snapshot["outcome"] == "success"
