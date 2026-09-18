from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402


def test_controller_hints_prefer_button_capabilities_not_environmental_sensors() -> None:
    matches = [
        {
            "id": "1",
            "label": "Bedroom 3 Dimmer",
            "capabilities": [
                "PushableButton",
                "HoldableButton",
                "DoubleTapableButton",
                "Battery",
            ],
        },
        {
            "id": "2",
            "label": "Bedroom 3 Sensor T1",
            "capabilities": ["IlluminanceMeasurement", "TemperatureMeasurement"],
        },
        {
            "id": "3",
            "label": "Bedroom 3 Soft Sensor",
            "capabilities": ["MotionSensor"],
        },
    ]

    hints = DeviceQueryService._controller_event_source_hints(matches)

    assert [item["label"] for item in hints] == ["Bedroom 3 Dimmer"]
    assert hints[0]["suggestedHistoryAttributes"] == [
        "pushed",
        "held",
        "doubleTapped",
    ]


def test_plain_button_capability_gets_pushed_history_hint() -> None:
    hints = DeviceQueryService._controller_event_source_hints([
        {
            "id": "9",
            "label": "Simple Button",
            "capabilities": ["Button"],
        }
    ])

    assert hints == [{
        "id": "9",
        "label": "Simple Button",
        "capabilities": ["Button"],
        "suggestedHistoryAttributes": ["pushed"],
    }]


def test_controller_hints_are_bounded() -> None:
    matches = [
        {
            "id": str(index),
            "label": f"Button {index}",
            "capabilities": ["PushableButton"],
        }
        for index in range(12)
    ]

    hints = DeviceQueryService._controller_event_source_hints(matches)

    assert len(hints) == 8
