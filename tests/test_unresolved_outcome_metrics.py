from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


def test_ambiguous_resolution_finishes_as_unresolved() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("device_resolution_ambiguous")
        snapshot = metrics.finish(metrics.completed_outcome())
    finally:
        metrics.reset(token)

    assert snapshot["outcome"] == "unresolved"
    assert snapshot["counters"] == {"device_resolution_ambiguous": 1}


def test_grounding_refusal_takes_precedence_over_unresolved() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("device_resolution_ambiguous")
        metrics.increment("grounding_refusals")
        snapshot = metrics.finish(metrics.completed_outcome())
    finally:
        metrics.reset(token)

    assert snapshot["outcome"] == "refused"


def test_normal_completion_remains_success() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        snapshot = metrics.finish(metrics.completed_outcome())
    finally:
        metrics.reset(token)

    assert snapshot["outcome"] == "success"


def test_presenter_accepts_unresolved_outcome() -> None:
    rows = present_request_metrics({
        "outcome": "unresolved",
        "counters": {"device_resolution_ambiguous": 1},
        "timings_ms": {"total": 250},
    })

    assert {"label": "Ambiguous resolutions", "value": "1"} in rows
    assert {"label": "Outcome", "value": "unresolved"} in rows


def test_dynamic_outcome_values_are_not_presented() -> None:
    rows = present_request_metrics({
        "outcome": "Bathroom Meter",
        "counters": {},
        "timings_ms": {},
    })

    assert rows == []
