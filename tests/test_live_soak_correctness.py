from __future__ import annotations

from contextual_read_fast_path import (
    clean_choice_label,
    parse_contextual_attribute,
    parse_motion_activity,
    parse_named_attribute,
    present_attribute,
    present_motion_activity,
)
from homebrain_agent import UnifiedMCPAgent


def test_last_contact_request_extracts_literal_device_and_state() -> None:
    assert UnifiedMCPAgent._last_contact_request(
        "When did the front door last open?"
    ) == ("front door", "open")
    assert UnifiedMCPAgent._last_contact_request(
        "When did Front Door last close?"
    ) == ("Front Door", "closed")


def test_last_contact_request_does_not_capture_general_history() -> None:
    assert UnifiedMCPAgent._last_contact_request(
        "Show me the recent history for Front Door"
    ) is None


def test_why_contact_request_extracts_relevant_transition() -> None:
    assert UnifiedMCPAgent._why_contact_request(
        "Why did Front Door open last night?"
    ) == ("Front Door", "open")


def test_unresolved_pronoun_follow_up_is_detected() -> None:
    assert UnifiedMCPAgent._is_choice_follow_up("And its battery?")
    assert UnifiedMCPAgent._is_choice_follow_up("Which one is warmer?")
    assert not UnifiedMCPAgent._is_choice_follow_up("Bedroom 1 Meter battery")


def test_choice_message_repeats_available_devices() -> None:
    assert UnifiedMCPAgent._choice_message([
        "Bedroom 1 Meter",
        "Bedroom 1 TRV",
        "Temperature Sensor",
    ]) == (
        "Which device do you mean: Bedroom 1 Meter, Bedroom 1 TRV, "
        "or Temperature Sensor?"
    )


def test_choices_are_recovered_from_deterministic_clarification_message() -> None:
    assert UnifiedMCPAgent._choices_from_message(
        "Which device would you like the temperature from: **Bedroom 1 Meter**, "
        "**Bedroom 1 TRV**, or **Temperature Sensor**?"
    ) == ["Bedroom 1 Meter", "Bedroom 1 TRV", "Temperature Sensor"]


def test_choices_are_recovered_from_possible_matches_message() -> None:
    assert UnifiedMCPAgent._choices_from_message(
        "I could not resolve the front door uniquely. Possible matches: "
        "Front Door, Weather Open-Meteo, or Fridge Door."
    ) == ["Front Door", "Weather Open-Meteo", "Fridge Door"]


def test_contextual_attribute_follow_ups_use_current_state_parser() -> None:
    assert parse_contextual_attribute("What is its humidity?") == "humidity"
    assert parse_contextual_attribute("What's its battery?") == "battery"
    assert parse_contextual_attribute("Show me its current power.") == "power"
    assert parse_contextual_attribute("What is its temperature history?") is None
    assert parse_contextual_attribute("When did its humidity change?") is None


def test_named_attribute_reads_use_current_state_parser() -> None:
    assert parse_named_attribute("What is the Bedroom 1 temperature?") == (
        "Bedroom 1",
        "temperature",
    )
    assert parse_named_attribute("Show me Computer current power.") == (
        "Computer",
        "power",
    )
    assert parse_named_attribute("What is its humidity?") is None
    assert parse_named_attribute("When did Bedroom 1 humidity change?") is None


def test_motion_activity_requests_are_deterministic() -> None:
    assert parse_motion_activity("Which motion sensors are active?") == ("active", False)
    assert parse_motion_activity("How many motion sensors are inactive?") == ("inactive", True)
    assert parse_motion_activity("Which lights are active?") is None


def test_contextual_read_presenters_are_concise() -> None:
    assert present_attribute("Bedroom 1 Meter", "humidity", 48, "%") == (
        "Bedroom 1 Meter humidity is 48%."
    )
    assert present_motion_activity(
        [{"label": "Kitchen Motion"}, {"label": "Hall Motion"}],
        state="active",
        count_only=False,
    ) == "2 motion sensors are active: Kitchen Motion and Hall Motion."


def test_choice_labels_drop_presentation_articles() -> None:
    assert clean_choice_label("the Temperature Sensor") == "Temperature Sensor"
    assert clean_choice_label("or the Bedroom Meter") == "Bedroom Meter"
