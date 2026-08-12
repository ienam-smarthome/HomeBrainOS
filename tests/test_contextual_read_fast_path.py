from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from contextual_read_fast_path import (  # noqa: E402
    capability_choice_labels,
    clean_choice_label,
    is_pronoun_reference,
    parse_bare_attribute,
    parse_contextual_attribute,
    parse_device_selection,
    parse_motion_activity,
    parse_named_attribute,
    present_attribute,
    present_motion_activity,
)

"""Regression test: this module had no dedicated test file at all (Tier 3
finding #17 from the 2026-08-10 full code review) -- a coverage gap, not a
known live bug. Every current call site happens to avoid the double-unit
shape present_attribute() has no guard against, so that gap is exercised
and documented here rather than silently fixed blind.
"""


def test_is_pronoun_reference_recognises_every_listed_pronoun_case_insensitively():
    assert is_pronoun_reference("it") is True
    assert is_pronoun_reference("It's") is True
    assert is_pronoun_reference("THAT DEVICE") is True
    assert is_pronoun_reference("current") is True
    assert is_pronoun_reference("  the  ") is True


def test_is_pronoun_reference_false_for_a_real_device_name():
    assert is_pronoun_reference("Front Door") is False
    assert is_pronoun_reference("Kitchen Light") is False


def test_clean_choice_label_strips_leading_conjunction_and_article():
    assert clean_choice_label("or the Front Door") == "Front Door"
    assert clean_choice_label("and a Kitchen Light") == "Kitchen Light"
    assert clean_choice_label("an Attic Sensor") == "Attic Sensor"
    assert clean_choice_label("Front Door") == "Front Door"


def test_parse_contextual_attribute_matches_pronoun_only_phrasing():
    assert parse_contextual_attribute("what's its temperature?") == "temperature"
    assert parse_contextual_attribute("tell me that device's battery") == "battery"
    assert parse_contextual_attribute("show its current power") == "power"


def test_parse_contextual_attribute_none_for_history_wording():
    assert parse_contextual_attribute("what was its temperature yesterday?") is None
    assert parse_contextual_attribute("when did its battery last change?") is None


def test_parse_contextual_attribute_none_when_a_device_name_is_present():
    assert parse_contextual_attribute("what's the front door's temperature?") is None


def test_parse_named_attribute_returns_name_and_attribute():
    assert parse_named_attribute("what's the front door temperature?") == (
        "front door",
        "temperature",
    )
    assert parse_named_attribute("tell me the kitchen light current power") == (
        "kitchen light",
        "power",
    )


def test_parse_named_attribute_none_for_bare_qualifier_backtracking():
    """Regression: parse_named_attribute's own regex used to backtrack
    "What's the temperature?" into name="the" and "What is the current
    battery" into name="current" when there was no real device name at
    all -- both must fall through to None (letting parse_bare_attribute
    handle them instead), not resolve "the"/"current" as a device name."""

    assert parse_named_attribute("what's the temperature?") is None
    assert parse_named_attribute("what is the current battery") is None


def test_parse_named_attribute_none_for_pronoun_name():
    assert parse_named_attribute("what's it's temperature?") is None


def test_parse_named_attribute_none_for_whole_house_aggregate_scope():
    """Regression test for a live failure: "what's the current whole house
    power" / "what's the whole house power" hit the same backtracking bug
    as "the"/"current" above -- with no real device name in the sentence,
    _NAMED_ATTRIBUTE's name group swallowed the aggregate-scope qualifier
    phrase ("whole house", "current whole house") and treated it as a
    literal device name to resolve. That deterministic single-device
    lookup then failed and offered an "Unresolved... Which device do you
    mean" clarification listing devices with nothing to do with power
    (e.g. "Front Door", "Google Chromecast+") -- both because this phrase
    should never have reached device-name resolution at all (it describes
    a whole-house aggregate question, which the model's tool-calling loop
    already handles correctly for "current power usage") and because the
    fuzzy matcher's fallback candidates weren't filtered by relevance
    (covered separately in test_device_target_resolver.py). These phrases
    must fall through to None so the request reaches the model loop.
    """

    assert parse_named_attribute("what's the whole house power") is None
    assert parse_named_attribute("what's the current whole house power?") is None
    assert parse_named_attribute("what is the whole home power") is None
    assert is_pronoun_reference("whole house") is True
    assert is_pronoun_reference("current whole house") is True


def test_parse_named_attribute_none_for_history_wording():
    assert parse_named_attribute("what was the front door temperature yesterday?") is None


def test_parse_bare_attribute_matches_single_word_and_minimal_question_forms():
    assert parse_bare_attribute("temperature") == "temperature"
    assert parse_bare_attribute("Battery") == "battery"
    assert parse_bare_attribute("what's the temperature?") == "temperature"
    assert parse_bare_attribute("what is the current humidity") == "humidity"


def test_parse_bare_attribute_none_for_history_wording_or_named_device():
    assert parse_bare_attribute("what was the temperature yesterday?") is None
    assert parse_bare_attribute("what's the front door temperature?") is None


