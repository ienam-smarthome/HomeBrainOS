from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"

sys.path.insert(0, str(APP_DIR))

from thermal_home_insight import build_thermal_insight  # noqa: E402


def test_livingroom_temperature_evidence():

    devices = [
        {
            "label": "Livingroom FP300",
            "attributes": {
                "temperature": 29.0
            }
        },
        {
            "label": "Livingroom TRV",
            "attributes": {
                "level": 70
            }
        },
    ]

    result = build_thermal_insight(
        devices,
        "Livingroom"
    )

    assert result["diagnosis_ready"] is True
    assert result["temperatures"][0]["temperature"] == 29.0
