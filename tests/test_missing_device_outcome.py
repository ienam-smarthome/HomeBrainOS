from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import resolve_device_candidate  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


def measured_resolution(requested: str, candidates: list[dict]) -> tuple[object, dict]:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        resolution = resolve_device_candidate(requested, candidates)
        snapshot = metrics.finish(metrics.completed_outcome())
    finally:
        metrics.reset(token)
    return resolution, snapshot


def test_empty_candidate_list_records_missing_unresolved() -> None:
    resolution, snapshot = measured_resolution("unknown device", [])

    assert resolution.target is None
    assert "No candidate matched" in resolution.reason
    assert snapshot["outcome"] == "unresolved"
    assert snapshot["counters"] == {"device_resolution_missing": 1}


def test_single_dissimilar_candidate_records_missing_not_ambiguous() -> None:
    resolution, snapshot = measured_resolution(
        "thermostat",
        [{"id": "1", "label": "Front Door Lock"}],
    )

    assert resolution.target is None
    assert "not similar enough" in resolution.reason
    assert snapshot["outcome"] == "unresolved"
    assert snapshot["counters"]["device_resolution_missing"] == 1
    assert "device_resolution_ambiguous" not in snapshot["counters"]


def test_successful_resolution_records_neither_missing_nor_ambiguous() -> None:
    resolution, snapshot = measured_resolution(
        "TV",
        [{"id": "1", "label": "TV"}],
    )

    assert resolution.target["id"] == "1"
    assert snapshot["outcome"] == "success"
    assert "device_resolution_missing" not in snapshot["counters"]
    assert "device_resolution_ambiguous" not in snapshot["counters"]


def test_missing_metric_is_presented_with_unresolved_outcome() -> None:
    rows = present_request_metrics({
        "outcome": "unresolved",
        "counters": {"device_resolution_missing": 1},
        "timings_ms": {"total": 250},
    })

    assert {"label": "Missing-device resolutions", "value": "1"} in rows
    assert {"label": "Outcome", "value": "unresolved"} in rows
