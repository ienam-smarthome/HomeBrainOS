from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from device_history_service import DeviceHistoryService  # noqa: E402


@dataclass
class FakeOutcome:
    message: str
    evidence: list[dict[str, Any]]
    request_class: str = "live-read"
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    automation_items: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "outcome": "success",
            "counters": {"model_rounds": 2},
            "timings_ms": {},
        }
    )


def _zero_motion_receipt() -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bedroom 3 Sensor T1",
            "attribute": "motion",
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "activeState": "active",
                "inactiveState": "inactive",
                "intervalCount": 0,
                "totalActiveDuration": "0s",
                "totalActiveSeconds": 0,
                "coverage": "partial",
                "durationReliability": "unverified-event-stream",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "windowLabel": "last night",
            },
        },
    }


def test_t1_motion_is_rejected_when_target_advertises_illuminance_not_motion() -> None:
    target = {
        "label": "Bedroom 3 Sensor T1",
        "attributes": {"illuminance": 124, "temperature": 22.0},
        "capabilities": ["IlluminanceMeasurement", "TemperatureMeasurement"],
    }

    rejection = DeviceHistoryService._unsupported_history_attribute(target, "motion")

    assert rejection is not None
    assert rejection["unsupportedAttribute"] == "motion"
    assert rejection["availableAttributes"] == ["illuminance", "temperature"]


def test_t1_illuminance_is_allowed() -> None:
    target = {
        "label": "Bedroom 3 Sensor T1",
        "attributes": {"illuminance": 124, "temperature": 22.0},
        "capabilities": ["IlluminanceMeasurement", "TemperatureMeasurement"],
    }

    assert DeviceHistoryService._unsupported_history_attribute(target, "illuminance") is None


def test_motion_capability_allows_motion_even_without_current_attribute_key() -> None:
    target = {
        "label": "Soft Sensor",
        "attributes": {"temperature": 21.0},
        "capabilities": ["MotionSensor", "TemperatureMeasurement"],
    }

    assert DeviceHistoryService._unsupported_history_attribute(target, "motion") is None


def test_unknown_custom_history_attribute_is_not_rejected() -> None:
    target = {
        "label": "Custom Device",
        "attributes": {"temperature": 21.0},
        "capabilities": ["Sensor"],
    }

    assert DeviceHistoryService._unsupported_history_attribute(target, "customState") is None


def test_unverified_no_motion_events_recorded_wording_is_rewritten() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "The light history is established. "
                "No motion events were recorded for the Bedroom 3 Sensor T1 during this window."
            ),
            evidence=[_zero_motion_receipt()],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.464",
    )

    assert "No bounded active interval was established for Bedroom 3 Sensor T1" in response["message"]
    assert "does not prove it stayed inactive" in response["message"]
    assert "No motion events were recorded" not in response["message"]
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True
