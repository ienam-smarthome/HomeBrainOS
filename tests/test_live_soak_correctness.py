from __future__ import annotations

from contextual_read_fast_path import (
    capability_choice_labels,
    clean_choice_label,
    parse_bare_attribute,
    parse_contextual_attribute,
    parse_device_selection,
    parse_motion_activity,
    parse_named_attribute,
    present_attribute,
    present_motion_activity,
)
from homebrain_agent import UnifiedMCPAgent
from request_classification import (
    parse_firmware_install_intent,
    parse_firmware_status_intent,
    parse_immediate_internet_access_intent,
)


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


def test_named_and_room_attribute_reads_use_current_state_parser() -> None:
    assert parse_named_attribute("What is the Bedroom 1 temperature?") == (
        "Bedroom 1",
        "temperature",
    )
    assert parse_named_attribute("What is the Bedroom 1 humidity?") == (
        "Bedroom 1",
        "humidity",
    )
    assert parse_named_attribute("What is the Bedroom 1 Meter temperature?") == (
        "Bedroom 1 Meter",
        "temperature",
    )
    assert parse_named_attribute("Show me Computer current power.") == (
        "Computer",
        "power",
    )
    assert parse_named_attribute("What is its humidity?") is None
    assert parse_named_attribute("When did Bedroom 1 humidity change?") is None


def test_named_attribute_does_not_treat_a_bare_article_as_a_device_name() -> None:
    """Regression test for a real bug this session's bare-attribute fast
    path exposed: the regex's optional "(?:the\\s+)?" lead-in and its
    required-nonempty name group can't both be satisfied by "the
    temperature" without giving "the" to one or the other, and it used to
    give it to name -- so "What's the temperature?" resolved a device
    literally named "the" instead of falling through to
    parse_bare_attribute. Articles must be excluded the same way pronouns
    already are.
    """

    assert parse_named_attribute("What's the temperature?") is None
    assert parse_named_attribute("What is a humidity?") is None
    assert parse_named_attribute("Show me an power.") is None
    assert parse_named_attribute("What is the Bedroom 1 temperature?") == (
        "Bedroom 1",
        "temperature",
    )


def test_bare_attribute_words_are_deterministic() -> None:
    """Regression test for a real live failure: a bare "temperature" query
    (no device name, no question wording) used to fall through to the
    model's tool-selection loop entirely, where it could -- and did --
    answer from the outdoor weather device instead of resolving as an
    indoor reading. This parser must catch the plain word on its own as
    well as its minimal question forms, but must not swallow a named
    request (that stays on parse_named_attribute) or a history request.
    """

    assert parse_bare_attribute("temperature") == "temperature"
    assert parse_bare_attribute("Temperature?") == "temperature"
    assert parse_bare_attribute("humidity") == "humidity"
    assert parse_bare_attribute("What's the temperature?") == "temperature"
    assert parse_bare_attribute("What is the current battery") == "battery"
    assert parse_bare_attribute("Show me the power.") == "power"
    assert parse_bare_attribute("What is the Bedroom 1 temperature?") is None
    assert parse_bare_attribute("Bedroom 1 temperature") is None
    assert parse_bare_attribute("What was the temperature yesterday?") is None
    assert parse_bare_attribute("temperature history") is None
    assert parse_bare_attribute("what's the weather outside") is None


def test_bare_attribute_matches_apostrophe_free_and_article_only_phrasing() -> None:
    """Two false-negative gaps found in a further debugging pass: real
    users often type "whats" without the apostrophe (mobile
    autocorrect-off is common), and a terse "the temperature" follow-up
    has no question word at all. Both used to fall through to the model's
    tool-selection loop -- the exact outdoor-weather-misrouting risk this
    parser exists to close -- rather than resolving deterministically.
    """

    assert parse_bare_attribute("whats the temperature") == "temperature"
    assert parse_bare_attribute("Whats the humidity?") == "humidity"
    assert parse_bare_attribute("whats battery") == "battery"
    assert parse_bare_attribute("the temperature") == "temperature"
    assert parse_bare_attribute("The temperature?") == "temperature"
    assert parse_bare_attribute("the current power") == "power"
    # Still correctly rejected: a real device name after "the" must keep
    # falling through to parse_named_attribute, not resolve here.
    assert parse_bare_attribute("the Bedroom 1 temperature") is None
    assert parse_bare_attribute("whatsoever") is None


def test_named_and_contextual_attribute_also_accept_apostrophe_free_whats() -> None:
    """Same "whats" (no apostrophe) gap applies to the other two attribute
    parsers, which share the same what(?:'s|\\s+is) prefix pattern.
    """

    assert parse_named_attribute("whats the Bedroom 1 temperature") == (
        "Bedroom 1",
        "temperature",
    )
    assert parse_contextual_attribute("whats its humidity") == "humidity"


