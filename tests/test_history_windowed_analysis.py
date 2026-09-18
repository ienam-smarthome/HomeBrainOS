from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_temporal_analysis import analyze_state_intervals_in_window  # noqa: E402


LOCAL = timezone(timedelta(hours=1))
START = datetime(2026, 9, 16, 18, 0, tzinfo=LOCAL)
END = datetime(2026, 9, 17, 8, 0, tzinfo=LOCAL)


def _event(value: str, timestamp: str, *, state_change: object = True) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": state_change,
    }


def test_predecessor_active_state_is_clipped_at_window_start() -> None:
    events = [
        _event("off", "2026-09-16T19:00:00+0100"),
        _event("on", "2026-09-16T17:30:00+0100"),
    ]

    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["totalActiveSeconds"] == 3600
    assert analysis["intervalCount"] == 1
    assert analysis["coverage"] == "complete"
    assert analysis["totalIsLowerBound"] is False
    assert analysis["boundaryBasis"] == "predecessor-event"
    assert analysis["intervals"][0]["clippedAtWindowStart"] is True
    assert analysis["intervals"][0]["start"] == START.isoformat()


def test_active_state_at_window_end_is_clipped_without_becoming_lower_bound() -> None:
    events = [
        _event("off", "2026-09-17T09:00:00+0100"),
        _event("on", "2026-09-17T07:00:00+0100"),
        _event("off", "2026-09-16T17:30:00+0100"),
    ]

    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["totalActiveSeconds"] == 3600
    assert analysis["coverage"] == "complete"
    assert analysis["totalIsLowerBound"] is False
    assert analysis["openActiveInterval"] is False
    assert analysis["intervals"][0]["clippedAtWindowEnd"] is True
    assert analysis["intervals"][0]["end"] == END.isoformat()


def test_complete_source_can_infer_boundary_state_from_first_transition() -> None:
    events = [_event("off", "2026-09-16T19:00:00+0100")]

    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["boundaryStateKnown"] is True
    assert analysis["boundaryBasis"] == "first-transition-inference"
    assert analysis["totalActiveSeconds"] == 3600
    assert analysis["coverage"] == "complete"


def test_truncated_source_does_not_invent_unknown_boundary_state() -> None:
    events = [_event("off", "2026-09-16T19:00:00+0100")]

    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=False,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["boundaryStateKnown"] is False
    assert analysis["boundaryBasis"] == "unknown"
    assert analysis["totalActiveSeconds"] == 0
    assert analysis["coverage"] == "partial"
    assert analysis["totalIsLowerBound"] is True


def test_big_lamp_style_window_keeps_only_requested_overnight_intervals() -> None:
    events = [
        _event("off", "2026-09-17T07:34:00.000+0100"),
        _event("on", "2026-09-17T04:56:00.000+0100"),
        _event("off", "2026-09-17T04:00:00.000+0100"),
        _event("on", "2026-09-17T03:49:00.000+0100"),
        _event("off", "2026-09-17T03:27:00.000+0100"),
        _event("on", "2026-09-17T03:00:00.100+0100"),
        _event("off", "2026-09-17T03:00:00.000+0100"),
        _event("on", "2026-09-17T02:37:00.000+0100"),
        _event("off", "2026-09-17T02:00:00.000+0100"),
        _event("on", "2026-09-17T01:08:00.000+0100"),
        _event("off", "2026-09-16T17:00:00.000+0100"),
    ]

    analysis = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
        source_integrity_verified=True,
    )

    assert analysis is not None
    assert analysis["windowed"] is True
    assert analysis["windowLabel"] == "last night"
    assert analysis["windowStart"] == START.isoformat()
    assert analysis["windowEnd"] == END.isoformat()
    assert analysis["intervalCount"] == 5
    assert analysis["totalActiveSeconds"] == 16260
    assert analysis["totalActiveDuration"] == "4h 31m"
    assert analysis["longestActiveDuration"] == "2h 38m"
    assert analysis["coverage"] == "complete"


def test_unsupported_attribute_still_has_no_synthetic_window_analysis() -> None:
    assert analyze_state_intervals_in_window(
        "temperature",
        [{"name": "temperature", "value": 21, "date": "2026-09-17T01:00:00+0100"}],
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
    ) is None
