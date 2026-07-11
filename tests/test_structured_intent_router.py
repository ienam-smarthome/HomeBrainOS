from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "homebrainos"
    / "rootfs"
    / "app"
    / "natural_intelligence.py"
)

spec = importlib.util.spec_from_file_location("natural_intelligence", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


def route(query: str):
    return module.classify_intent(query)


def test_bathroom_status_is_room_status_glance():
    result = route("bathroom status")
    assert result.intent == "room_status"
    assert result.room == "Bathroom"
    assert result.detail_level == "glance"
    assert result.confidence >= 0.9


def test_detailed_room_status_is_explicit():
    result = route("show detailed bathroom status")
    assert result.intent == "room_status"
    assert result.room == "Bathroom"
    assert result.detail_level == "detailed"


def test_diagnostic_room_status_is_explicit():
    result = route("diagnose bathroom devices")
    assert result.room == "Bathroom"
    assert result.detail_level == "diagnostic"


def test_power_switch_state_is_not_energy():
    result = route("is the bathroom power switch on")
    assert result.intent == "device_state"


def test_live_power_usage_is_energy():
    result = route("what is using the most power right now")
    assert result.intent == "energy"


def test_command_is_never_classified_as_advice():
    result = route("turn off dehumidifier one")
    assert result.intent == "command"
    assert result.action == "command"


def test_existing_intent_api_remains_compatible():
    assert module._intent("what is using power right now") == "energy"
    assert module._intent("turn off dehumidifier one") == "home_context"