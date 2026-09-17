from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_time_windows import (  # noqa: E402
    active_history_window_request,
    parse_history_window_request,
    required_history_hours,
    reset_history_window_request,
    resolve_history_window,
    set_history_window_request,
)


LOCAL = timezone(timedelta(hours=1))


def _now(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 17, hour, minute, tzinfo=LOCAL)


def test_last_night_is_previous_1800_to_today_0800_after_morning() -> None:
    request = parse_history_window_request("How long was Big lamp on last night?")
    window = resolve_history_window(request, now=_now(20))

    assert window is not None
    assert window.kind == "last_night"
    assert window.label == "last night"
    assert window.start == datetime(2026, 9, 16, 18, 0, tzinfo=LOCAL)
    assert window.end == datetime(2026, 9, 17, 8, 0, tzinfo=LOCAL)
    assert window.ongoing is False
    assert required_history_hours(window, now=_now(20)) == 27


def test_last_night_is_capped_at_now_while_window_is_in_progress() -> None:
    request = parse_history_window_request("Was the lamp on last night?")
    window = resolve_history_window(request, now=_now(3, 15))

    assert window is not None
    assert window.start == datetime(2026, 9, 16, 18, 0, tzinfo=LOCAL)
    assert window.end == _now(3, 15)
    assert window.ongoing is True


def test_calendar_phrases_resolve_to_local_calendar_boundaries() -> None:
    yesterday = resolve_history_window(
        parse_history_window_request("how long yesterday"),
        now=_now(20),
    )
    morning = resolve_history_window(
        parse_history_window_request("how long this morning"),
        now=_now(20),
    )
    midnight = resolve_history_window(
        parse_history_window_request("how long since midnight"),
        now=_now(20),
    )
    today = resolve_history_window(
        parse_history_window_request("how long today"),
        now=_now(20),
    )

    assert yesterday is not None
    assert yesterday.start == datetime(2026, 9, 16, 0, 0, tzinfo=LOCAL)
    assert yesterday.end == datetime(2026, 9, 17, 0, 0, tzinfo=LOCAL)
    assert morning is not None
    assert morning.start == datetime(2026, 9, 17, 0, 0, tzinfo=LOCAL)
    assert morning.end == datetime(2026, 9, 17, 12, 0, tzinfo=LOCAL)
    assert midnight is not None
    assert midnight.start == datetime(2026, 9, 17, 0, 0, tzinfo=LOCAL)
    assert midnight.end == _now(20)
    assert midnight.ongoing is True
    assert today is not None
    assert today.start == datetime(2026, 9, 17, 0, 0, tzinfo=LOCAL)
    assert today.end == _now(20)


def test_explicit_clock_range_overrides_last_night_default() -> None:
    request = parse_history_window_request(
        "How long was Big lamp on between 10pm and 6am last night?"
    )
    window = resolve_history_window(request, now=_now(20))

    assert request == {
        "kind": "clock_range",
        "label": "between 10pm and 6am",
        "startClock": "22:00",
        "endClock": "06:00",
        "anchor": "last_night",
    }
    assert window is not None
    assert window.start == datetime(2026, 9, 16, 22, 0, tzinfo=LOCAL)
    assert window.end == datetime(2026, 9, 17, 6, 0, tzinfo=LOCAL)
    assert window.ongoing is False


def test_unanchored_clock_range_uses_most_recent_started_occurrence() -> None:
    request = parse_history_window_request(
        "How long was Big lamp on between 10pm and 6am?"
    )
    window = resolve_history_window(request, now=_now(20))

    assert window is not None
    assert window.start == datetime(2026, 9, 16, 22, 0, tzinfo=LOCAL)
    assert window.end == datetime(2026, 9, 17, 6, 0, tzinfo=LOCAL)


def test_bare_hour_without_ampm_or_minutes_is_not_treated_as_clock_range() -> None:
    assert parse_history_window_request("between 10 and 6") is None


def test_request_scoped_window_is_used_and_reset_without_leaking() -> None:
    request = parse_history_window_request("How long was Big lamp on last night?")
    token = set_history_window_request(request)
    try:
        assert active_history_window_request() == request
        window = resolve_history_window(None, now=_now(20))
        assert window is not None
        assert window.label == "last night"
    finally:
        reset_history_window_request(token)

    assert active_history_window_request() is None
    assert resolve_history_window(None, now=_now(20)) is None
