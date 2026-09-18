from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from location_correlation import nearest_location_correlations  # noqa: E402


def _evidence() -> list[dict[str, Any]]:
    newer = [
        {
            "name": "mode",
            "value": f"Newer {index}",
            "date": f"2026-09-18T0{8-index}:00:00+01:00",
            "isStateChange": True,
        }
        for index in range(6)
    ]
    return [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "evidence_kind": "deterministic_device_event_history",
            "details": {
                "label": "Bedroom 3 Light",
                "attribute": "switch",
                "temporalAnalysis": {
                    "activeState": "on",
                    "intervalCount": 1,
                    "totalActiveDuration": "1h 27m",
                    "durationReliability": "unverified-event-stream",
                    "observedIntervals": [{
                        "start": "2026-09-18T00:02:53.713+01:00",
                        "end": "2026-09-18T01:30:07.971+01:00",
                        "duration": "1h 27m",
                    }],
                },
            },
        },
        {
            "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "success": True,
            "evidence_kind": "authoritative_location_event_history",
            "details": {
                "count": 8,
                "events": [
                    *newer,
                    {
                        "name": "mode",
                        "value": "Late Night",
                        "date": "2026-09-18T01:30:02.403+01:00",
                        "isStateChange": True,
                    },
                    {
                        "name": "mode",
                        "value": "Night",
                        "date": "2026-09-17T23:00:03.946+01:00",
                        "isStateChange": True,
                    },
                ],
            },
        },
    ]


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
            "counters": {"model_rounds": 3},
            "timings_ms": {},
        }
    )


def test_nearest_location_correlation_finds_late_night_transition() -> None:
    matches = nearest_location_correlations(_evidence(), max_delta_seconds=15.0)

    assert matches
    assert matches[0]["eventValue"] == "Late Night"
    assert matches[0]["subjectTransition"] == "ended"
    assert 5.0 < matches[0]["deltaSeconds"] < 6.0


def test_ledger_prioritizes_transition_near_event_over_newest_six() -> None:
    ledger = build_current_turn_evidence_ledger(_evidence())

    assert ledger is not None
    assert "NEAR SUBJECT TRANSITION" in ledger
    assert "mode=Late Night" in ledger


def test_false_no_mode_correlation_is_corrected_at_serialization() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "The location and mode history does not show a mode change or "
                "event that correlates with these specific transitions."
            ),
            evidence=_evidence(),
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.465",
    )

    assert "does contain a close temporal correlation" in response["message"]
    assert "mode=Late Night" in response["message"]
    assert "does not by itself establish causation" in response["message"]


def test_no_correlation_guard_when_location_event_is_not_close() -> None:
    evidence = _evidence()
    evidence[1]["details"]["events"][-2]["date"] = "2026-09-18T01:29:00+01:00"

    response = build_agent_response(
        FakeOutcome(
            message=(
                "The location and mode history does not show a mode change or "
                "event that correlates with these specific transitions."
            ),
            evidence=evidence,
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.465",
    )

    assert "does not show a mode change" in response["message"]
