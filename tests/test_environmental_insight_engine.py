from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"

sys.path.insert(0, str(APP_DIR))

from environmental_insight_engine import build_environmental_insights


def test_hot_room_reasoning():

    result = build_environmental_insights(
        {
            "temperatures": [
                {
                    "device": "Livingroom FP300",
                    "room": "Livingroom",
                    "value": 29,
                }
            ]
        }
    )

    assert result[0]["type"] == "thermal"


def test_high_humidity_reasoning():

    result = build_environmental_insights(
        {
            "humidities": [
                {
                    "device": "Bathroom Meter",
                    "room": "Bathroom",
                    "value": 53,
                }
            ]
        }
    )

    assert result[0]["type"] == "humidity"
