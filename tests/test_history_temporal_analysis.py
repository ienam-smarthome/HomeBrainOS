from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_temporal_analysis import analyze_state_intervals  # noqa: E402


def _event(value: str, timestamp: str, *, state_change: object = True) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": state_change,
    }


def test_big_lamp_history_pairs_intervals_and_totals_without_model_math() -> None:
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
    ]

    analysis = analyze_state_intervals("switch", events)

    assert analysis is not None
    assert analysis["intervalCount"] == 5
    assert analysis["totalActiveSeconds"] == 16260
    assert analysis["totalActiveDuration"] == "4h 31m"
    assert analysis["longestActiveSeconds"] == 9480
    assert analysis["longestActiveDuration"] == "2h 38m"
    assert analysis["coverage"] == "complete"
    assert analysis["totalIsLowerBound"] is False
    assert analysis["continuous"] is False
    assert [row["duration"] for row in analysis["intervals"]] == [
        "52m",
        "23m",
        "27m",
        "11m",
        "2h 38m",
    ]


def test_equal_timestamps_preserve_newest_first_sequence_when_reversed() -> None:
    events = [
        _event("off", "2026-09-17T04:00:00.000+0100"),
        _event("on", "2026-09-17T03:00:00.000+0100"),
        _event("off", "2026-09-17T03:00:00.000+0100"),
        _event("on", "2026-09-17T02:30:00.000+0100"),
    ]

    analysis = analyze_state_intervals("switch", events)

    assert analysis is not None
    assert analysis["intervalCount"] == 2
    assert analysis["totalActiveSeconds"] == 5400
    assert [row["duration"] for row in analysis["intervals"]] == ["30m", "1h"]


def test_partial_boundaries_are_reported_as_lower_bound_not_guessed() -> None:
    events = [
        _event("on", "2026-09-17T05:00:00.000+0100"),
        _event("off", "2026-09-17T04:00:00.000+0100"),
    ]

    analysis = analyze_state_intervals("switch", events)

    assert analysis is not None
    assert analysis["coverage"] == "partial"
    assert analysis["totalIsLowerBound"] is True
    assert analysis["openActiveInterval"] is True
    assert analysis["unmatchedInactiveRows"] == 1
    assert analysis["totalActiveSeconds"] == 0


def test_duplicate_or_non_state_change_rows_do_not_inflate_duration() -> None:
    events = [
        _event("off", "2026-09-17T02:00:00.000+0100"),
        _event("on", "2026-09-17T01:30:00.000+0100", state_change=False),
        _event("on", "2026-09-17T01:00:00.000+0100"),
        _event("on", "2026-09-17T00:59:00.000+0100"),
    ]

    analysis = analyze_state_intervals("switch", events)

    assert analysis is not None
    assert analysis["intervalCount"] == 1
    assert analysis["totalActiveSeconds"] == 3660
    assert analysis["duplicateStateRowsIgnored"] == 1
    assert analysis["ignoredRows"] == 1


def test_aware_datetimes_handle_offset_change_across_dst_boundary() -> None:
    events = [
        _event("off", "2026-10-25T01:30:00.000+0000"),
        _event("on", "2026-10-25T01:30:00.000+0100"),
    ]

    analysis = analyze_state_intervals("switch", events)

    assert analysis is not None
    assert analysis["intervalCount"] == 1
    assert analysis["totalActiveSeconds"] == 3600
    assert analysis["totalActiveDuration"] == "1h"


def test_unsupported_attribute_returns_no_synthetic_analysis() -> None:
    assert analyze_state_intervals(
        "temperature",
        [{"name": "temperature", "value": 21, "date": "2026-09-17T01:00:00+0100"}],
    ) is None
