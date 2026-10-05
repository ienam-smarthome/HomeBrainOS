from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_temporal_analysis import (
    analyze_state_intervals,
    analyze_state_intervals_in_window,
    guard_history_duration_claim,
    history_temporal_evidence_details,
)


def _switch(value: str, when: str, *, changed: bool = True) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": when,
        "isStateChange": changed,
    }


def test_non_windowed_open_interval_reports_elapsed_observed_span():
    analysis = analyze_state_intervals(
        "switch",
        [_switch("on", "2026-10-05T18:42:42.583+01:00")],
        as_of=datetime.fromisoformat("2026-10-05T18:44:00+01:00"),
    )

    assert analysis is not None
    assert analysis["intervalCount"] == 0
    assert analysis["completedIntervalCount"] == 0
    assert analysis["openIntervalCount"] == 1
    assert analysis["openActiveInterval"] is True
    assert analysis["openActiveSeconds"] == 77
    assert analysis["activeSecondsSoFar"] == 77
    assert analysis["openActiveDuration"] == "1m"
    assert analysis["activeDurationSoFar"] == "1m"
    # Completed-pair totals remain distinct for compatibility/auditability.
    assert analysis["totalActiveSeconds"] == 0


def test_unverified_window_open_transition_keeps_open_span_separate_from_total():
    analysis = analyze_state_intervals_in_window(
        "switch",
        [_switch("on", "2026-10-05T18:42:42.583+01:00")],
        start=datetime.fromisoformat("2026-10-05T18:00:00+01:00"),
        end=datetime.fromisoformat("2026-10-05T18:44:00+01:00"),
        window_label="this evening",
        source_complete_to_start=True,
        window_ongoing=True,
        source_integrity_verified=False,
    )

    assert analysis is not None
    assert analysis["intervalCount"] == 0
    assert analysis["totalActiveSeconds"] == 0
    assert analysis["openActiveInterval"] is True
    assert analysis["openActiveSeconds"] == 77
    assert analysis["activeSecondsSoFar"] == 77
    assert analysis["openActiveStartedBeforeWindow"] is False
    assert analysis["openActiveStart"].startswith("2026-10-05T18:42:42.583")


def test_verified_predecessor_marks_open_state_as_already_active_at_window_start():
    analysis = analyze_state_intervals_in_window(
        "switch",
        [_switch("on", "2026-10-05T18:00:00+01:00")],
        start=datetime.fromisoformat("2026-10-05T18:30:00+01:00"),
        end=datetime.fromisoformat("2026-10-05T18:44:00+01:00"),
        window_label="the requested window",
        source_complete_to_start=True,
        window_ongoing=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["boundaryBasis"] == "predecessor-event"
    assert analysis["openActiveStartedBeforeWindow"] is True
    assert analysis["openActiveEffectiveStart"].startswith("2026-10-05T18:30:00")
    assert analysis["openActiveSeconds"] == 14 * 60
    assert analysis["activeSecondsSoFar"] == 14 * 60


def test_guard_preserves_observed_open_on_fact_instead_of_saying_no_bounded_interval():
    evidence = [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": {
                "label": "Bathroom Light 1",
                "historySourceIntegrity": "unverified",
                "historySourceIntegrityVerified": False,
                "temporalAnalysis": {
                    "activeState": "on",
                    "inactiveState": "off",
                    "totalActiveSeconds": 0,
                    "totalActiveDuration": "0s",
                    "intervalCount": 0,
                    "openActiveInterval": True,
                    "unboundedActiveInterval": True,
                    "openActiveStart": "2026-10-05T18:42:42.583+01:00",
                    "openActiveStartNatural": "6:42 pm on Monday 5 October 2026",
                    "openActiveSeconds": 77,
                    "openActiveDuration": "1m",
                    "durationReliability": "observed-open-span",
                },
            },
        }
    ]

    corrected, changed = guard_history_duration_claim(
        "Bathroom Light 1 was on continuously for 1 minute.",
        evidence,
    )

    assert changed is True
    assert "switched on at 6:42 pm" in corrected
    assert "No subsequent off event was found" in corrected
    assert "observed open span of about 1m" in corrected
    assert "No bounded on interval" not in corrected
    assert "not been independently verified as complete" in corrected


def test_evidence_details_retain_open_span_fields_for_final_synthesis():
    details = history_temporal_evidence_details(
        {
            "label": "Bathroom Light 1",
            "attribute": "switch",
            "hoursBack": 168,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "events": [_switch("on", "2026-10-05T18:42:42.583+01:00")],
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveSeconds": 0,
                "totalActiveDuration": "0s",
                "completedActiveSeconds": 0,
                "completedActiveDuration": "0s",
                "openActiveSeconds": 77,
                "openActiveDuration": "1m",
                "activeSecondsSoFar": 77,
                "activeDurationSoFar": "1m",
                "intervalCount": 0,
                "completedIntervalCount": 0,
                "openIntervalCount": 1,
                "openActiveInterval": True,
                "unboundedActiveInterval": True,
                "openActiveStart": "2026-10-05T18:42:42.583+01:00",
                "openActiveStartNatural": "6:42 pm on Monday 5 October 2026",
                "intervals": [],
            },
        }
    )

    assert details is not None
    temporal = details["temporalAnalysis"]
    assert temporal["openActiveSeconds"] == 77
    assert temporal["activeSecondsSoFar"] == 77
    assert temporal["openIntervalCount"] == 1
