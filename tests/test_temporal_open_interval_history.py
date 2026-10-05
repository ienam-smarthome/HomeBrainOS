from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_temporal_analysis import (  # noqa: E402
    analyze_state_intervals,
    analyze_state_intervals_in_window,
    boundary_event_evidence,
    guard_history_duration_claim,
    history_temporal_evidence_details,
)


def _event(value: str, timestamp: str, *, state_change: object = True) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": state_change,
    }


def test_open_switch_transition_is_exposed_as_observed_unbounded_interval() -> None:
    analysis = analyze_state_intervals(
        "switch",
        [_event("on", "2026-10-05T18:42:42.583+0100")],
    )

    assert analysis is not None
    assert analysis["intervalCount"] == 0
    assert analysis["totalActiveSeconds"] == 0
    assert analysis["openIntervalCount"] == 1
    assert analysis["unboundedActiveInterval"] is True
    assert analysis["openActiveInterval"] is True
    assert analysis["openActiveStartObserved"] is True
    assert analysis["openActiveStart"] == "2026-10-05T18:42:42.583+0100"


def test_unverified_open_transition_guard_preserves_observed_on_fact() -> None:
    analysis = analyze_state_intervals(
        "switch",
        [_event("on", "2026-10-05T18:42:42.583+0100")],
    )
    assert analysis is not None
    details = history_temporal_evidence_details(
        {
            "success": True,
            "label": "Bathroom Light 1",
            "attribute": "switch",
            "hoursBack": 168,
            "temporalAnalysis": analysis,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
        }
    )
    assert details is not None

    message, applied = guard_history_duration_claim(
        "Bathroom Light 1 was on continuously for 2 minutes.",
        [{"tool": "homebrain_device_history", "success": True, "details": details}],
    )

    assert applied is True
    assert (
        "Bathroom Light 1 has a recorded on transition at 6:42 pm on Monday 5 October 2026"
        in message
    )
    assert "with no subsequent off transition in the returned history" in message
    assert "does not prove uninterrupted activity" in message
    assert "device's current state" in message
    assert "No bounded on interval" not in message
    assert "stayed off" not in message


def test_pre_window_active_state_is_clipped_but_not_relabelled_as_observed_transition() -> None:
    events = [_event("on", "2026-10-05T17:30:00.000+0100")]
    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=datetime.fromisoformat("2026-10-05T18:00:00+01:00"),
        end=datetime.fromisoformat("2026-10-05T19:00:00+01:00"),
        window_label="during the requested window",
        source_complete_to_start=True,
        window_ongoing=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["unboundedActiveInterval"] is True
    assert analysis["openActiveStartObserved"] is False
    assert analysis["openActiveStart"] == "2026-10-05T18:00:00+01:00"
    assert analysis["intervals"][0]["clippedAtWindowStart"] is True
    assert analysis["intervals"][0]["clippedAtWindowEnd"] is True


def test_clipped_window_boundaries_are_not_used_as_event_provenance() -> None:
    events = [
        _event("on", "2026-10-05T17:30:00.000+0100"),
        {
            "name": "command-on",
            "value": "on",
            "date": "2026-10-05T18:00:03.000+0100",
            "isStateChange": True,
        },
    ]
    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=datetime.fromisoformat("2026-10-05T18:00:00+01:00"),
        end=datetime.fromisoformat("2026-10-05T19:00:00+01:00"),
        window_label="during the requested window",
        source_complete_to_start=True,
        window_ongoing=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert boundary_event_evidence(events, analysis) == []
