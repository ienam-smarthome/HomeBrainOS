from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from location_event_queries import (  # noqa: E402
    find_mode_last_entered,
    mode_active_before,
    mode_events,
    parse_location_events_intent,
    parse_mode_last_entered,
    present_location_events,
    present_mode_at_time,
    present_mode_last_entered,
)


_EVENTS = [
    {
        "name": "mode",
        "value": "Afternoon",
        "date": "2026-08-10T12:00:02.375+0100",
    },
    {
        "name": "sunriseSunsetUpdated",
        "value": "",
        "date": "2026-08-10T12:00:02.228+0100",
    },
    {
        "name": "mode",
        "value": "Morning",
        "date": "2026-08-10T08:30:02.048+0100",
    },
    {
        "name": "mode",
        "value": "Night",
        "date": "2026-08-09T23:00:02.018+0100",
    },
]


def test_parse_location_events_intent_matches_button_style_phrasings():
    assert parse_location_events_intent("show recent mode changes")
    assert parse_location_events_intent("Show me the mode history")
    assert parse_location_events_intent("location events")
    assert parse_location_events_intent("recent location events")
    assert parse_location_events_intent("What mode changes happened today?")
    assert not parse_location_events_intent("what mode is the hub in")
    assert not parse_location_events_intent("turn off the lamp")
    assert not parse_location_events_intent("")


def test_parse_mode_last_entered_extracts_the_mode_name():
    assert parse_mode_last_entered("When did we last enter Night mode?") == "Night"
    assert parse_mode_last_entered("when did the hub last enter Bedtime mode") == "Bedtime"
    assert parse_mode_last_entered("When was School Run mode last active?") == "School Run"
    assert (
        parse_mode_last_entered("When did the mode last change to Late Night")
        == "Late Night"
    )
    assert parse_mode_last_entered("show recent mode changes") is None
    assert parse_mode_last_entered("turn off the lamp") is None


def test_mode_events_filters_out_non_mode_rows():
    changes = mode_events(_EVENTS)

    assert len(changes) == 3
    assert all(item["name"] == "mode" for item in changes)


def test_mode_active_before_returns_the_latest_mode_at_or_before_reference():
    active = mode_active_before(
        _EVENTS, reference_timestamp="2026-08-10T09:00:00+0100"
    )

    assert active is not None
    assert active["value"] == "Morning"


def test_mode_active_before_returns_none_when_reference_predates_all_events():
    active = mode_active_before(
        _EVENTS, reference_timestamp="2026-08-01T00:00:00+0100"
    )

    assert active is None


def test_mode_active_before_returns_none_for_an_unparseable_reference():
    assert mode_active_before(_EVENTS, reference_timestamp="") is None
    assert mode_active_before(_EVENTS, reference_timestamp="not a date") is None


def test_find_mode_last_entered_is_case_insensitive_and_picks_the_newest():
    matching = find_mode_last_entered(_EVENTS, mode_name="afternoon")

    assert matching is not None
    assert matching["date"] == "2026-08-10T12:00:02.375+0100"


def test_find_mode_last_entered_returns_none_when_never_reported():
    assert find_mode_last_entered(_EVENTS, mode_name="Vacation") is None


def test_present_location_events_lists_only_mode_changes_newest_first():
    message = present_location_events(_EVENTS)

    assert message.startswith("Recent mode changes:")
    assert "Afternoon" in message
    assert "Morning" in message
    assert "Night" in message
    assert "sunriseSunsetUpdated" not in message


def test_present_location_events_reports_explicitly_when_none_found():
    message = present_location_events([])

    assert message == "No mode changes were reported in that window."


def test_present_mode_last_entered_reports_the_timestamp():
    matching = find_mode_last_entered(_EVENTS, mode_name="Night")

    message = present_mode_last_entered("Night", matching)

    assert "hub last entered Night mode" in message


def test_present_mode_last_entered_is_explicit_when_never_reported():
    message = present_mode_last_entered("Vacation", None)

    assert message == 'No "Vacation" mode change was reported in that window.'


def test_present_mode_at_time_never_fabricates_a_mode():
    assert present_mode_at_time(None) is None
    assert present_mode_at_time({"value": ""}) is None


def test_present_mode_at_time_formats_a_short_clause():
    active = mode_active_before(
        _EVENTS, reference_timestamp="2026-08-10T09:00:00+0100"
    )

    assert present_mode_at_time(active) == "Morning mode"
