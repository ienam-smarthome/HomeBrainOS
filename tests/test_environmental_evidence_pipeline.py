from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"

sys.path.insert(0, str(APP_DIR))

from environmental_insight_engine import (
    build_environmental_insights,
)


def test_environmental_issue_detection():

    result = build_environmental_insights(
        {
            "temperatures": [
                {
                    "device": "Livingroom FP300",
                    "room": "Livingroom",
                    "value": 29,
                }
            ],
            "humidities": [
                {
                    "device": "Bathroom Meter",
                    "room": "Bathroom",
                    "value": 53,
                }
            ],
        }
    )

    types = [
        item["type"]
        for item in result
    ]

    assert "thermal" in types
    assert "humidity" in types
