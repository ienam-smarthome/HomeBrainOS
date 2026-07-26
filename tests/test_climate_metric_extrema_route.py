from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from climate_metric_extrema_route import select_metric_extreme


def test_highest_humidity_uses_verified_reading_and_room():
    selected = select_metric_extreme(
        [
            {"label": "Bathroom Meter", "room": "Bathroom", "value": 47},
            {"label": "Hallway Meter", "room": "Hallway", "value": 43},
        ],
        metric="humidity",
        direction="max",
    )

    assert selected is not None
    assert selected["label"] == "Bathroom Meter"
    assert selected["room"] == "Bathroom"
    assert selected["value"] == 47.0


def test_invalid_humidity_and_aggregate_rows_are_ignored():
    selected = select_metric_extreme(
        [
            {"label": "Invented aggregate", "room": "Garage", "value": 74, "aggregate": True},
            {"label": "Invalid sensor", "room": "Nowhere", "value": 140},
            {"label": "Bathroom Meter", "room": "Bathroom", "value": 47},
        ],
        metric="humidity",
        direction="max",
    )

    assert selected is not None
    assert selected["label"] == "Bathroom Meter"
    assert selected["room"] == "Bathroom"
