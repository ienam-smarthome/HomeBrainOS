from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"

sys.path.insert(0, str(APP_DIR))

from humidity_home_insight import build_humidity_insight


def test_bathroom_humidity_evidence():

    devices = [
        {
            "label": "Bathroom Meter",
            "attributes": {
                "humidity": 53
            }
        },
        {
            "label": "Bathroom Fan",
            "capabilities": [
                "Switch"
            ],
        },
    ]

    result = build_humidity_insight(
        devices,
        "Bathroom"
    )

    assert result["diagnosis_ready"] is True
    assert result["humidity"][0]["humidity"] == 53
