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
        "room": None,
        "matchBasis": None,
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


def test_room_controller_candidates_include_label_affinity_when_room_missing() -> None:
    devices = [
        {
            "id": "10",
            "label": "Bedroom 3 Dimmer",
            "capabilities": ["PushableButton"],
        },
        {
            "id": "11",
            "label": "Bedroom 2 Dimmer",
            "capabilities": ["PushableButton"],
        },
        {
            "id": "12",
            "label": "Remote",
            "room": "Bedroom 3",
            "capabilities": ["PushableButton"],
        },
        {
            "id": "13",
            "label": "Bedroom 3 Sensor T1",
            "capabilities": ["IlluminanceMeasurement"],
        },
    ]

    candidates = DeviceQueryService._room_controller_candidates(devices, "Bedroom 3")

    assert [item["label"] for item in candidates] == [
        "Remote",
        "Bedroom 3 Dimmer",
    ]
    assert candidates[0]["matchBasis"] == "room"
    assert candidates[1]["matchBasis"] == "label-affinity"


def test_room_controller_candidates_do_not_use_label_affinity_without_button_capability() -> None:
    devices = [{
        "id": "20",
        "label": "Bedroom 3 Sensor",
        "capabilities": ["MotionSensor"],
    }]

    assert DeviceQueryService._room_controller_candidates(devices, "Bedroom 3") == []
