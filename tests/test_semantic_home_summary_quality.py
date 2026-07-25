from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_home_evidence import _is_household_battery, _is_household_climate, _required_facts  # noqa: E402
from semantic_home_summary_agent import (  # noqa: E402
    _contains_required_facts,
    _fact_manifest,
    _fallback,
    _normalise_answer,
)


def sample_evidence():
    data = {
        "mode": "Morning",
        "motion": {
            "active_count": 2,
            "active": [
                {"device": "Bedroom 3 Presence Sensor", "room": "Bedroom 3", "state": "active"},
                {"device": "Livingroom FP300", "room": "Living Room", "state": "active"},
            ],
        },
        "contacts": {
            "open_count": 1,
            "open": [{"title": "Front Door", "room": "Hallway"}],
        },
        "lights": {
            "on_count": 1,
            "on": [{"title": "Bathroom Light 1", "room": "Bathroom"}],
        },
        "heating": [],
        "attention": [{"title": "Livingroom TRV", "value": "10%"}],
        "presence": {"count": 0, "people": []},
        "low_batteries": {
            "threshold_percent": 20,
            "count": 2,
            "items": [
                {"device": "Livingroom TRV", "value": 10.0, "unit": "%"},
                {"device": "Fridge Door", "value": 14.0, "unit": "%"},
            ],
        },
        "climate": {"warmest": [], "most_humid": []},
    }
    return {"data": data, "required_facts": _required_facts(data)}


def test_fallback_is_natural_and_complete():
    message = _fallback(sample_evidence())
    assert "It's Morning mode" in message
    assert "2 motion sensors are active" in message
    assert "Bedroom 3 Presence Sensor" in message
    assert "Livingroom FP300" in message
    assert "Front Door" in message
    assert "Bathroom Light 1" in message
    assert "low battery" in message
    assert "states read" not in message.lower()


def test_fact_manifest_covers_every_non_empty_authoritative_domain():
    manifest = {item["domain"]: item for item in _fact_manifest(sample_evidence())}
    assert manifest["mode"]["required"] is True
    assert manifest["motion"] == {
        "domain": "motion",
        "count": 2,
        "names": ["Bedroom 3 Presence Sensor", "Livingroom FP300"],
        "required": True,
    }
    assert manifest["contacts"]["names"] == ["Front Door"]
    assert manifest["lights"]["names"] == ["Bathroom Light 1"]
    assert manifest["low_batteries"]["names"] == ["Livingroom TRV", "Fridge Door"]


def test_synthesis_validation_requires_all_non_empty_domain_names():
    evidence = sample_evidence()
    good = (
        "It's Morning mode. Two motion sensors are active: Bedroom 3 Presence Sensor and Livingroom FP300. "
        "One contact is open: Front Door. One light is on: Bathroom Light 1. "
        "Two devices have low batteries: Livingroom TRV and Fridge Door."
    )
    assert _contains_required_facts(good, evidence) is True
    assert _contains_required_facts(good.replace("Front Door", ""), evidence) is False
    assert _contains_required_facts(good.replace("Bathroom Light 1", ""), evidence) is False
    assert _contains_required_facts(good.replace("Fridge Door", ""), evidence) is False


def test_counts_must_appear_in_the_correct_domain_sentence():
    evidence = sample_evidence()
    wrong = (
        "It's Morning mode. Two motion sensors are active: Bedroom 3 Presence Sensor and Livingroom FP300. "
        "Front Door is open. Bathroom Light 1 is on. "
        "Two devices have low batteries: Livingroom TRV and Fridge Door."
    )
    assert _contains_required_facts(wrong, evidence) is False


def test_zero_motion_accepts_no_none_or_zero_wording():
    evidence = deepcopy(sample_evidence())
    evidence["data"]["motion"] = {"active_count": 0, "active": []}
    assert _contains_required_facts(
        "It's Morning mode. No motion sensors are active. One contact is open: Front Door. "
        "One light is on: Bathroom Light 1. Two devices have low batteries: Livingroom TRV and Fridge Door.",
        evidence,
    ) is True
    assert _contains_required_facts(
        "It's Morning mode. Motion sensors are inactive. One contact is open: Front Door. "
        "One light is on: Bathroom Light 1. Two devices have low batteries: Livingroom TRV and Fridge Door.",
        evidence,
    ) is False


def test_number_words_are_accepted_for_counts():
    evidence = sample_evidence()
    message = (
        "It's Morning mode. Two motion sensors are active: Bedroom 3 Presence Sensor and Livingroom FP300. "
        "One contact is open: Front Door. One light is on: Bathroom Light 1. "
        "Two devices have low batteries: Livingroom TRV and Fridge Door."
    )
    assert _contains_required_facts(message, evidence) is True


def test_states_read_heading_and_mechanical_motion_wording_are_removed_and_capitalised():
    text = _normalise_answer(
        "Home summary: There are 3 active-motion devices in the house (13 states read). Please note that batteries are low."
    )
    assert text == "There are 3 motion sensors in the house. Batteries are low."


def test_non_household_climate_sources_are_excluded():
    assert _is_household_climate("Hub Info (C8 Pro)", "Bridge") is False
    assert _is_household_climate("Fridge Meter", "Appliances") is False
    assert _is_household_climate("Weather Open-Meteo", "Climate") is False
    assert _is_household_climate("Hallway Meter", "Climate") is True


def test_life360_battery_is_not_reported_as_replaceable_device_battery():
    assert _is_household_battery("Tahmid Khan", "Life360") is False
    assert _is_household_battery("Livingroom TRV", "Thermostat & TRV's") is True
