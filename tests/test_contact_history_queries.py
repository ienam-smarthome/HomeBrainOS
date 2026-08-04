from __future__ import annotations

from datetime import datetime, timezone

from contact_history_queries import (
    events_in_window,
    find_before_reference,
    parse_before_that,
    parse_count_yesterday,
    parse_list_yesterday,
    present_count,
    present_yesterday_events,
    yesterday_bounds,
)


def _event(value: str, date: str) -> dict[str, str]:
    return {"name": "contact", "value": value, "date": date}


def test_parses_supported_history_queries() -> None:
    assert parse_before_that("When did the front door open before that?") == (
        "front door",
        "open",
    )
    assert parse_count_yesterday("How many times did the front door open yesterday?") == (
        "front door",
        "open",
    )
    assert parse_list_yesterday("Show only front door contact events from yesterday.") == "front door"


def test_before_that_uses_reference_timestamp_not_event_position() -> None:
    events = [
        _event("closed", "2026-08-03T23:32:58.577+01:00"),
        _event("open", "2026-08-03T23:32:52.656+01:00"),
        _event("open", "2026-08-03T20:41:40.835+01:00"),
    ]
    found = find_before_reference(
        events,
        state="open",
        reference_timestamp="2026-08-03T23:32:58.577+01:00",
    )
    assert found == events[1]


def test_yesterday_window_and_count_presentation() -> None:
    now = datetime(2026, 8, 4, 13, 45, tzinfo=timezone.utc)
    start, end = yesterday_bounds(now)
    events = [
        _event("open", "2026-08-03T08:00:00+00:00"),
        _event("closed", "2026-08-03T08:01:00+00:00"),
        _event("open", "2026-08-04T08:00:00+00:00"),
    ]
    selected = events_in_window(events, start, end)
    assert len(selected) == 2
    assert present_count("Front Door", "open", 1) == "Front Door opened 1 time yesterday."


def test_yesterday_event_list_uses_natural_times() -> None:
    message = present_yesterday_events(
        "Front Door",
        [
            _event("closed", "2026-08-03T23:32:58.577+01:00"),
            _event("open", "2026-08-03T23:32:52.656+01:00"),
        ],
    )
    assert message.startswith("Front Door contact events yesterday:")
    assert "- Closed at 11:32 pm on Monday 3 August 2026" in message
    assert "- Opened at 11:32 pm on Monday 3 August 2026" in message
    assert "Recent history" not in message
    assert "caused" not in message
