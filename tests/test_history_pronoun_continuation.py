from __future__ import annotations

from contact_history_queries import (
    find_after_reference,
    find_before_reference,
    parse_after_that,
    parse_before_that,
)
from homebrain_agent import UnifiedMCPAgent


def _events() -> list[dict[str, str]]:
    return [
        {"name": "contact", "value": "closed", "date": "2026-08-04T12:00:10+01:00"},
        {"name": "contact", "value": "open", "date": "2026-08-04T12:00:05+01:00"},
        {"name": "contact", "value": "closed", "date": "2026-08-04T11:00:10+01:00"},
        {"name": "contact", "value": "open", "date": "2026-08-04T11:00:05+01:00"},
    ]


def test_pronoun_before_that_uses_saved_target_marker() -> None:
    assert parse_before_that("When did it open before that?") == (None, "open")


def test_named_before_that_keeps_explicit_target() -> None:
    assert parse_before_that("When did the front door open before that?") == (
        "front door",
        "open",
    )


def test_pronoun_after_that_is_supported() -> None:
    assert parse_after_that("When did it close after that?") == (None, "closed")


def test_relative_event_selection_uses_nearest_timestamp() -> None:
    before = find_before_reference(
        _events(), state="open", reference_timestamp="2026-08-04T12:00:10+01:00"
    )
    after = find_after_reference(
        _events(), state="closed", reference_timestamp="2026-08-04T11:00:05+01:00"
    )
    assert before is not None and before["date"] == "2026-08-04T12:00:05+01:00"
    assert after is not None and after["date"] == "2026-08-04T11:00:10+01:00"


def test_recovered_choices_are_deduplicated_and_cleaned() -> None:
    message = "I could not resolve it uniquely. Possible matches: Switch, Switch, and TV."
    assert UnifiedMCPAgent._choices_from_message(message) == ["Switch", "TV"]
