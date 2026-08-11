from __future__ import annotations

from datetime import datetime, timezone

from contact_history_queries import (
    events_in_window,
    find_before_reference,
    parse_before_that,
    parse_count_yesterday,
    parse_event_datetime,
    parse_list_yesterday,
    present_count,
    present_yesterday_events,
    yesterday_bounds,
)


def _event(value: str, date: str) -> dict[str, str]:
    return {"name": "contact", "value": value, "date": date}


def test_parse_event_datetime_handles_a_colonless_utc_offset() -> None:
    """Regression test (Tier 3 finding #16): this module's own datetime
    parsing used to carry a bare `.replace("Z", "+00:00")` with no offset-
    without-colon normalization, unlike natural_datetime.py's
    format_natural_datetime(), which explicitly rewrites a trailing
    "+0100"-style offset (no colon) to "+01:00" before calling
    fromisoformat() -- required on Python 3.10 and earlier, where
    fromisoformat() only accepts the colon form. Hubitat emits event
    timestamps in exactly this colonless shape
    ("...23:32:52.656+0100"). Currently inert on the deployed Python
    version (which parses the colonless form natively), but this proves
    parse_event_datetime() now shares the exact same normalization as
    format_natural_datetime() rather than silently drifting from it."""

    parsed = parse_event_datetime("2026-08-03T23:32:52.656+0100")

    assert parsed is not None
    assert parsed.utcoffset().total_seconds() == 3600
    assert parsed.hour == 23
    assert parsed.minute == 32


def test_parse_event_datetime_still_handles_a_trailing_z() -> None:
    parsed = parse_event_datetime("2026-08-03T23:32:52Z")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


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
