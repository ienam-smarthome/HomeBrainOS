from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_temporal_analysis import (  # noqa: E402
    analyze_state_intervals,
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


def _big_lamp_events() -> list[dict]:
    return [
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


def _big_lamp_history_data() -> dict:
    analysis = analyze_state_intervals("switch", _big_lamp_events())
    assert analysis is not None
    return {
        "success": True,
        "label": "Big lamp",
        "attribute": "switch",
        "hoursBack": 24,
        "temporalAnalysis": analysis,
    }


def _big_lamp_receipt() -> dict:
    details = history_temporal_evidence_details(_big_lamp_history_data())
    assert details is not None
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": details,
    }


def test_big_lamp_history_pairs_intervals_and_totals_without_model_math() -> None:
    analysis = analyze_state_intervals("switch", _big_lamp_events())

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


def test_temporal_evidence_details_expose_auditable_duration_proof() -> None:
    details = history_temporal_evidence_details(_big_lamp_history_data())

    assert details is not None
    assert details["label"] == "Big lamp"
    assert details["attribute"] == "switch"
    assert details["hoursBack"] == 24
    assert details["temporalAnalysis"]["activeState"] == "on"
    assert details["temporalAnalysis"]["totalActiveSeconds"] == 16260
    assert details["temporalAnalysis"]["totalActiveDuration"] == "4h 31m"
    assert details["temporalAnalysis"]["intervalCount"] == 5
    assert details["temporalAnalysis"]["longestActiveDuration"] == "2h 38m"
    assert details["temporalAnalysis"]["coverage"] == "complete"


def test_wrong_model_total_is_replaced_with_deterministic_history_summary() -> None:
    message, applied = guard_history_duration_claim(
        (
            "The big lamp was on for a total of 4 hours and 29 minutes last night, "
            "across 5 separate intervals. The longest stretch was 2 hours and 38 minutes."
        ),
        [_big_lamp_receipt()],
    )

    assert applied is True
    assert message == (
        "Big lamp was on for a total of 4h 31m across 5 separate intervals. "
        "The longest interval was 2h 38m."
    )


def test_correct_model_total_passes_through_unchanged() -> None:
    original = (
        "Big lamp was on for a total of 4 hours and 31 minutes across 5 intervals; "
        "the longest was 2 hours and 38 minutes."
    )

    message, applied = guard_history_duration_claim(original, [_big_lamp_receipt()])

    assert applied is False
    assert message == original


def test_longest_only_claim_is_not_rewritten_as_total() -> None:
    original = "The longest Big lamp interval was 2 hours and 38 minutes."

    message, applied = guard_history_duration_claim(original, [_big_lamp_receipt()])

    assert applied is False
    assert message == original
