from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_result_enrichment import prepare_history_arguments  # noqa: E402
from history_temporal_analysis import (  # noqa: E402
    analyze_state_intervals,
    history_temporal_evidence_details,
)
from history_time_windows import (  # noqa: E402
    reset_history_window_request,
    set_history_window_request,
)
from synthesis_validator import validate_synthesis  # noqa: E402


def _history_receipt() -> dict:
    analysis = analyze_state_intervals(
        "switch",
        [
            {
                "name": "switch",
                "value": "off",
                "date": "2026-10-06T07:20:00.000+0100",
                "isStateChange": True,
            },
            {
                "name": "switch",
                "value": "on",
                "date": "2026-10-06T07:10:00.000+0100",
                "isStateChange": True,
            },
        ],
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
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": details,
    }


def test_prepared_history_args_carry_request_window_even_with_known_attribute() -> None:
    window = {
        "label": "this morning",
        "start": "2026-10-06T00:00:00+01:00",
        "end": "2026-10-06T09:00:00+01:00",
        "ongoing": True,
    }
    token = set_history_window_request(window)
    try:
        prepared = prepare_history_arguments(
            "homebrain_device_history",
            {"name": "Bathroom Light 1", "attribute": "switch", "limit": 1},
        )
    finally:
        reset_history_window_request(token)

    assert prepared["time_window"] == window
    assert prepared["time_window"] is not window
    assert prepared["limit"] == 1


def test_explicit_history_window_is_not_overwritten_by_request_context() -> None:
    request_window = {
        "label": "this morning",
        "start": "2026-10-06T00:00:00+01:00",
        "end": "2026-10-06T09:00:00+01:00",
        "ongoing": True,
    }
    explicit_window = {
        "label": "yesterday",
        "start": "2026-10-05T00:00:00+01:00",
        "end": "2026-10-06T00:00:00+01:00",
        "ongoing": False,
    }
    token = set_history_window_request(request_window)
    try:
        prepared = prepare_history_arguments(
            "homebrain_device_history",
            {
                "name": "Bathroom Light 1",
                "attribute": "switch",
                "limit": 1,
                "time_window": explicit_window,
            },
        )
    finally:
        reset_history_window_request(token)

    assert prepared["time_window"] == explicit_window


def test_duration_request_cannot_lose_deterministic_total_when_model_omits_it() -> None:
    draft = (
        "Bathroom Light 1 turned on at 7:10 am and turned off at 7:20 am. "
        "The event stream integrity is unverified."
    )

    corrected, issues = validate_synthesis(
        draft,
        [_history_receipt()],
        original_user="How long was Bathroom Light 1 on this morning?",
    )

    assert "history_duration_reliability" in issues
    assert "10m" in corrected
    assert "1" in corrected


def test_recorded_event_timestamps_are_not_described_as_estimates() -> None:
    draft = (
        "Bathroom Light 1 turned on at 7:10 am. "
        "These timestamps are estimates based on recorded events, as the event stream integrity is unverified."
    )

    corrected, issues = validate_synthesis(draft, [_history_receipt()])

    assert "history_recorded_timestamp_semantics" in issues
    assert "recorded event observations" in corrected
    assert "timestamps are estimates" not in corrected.casefold()