def test_firmware_install_intent_matches_only_genuine_install_directives() -> None:
    """Must catch the WebUI's own "Update hub firmware" button text
    (which submits "Install the available Hubitat firmware update") and
    reasonable variants, but never a read-only firmware question -- this
    is a sensitive-write trigger, not a read fast path, so false positives
    matter more here than elsewhere in this module.
    """

    assert parse_firmware_install_intent("Install the available Hubitat firmware update")
    assert parse_firmware_install_intent("install firmware")
    assert parse_firmware_install_intent("Please install the firmware update.")
    assert parse_firmware_install_intent("update hub firmware")
    assert parse_firmware_install_intent("Update the Hubitat firmware")
    assert parse_firmware_install_intent("upgrade firmware")
    assert parse_firmware_install_intent("Upgrade the hub firmware")

    assert not parse_firmware_install_intent("check firmware")
    assert not parse_firmware_install_intent("what firmware is installed")
    assert not parse_firmware_install_intent("is there a firmware update")
    assert not parse_firmware_install_intent("firmware status")
    assert not parse_firmware_install_intent("Hub firmware 2.5.1.145 is installed")
    assert not parse_firmware_install_intent("update the living room light")
    assert not parse_firmware_install_intent("")


def test_firmware_status_intent_matches_only_progress_questions() -> None:
    """Must catch the exact phrasing the confirm-step message suggests
    ("ask me for the update status") and reasonable variants, but never a
    generic firmware question that the ordinary snapshot flow already
    answers fine, and never an install directive (that stays on
    parse_firmware_install_intent).
    """

    assert parse_firmware_status_intent("update status")
    assert parse_firmware_status_intent("firmware update status")
    assert parse_firmware_status_intent("check the firmware update status")
    assert parse_firmware_status_intent("update progress")
    assert parse_firmware_status_intent("check firmware update progress")
    assert parse_firmware_status_intent("How's the update going?")
    assert parse_firmware_status_intent("How is the firmware update going?")
    assert parse_firmware_status_intent("Is the update done?")
    assert parse_firmware_status_intent("Is the firmware update finished?")
    assert parse_firmware_status_intent("Has the firmware update completed?")

    assert not parse_firmware_status_intent("check firmware")
    assert not parse_firmware_status_intent("what firmware is installed")
    assert not parse_firmware_status_intent("is there a firmware update")
    assert not parse_firmware_status_intent("install firmware")
    assert not parse_firmware_status_intent("Install the available Hubitat firmware update")
    assert not parse_firmware_status_intent("update hub firmware")
    assert not parse_firmware_status_intent("")


def test_immediate_internet_access_intent_matches_only_unscheduled_block_allow() -> None:
    """Regression test for a real live failure: "block the tv" (no time
    clause at all) had no deterministic handling anywhere in the codebase
    -- RuleAuthoringService's own block/allow grammar only ever engages
    for a scheduled request (an "at <time>" clause or a "from X to Y"
    window) -- so it fell through to the model, which interpreted "block"
    as "turn off" and powered the device down instead. Must catch the
    bare, immediate form, but must never intercept a scheduled request
    (those still belong to RuleAuthoringService, unchanged) or explicit
    rule-authoring language.
    """

    assert parse_immediate_internet_access_intent("block the tv") == ("tv", "blockInternet")
    assert parse_immediate_internet_access_intent("Block the TV.") == ("TV", "blockInternet")
    assert parse_immediate_internet_access_intent("disable internet for the tv") == (
        "tv", "blockInternet",
    )
    assert parse_immediate_internet_access_intent("allow the tv") == ("tv", "allowInternet")
    assert parse_immediate_internet_access_intent("enable internet access for the tv") == (
        "tv", "allowInternet",
    )
    assert parse_immediate_internet_access_intent("please block the xbox") == (
        "xbox", "blockInternet",
    )

    assert parse_immediate_internet_access_intent("block the tv at 10pm") is None
    assert parse_immediate_internet_access_intent(
        "block internet for the tv from 10pm to 6am"
    ) is None
    assert parse_immediate_internet_access_intent(
        "create an automation to block the tv"
    ) is None
    assert parse_immediate_internet_access_intent("is the tv blocked") is None
    assert parse_immediate_internet_access_intent("") is None


def test_explicit_device_selection_commands_are_deterministic() -> None:
    assert parse_device_selection("Select Bedroom 1 Meter") == "Bedroom 1 Meter"
    assert parse_device_selection("Use the Bedroom 1 TRV") == "Bedroom 1 TRV"
    assert parse_device_selection("I mean Bedroom 1 Meter") == "Bedroom 1 Meter"
    assert parse_device_selection("Bedroom 1 Meter") is None


def test_capability_choices_filter_room_name_collisions() -> None:
    matches = [
        {"label": "Bedroom1 (MQTT)", "value": None},
        {"label": "Bedroom 1 Meter", "value": 28.5},
        {"label": "Bedroom 1 TRV", "value": 28.2},
        {"label": "Livingroom Meter", "value": 29.0},
    ]
    assert capability_choice_labels("Bedroom 1", matches) == [
        "Bedroom 1 Meter",
        "Bedroom 1 TRV",
    ]


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
