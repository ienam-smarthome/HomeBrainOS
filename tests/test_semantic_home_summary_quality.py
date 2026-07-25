from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_home_evidence import _is_household_battery, _is_household_climate, _required_facts  # noqa: E402
from semantic_home_summary_agent import _contains_required_facts, _fallback, _normalise_answer  # noqa: E402


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
        "contacts": {"open_count": 0, "open": []},
        "lights": {"on_count": 0, "on": []},
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
    assert "Morning mode" in message
    assert "2 motion sensors are active" in message
    assert "Bedroom 3 Presence Sensor" in message
    assert "Livingroom FP300" in message
    assert "low battery" in message
    assert "states read" not in message.lower()


def test_synthesis_validation_requires_exact_motion_names_and_battery_fact():
    evidence = sample_evidence()
    good = (
        "The home is in Morning mode. Two motion sensors are active: Bedroom 3 Presence Sensor and "
        "Livingroom FP300. Two devices have low batteries."
    )
    assert _contains_required_facts(good.replace("Two", "2"), evidence) is True
    assert _contains_required_facts("The home is in Morning mode and 2 motion sensors are active.", evidence) is False


def test_states_read_and_repeated_heading_are_removed():
    text = _normalise_answer("Home summary: The home is calm (13 states read).")
    assert text == "The home is calm."


def test_non_household_climate_sources_are_excluded():
    assert _is_household_climate("Hub Info (C8 Pro)", "Bridge") is False
    assert _is_household_climate("Fridge Meter", "Appliances") is False
    assert _is_household_climate("Weather Open-Meteo", "Climate") is False
    assert _is_household_climate("Hallway Meter", "Climate") is True


def test_life360_battery_is_not_reported_as_replaceable_device_battery():
    assert _is_household_battery("Tahmid Khan", "Life360") is False
    assert _is_household_battery("Livingroom TRV", "Thermostat & TRV's") is True
