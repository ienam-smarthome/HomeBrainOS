from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import resolve_device_candidate  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def _measured_resolution(requested: str, candidates: list[dict]):
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        resolution = resolve_device_candidate(requested, candidates)
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)
    return resolution, snapshot


def test_ranked_ambiguity_records_one_metric() -> None:
    resolution, snapshot = _measured_resolution(
        "hallway light",
        [
            {"id": "1", "label": "Hallway Light 1"},
            {"id": "2", "label": "Hallway Light 2"},
        ],
    )

    assert resolution.target is None
    assert "ambiguous" in resolution.reason
    assert snapshot["counters"]["device_resolution_ambiguous"] == 1


def test_duplicate_exact_names_record_one_metric() -> None:
    resolution, snapshot = _measured_resolution(
        "TV",
        [
            {"id": "1", "label": "TV"},
            {"id": "2", "label": "TV"},
        ],
    )

    assert resolution.target is None
    assert "multiple devices exactly" in resolution.reason
    assert snapshot["counters"]["device_resolution_ambiguous"] == 1


def test_successful_and_missing_resolution_do_not_count_as_ambiguity() -> None:
    exact, exact_snapshot = _measured_resolution(
        "TV",
        [{"id": "1", "label": "TV"}],
    )
    missing, missing_snapshot = _measured_resolution("unknown", [])

    assert exact.target["id"] == "1"
    assert missing.target is None
    assert "device_resolution_ambiguous" not in exact_snapshot["counters"]
    assert "device_resolution_ambiguous" not in missing_snapshot["counters"]


def test_ambiguity_outside_request_context_is_ignored() -> None:
    metrics = RequestMetrics()

    resolve_device_candidate(
        "hallway light",
        [
            {"id": "1", "label": "Hallway Light 1"},
            {"id": "2", "label": "Hallway Light 2"},
        ],
    )

    assert metrics.snapshot()["counters"] == {}
