from __future__ import annotations

from homebrain_agent import UnifiedMCPAgent


def test_last_contact_request_extracts_literal_device_and_state() -> None:
    assert UnifiedMCPAgent._last_contact_request(
        "When did the front door last open?"
    ) == ("the front door", "open")
    assert UnifiedMCPAgent._last_contact_request(
        "When did Front Door last close?"
    ) == ("Front Door", "closed")


def test_last_contact_request_does_not_capture_general_history() -> None:
    assert UnifiedMCPAgent._last_contact_request(
        "Show me the recent history for Front Door"
    ) is None


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
