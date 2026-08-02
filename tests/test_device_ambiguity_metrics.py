from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import resolve_device_candidate  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def test_ranked_ambiguity_increments_request_metric() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        resolution = resolve_device_candidate(
            "hallway light",
            [
                {"id": "1", "label": "Hallway Light 1"},
                {"id": "2", "label": "Hallway Light 2"},
            ],
        )
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert resolution.target is None
    assert snapshot["counters"]["device_resolution_ambiguous"] == 1


def test_duplicate_exact_labels_increment_request_metric() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        resolution = resolve_device_candidate(
            "TV",
            [
                {"id": "1", "label": "TV"},
                {"id": "2", "label": "TV"},
            ],
        )
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert resolution.target is None
    assert snapshot["counters"]["device_resolution_ambiguous"] == 1


def test_no_match_and_unique_match_are_not_counted_as_ambiguity() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        no_match = resolve_device_candidate("missing", [])
        unique = resolve_device_candidate(
            "Bedroom Light",
            [{"id": "1", "label": "Bedroom Light"}],
        )
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert no_match.target is None
    assert unique.target is not None
    assert "device_resolution_ambiguous" not in snapshot["counters"]


def test_ambiguity_outside_active_request_is_ignored() -> None:
    metrics = RequestMetrics()

    resolve_device_candidate(
        "hallway light",
        [
            {"id": "1", "label": "Hallway Light 1"},
            {"id": "2", "label": "Hallway Light 2"},
        ],
    )

    assert metrics.snapshot()["counters"] == {}
