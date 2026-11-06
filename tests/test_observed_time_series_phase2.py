"""Offline Phase 2 temporal-operator tests: no cloud, hub or writes."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from observed_time_series import observed_transition  # noqa: E402


def run(rows, **kw):
    return observed_transition(
        rows, from_operator="gt", from_threshold="70",
        to_operator="lt", to_threshold="60", **kw,
    )


def test_strict_threshold_and_exact_observed_sample_gap():
    rows = [
        {"timestamp": "2026-11-06T14:20:00Z", "value": 70},
        {"timestamp": "2026-11-06T14:25:00Z", "value": "74"},
        {"timestamp": "2026-11-06T18:00:00Z", "value": 60},
        {"timestamp": "2026-11-06T18:26:00Z", "value": "59"},
    ]
    r = run(rows)
    assert r["status"] == "observed_interval"
    assert r["start"] == {
        "timestamp_utc": "2026-11-06T14:25:00+00:00", "value": "74",
    }
    assert r["end"]["value"] == "59"
    assert r["observed_elapsed_seconds"] == 4 * 3600 + 60
    assert r["source_coverage_verified"] is False
    assert r["exact_physical_crossing_verified"] is False


def test_chooses_last_high_even_if_earlier_high_had_subsequent_low():
    rows = [
        {"timestamp": "2026-11-06T12:00:00Z", "value": 75},
        {"timestamp": "2026-11-06T13:00:00Z", "value": 55},
        {"timestamp": "2026-11-06T14:00:00Z", "value": 80},
    ]
    r = run(rows)
    assert r["status"] == "later_end_not_observed_in_supplied_rows"
    assert r["start"]["value"] == "80"
    assert r["observed_elapsed_seconds"] is None
    assert run(rows, choose_from="first")["observed_elapsed_seconds"] == 3600


def test_sort_by_absolute_time_and_handle_daylight_saving():
    rows = [
        {"timestamp": "2026-10-25T01:15:00+00:00", "value": 58},
        {"timestamp": "2026-10-25T01:45:00+01:00", "value": 72},
    ]
    assert run(rows)["observed_elapsed_seconds"] == 30 * 60


def test_same_timestamp_does_not_establish_later_observation():
    rows = [
        {"timestamp": "2026-11-06T12:00:00Z", "value": 80},
        {"timestamp": "2026-11-06T12:00:00Z", "value": 55},
    ]
    assert run(rows)["status"] == "later_end_not_observed_in_supplied_rows"


def test_missing_events_are_not_claimed_absent():
    assert run([])["status"] == "no_valid_observations"
    rows = [{"timestamp": "2026-11-06T13:00:00Z", "value": 69}]
    assert run(rows)["status"] == "start_not_observed_in_supplied_rows"


def test_invalid_rows_are_rejected_not_converted_to_zero():
    rows = [
        {"timestamp": "2026-11-06T14:25:00", "value": 74},
        {"timestamp": "2026-11-06T14:25:00Z", "value": "74 percent"},
        {"timestamp": "2026-11-06T14:25:00Z", "value": True},
        {"timestamp": "2026-11-06T14:25:00Z", "value": float("nan")},
        {"timestamp": "2026-11-06T14:25:00Z", "value": "74.0"},
        {"timestamp": "2026-11-06T18:26:00Z", "value": "59.0"},
    ]
    r = run(rows)
    assert r["observed_rows"] == 2 and r["rejected_rows"] == 4
    assert r["observed_elapsed_seconds"] == 14460


@pytest.mark.parametrize("options", [
    {"from_operator": "outside"},
    {"to_operator": "script"},
    {"from_threshold": "NaN"},
    {"to_threshold": "60%"},
    {"choose_from": "middle"},
])
def test_invalid_contract_rejected(options):
    defaults = {
        "from_operator": "gt", "from_threshold": "70",
        "to_operator": "lt", "to_threshold": "60",
    }
    defaults.update(options)
    with pytest.raises(ValueError):
        observed_transition([], **defaults)


def test_generic_comparisons_not_device_specific():
    rows = [
        {"timestamp": "2026-11-06T12:00:00Z", "value": "100"},
        {"timestamp": "2026-11-06T12:10:00Z", "value": "0"},
    ]
    r = observed_transition(
        rows, from_operator="gte", from_threshold=100,
        to_operator="eq", to_threshold=0,
    )
    assert r["status"] == "observed_interval"
    assert r["observed_elapsed_seconds"] == 600
