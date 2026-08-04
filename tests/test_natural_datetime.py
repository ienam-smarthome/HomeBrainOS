from __future__ import annotations

from natural_datetime import format_natural_datetime


def test_formats_iso_timestamp_as_natural_local_time() -> None:
    assert format_natural_datetime("2026-08-03T23:32:52.656+0100") == (
        "11:32 pm on Monday 3 August 2026"
    )


def test_formats_morning_without_leading_zero() -> None:
    assert format_natural_datetime("2026-08-04T09:05:00+01:00") == (
        "9:05 am on Tuesday 4 August 2026"
    )


def test_preserves_unparseable_timestamp() -> None:
    assert format_natural_datetime("not-a-date") == "not-a-date"


def test_empty_timestamp_has_safe_fallback() -> None:
    assert format_natural_datetime("") == "an unreported time"