def test_parse_device_selection_requires_a_selection_prefix():
    assert parse_device_selection("select the Front Door") == "Front Door"
    assert parse_device_selection("use Kitchen Light") == "Kitchen Light"
    assert parse_device_selection("I mean the Attic Sensor") == "Attic Sensor"
    assert parse_device_selection("the Front Door") is None


def test_parse_device_selection_bare_prefix_word_falls_through_to_the_whole_string():
    """"select" alone has the selection-prefix keyword but no trailing
    whitespace-separated remainder for _DEVICE_SELECTION's optional prefix
    group to consume, so its non-greedy name group ends up matching the
    literal word "select" itself rather than yielding None."""

    assert parse_device_selection("select") == "select"


def test_parse_device_selection_none_when_no_selection_prefix_is_present():
    assert parse_device_selection("the front door") is None


def test_capability_choice_labels_requires_every_token_present():
    matches = [
        {"label": "Front Door Lock"},
        {"label": "Back Door Lock"},
        {"label": "Front Door Sensor"},
    ]
    assert capability_choice_labels("front door", matches) == [
        "Front Door Lock",
        "Front Door Sensor",
    ]


def test_capability_choice_labels_dedupes_by_case_insensitive_label():
    matches = [{"label": "Front Door"}, {"label": "front door"}]
    assert capability_choice_labels("front door", matches) == ["Front Door"]


def test_capability_choice_labels_skips_entries_with_no_label():
    matches = [{"label": ""}, {"name": "Front Door"}]
    assert capability_choice_labels("front door", matches) == ["Front Door"]


def test_parse_motion_activity_count_only_form():
    assert parse_motion_activity("how many motion sensors are active?") == (
        "active",
        True,
    )


def test_parse_motion_activity_list_form():
    assert parse_motion_activity("which motion sensors are inactive?") == (
        "inactive",
        False,
    )
    assert parse_motion_activity("show motion sensors active") == ("active", False)


def test_parse_motion_activity_none_for_unrelated_prompt():
    assert parse_motion_activity("what's the temperature?") is None


def test_present_attribute_renders_percent_unit_with_no_separator():
    assert present_attribute("Front Door Lock", "battery", 45, "%") == (
        "Front Door Lock battery is 45%."
    )


def test_present_attribute_renders_other_units_with_no_separator():
    assert present_attribute("Living Room", "temperature", 68, "°F") == (
        "Living Room temperature is 68°F."
    )


def test_present_attribute_renders_no_unit_as_bare_value():
    assert present_attribute("Front Door", "contact", "open", None) == (
        "Front Door contact is open."
    )
    assert present_attribute("Front Door", "contact", "open", "") == (
        "Front Door contact is open."
    )


def test_present_attribute_has_no_guard_against_an_already_suffixed_value():
    """Documents a known, currently-unreached gap (Tier 3 finding #17):
    present_attribute() has no strip guard for a value that already
    carries its own unit suffix, unlike deterministic_tool_presenter.py's
    battery-filter branch (fixed in 0.10.408) and
    device_query_service.py's low-battery aggregation, both of which
    explicitly strip a pre-existing "%" before re-appending one. No known
    call site currently passes an already-suffixed value into this
    function, so this is coverage of the gap's existence, not a live bug
    fix."""

    assert present_attribute("Front Door Lock", "battery", "45%", "%") == (
        "Front Door Lock battery is 45%%."
    )


def test_present_motion_activity_count_only():
    matches = [{"label": "Hallway Motion"}, {"label": "Kitchen Motion"}]
    assert present_motion_activity(matches, state="active", count_only=True) == (
        "2 motion sensors are active."
    )


def test_present_motion_activity_single_sensor():
    matches = [{"label": "Hallway Motion"}]
    assert present_motion_activity(matches, state="active", count_only=False) == (
        "1 motion sensor is active: Hallway Motion."
    )


def test_present_motion_activity_two_sensors_joined_with_and():
    matches = [{"label": "Hallway Motion"}, {"label": "Kitchen Motion"}]
    assert present_motion_activity(matches, state="active", count_only=False) == (
        "2 motion sensors are active: Hallway Motion and Kitchen Motion."
    )


def test_present_motion_activity_three_or_more_uses_oxford_comma_list():
    matches = [
        {"label": "Hallway Motion"},
        {"label": "Kitchen Motion"},
        {"label": "Attic Motion"},
    ]
    assert present_motion_activity(matches, state="active", count_only=False) == (
        "3 motion sensors are active: Hallway Motion, Kitchen Motion, and Attic Motion."
    )


def test_present_motion_activity_dedupes_by_case_insensitive_label():
    matches = [{"label": "Hallway Motion"}, {"label": "hallway motion"}]
    assert present_motion_activity(matches, state="active", count_only=False) == (
        "1 motion sensor is active: Hallway Motion."
    )


def test_present_motion_activity_zero_matches():
    assert present_motion_activity([], state="active", count_only=False) == (
        "0 motion sensors are active."
    )
