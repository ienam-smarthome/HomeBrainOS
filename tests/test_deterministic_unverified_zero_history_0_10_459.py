from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402


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
            "counters": {"model_rounds": 2, "tool_calls": 1},
            "timings_ms": {"total": 10},
        }
    )


def _receipt(
    *,
    intervals: int = 0,
    integrity_verified: bool = False,
    reliability: str = "unverified-event-stream",
) -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Hallway Light 1",
            "attribute": "switch",
            "historySourceIntegrity": (
                "verified" if integrity_verified else "unverified"
            ),
            "historySourceIntegrityVerified": integrity_verified,
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveDuration": "0s" if intervals == 0 else "8m",
                "totalActiveSeconds": 0 if intervals == 0 else 480,
                "intervalCount": intervals,
                "longestActiveDuration": "0s" if intervals == 0 else "3m",
                "longestActiveSeconds": 0 if intervals == 0 else 180,
                "coverage": "partial" if not integrity_verified else "complete",
                "totalIsLowerBound": False,
                "durationReliability": reliability,
                "sourceIntegrity": (
                    "verified" if integrity_verified else "unverified"
                ),
                "sourceIntegrityVerified": integrity_verified,
                "windowed": True,
                "windowLabel": "last night",
                "boundaryStateKnown": False if not integrity_verified else True,
                "boundaryBasis": (
                    "source-integrity-unverified"
                    if not integrity_verified
                    else "predecessor-event"
                ),
            },
        },
    }


def _response(message: str, receipt: dict[str, Any]) -> dict[str, Any]:
    return build_agent_response(
        FakeOutcome(message=message, evidence=[receipt]),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.459",
    )


def test_zero_unverified_history_ignores_phrase_variant_and_serializes_safe_answer() -> None:
    response = _response(
        (
            "Based on the device history for Hallway Light 1, there is no record "
            "of it being on during the night (between 6:00 PM yesterday and "
            "8:00 AM this morning). All recorded activity occurred this morning "
            "starting after 9:23 AM."
        ),
        _receipt(),
    )

    assert response["message"] == (
        "No bounded on interval was established for Hallway Light 1 during last "
        "night from the recorded device-event rows. The event stream has not been "
        "independently verified as complete, so this does not prove it stayed off "
        "throughout that window."
    )
    assert "9:23" not in response["message"]
    assert "no record of it being on" not in response["message"].casefold()
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_zero_unverified_history_replaces_even_without_known_absence_wording() -> None:
    response = _response(
        "Hallway Light 1 only became active after breakfast.",
        _receipt(),
    )

    assert response["message"].startswith("No bounded on interval was established")
    assert "only became active" not in response["message"]
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_nonzero_unverified_history_is_not_forced_through_zero_serializer() -> None:
    message = "Hallway Light 1 has several recorded switch intervals."
    response = _response(message, _receipt(intervals=3))

    assert response["message"] == message
    assert (
        "finalAnswerCorrectionApplied"
        not in response["evidence"][0]["details"]
    )


def test_verified_zero_history_does_not_use_unverified_zero_serializer() -> None:
    message = "Hallway Light 1 was off throughout last night."
    response = _response(
        message,
        _receipt(integrity_verified=True, reliability="exact"),
    )

    assert response["message"] == message
    assert (
        "finalAnswerCorrectionApplied"
        not in response["evidence"][0]["details"]
    )
