from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from time_expressions import AT_TIME, parse_clock, strip_trailing_time  # noqa: E402


def test_parse_clock_handles_period_separated_minutes():
    """Regression test for a live production bug: "turn on livingroom light
    1 every day at 11.25" and "...at 11.23" both created real Rule Machine
    rules, but for 11:00 AM instead of 11:25/11:23 -- the requested minutes
    were silently dropped. Root cause: AT_TIME's time-capture group only
    recognised a colon between hour and minute, so a period separator like
    "11.25" only captured "11" up to the word boundary before the period,
    and parse_clock then defaulted the missing minute to 0. Both AT_TIME
    and parse_clock now accept a period as an equally valid separator.
    """

    assert parse_clock("11.25") == "11:25"
    assert parse_clock("11.23") == "11:23"
    assert parse_clock("7.30am") == "07:30"
    assert parse_clock("11.25pm") == "23:25"
    # A bare period-abbreviated am/pm spelling must still work -- the fix
    # must not treat every "." as a minute separator, only one directly
    # between an hour and a two-digit minute.
    assert parse_clock("7 p.m.") == "19:00"
    assert parse_clock("7a.m.") == "07:00"


def test_at_time_captures_period_separated_clock_expressions():
    match = AT_TIME.search("turn on livingroom light 1 every day at 11.25")
    assert match is not None
    assert match.group("time") == "11.25"
    assert parse_clock(match.group("time")) == "11:25"


def test_parse_clock_handles_12_and_24_hour_forms():
    assert parse_clock("7am") == "07:00"
    assert parse_clock("11:11pm") == "23:11"
    assert parse_clock("19:00") == "19:00"
    assert parse_clock("12am") == "00:00"
    assert parse_clock("12pm") == "12:00"


def test_parse_clock_rejects_malformed_input():
    assert parse_clock("25:00") is None
    assert parse_clock("13pm") is None
    assert parse_clock("not a time") is None


def test_strip_trailing_time_removes_only_a_parseable_at_clause():
    cleaned, parsed = strip_trailing_time("hallway lights at 11:11pm")
    assert cleaned == "hallway lights"
    assert parsed == "23:11"


def test_strip_trailing_time_leaves_text_untouched_when_no_time_present():
    cleaned, parsed = strip_trailing_time("hallway lights")
    assert cleaned == "hallway lights"
    assert parsed is None


def test_strip_trailing_time_leaves_malformed_at_clause_untouched():
    cleaned, parsed = strip_trailing_time("meeting at the office")
    assert cleaned == "meeting at the office"
    assert parsed is None
