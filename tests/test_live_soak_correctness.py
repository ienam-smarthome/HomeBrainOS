from __future__ import annotations

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
