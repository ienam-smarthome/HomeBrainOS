from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from time_expressions import parse_clock, strip_trailing_time  # noqa: E402


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
