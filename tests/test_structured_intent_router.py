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


def test_contracted_bathroom_happening_is_room_status():
    result = route("what's happening in the bathroom?")
    assert result.intent == "room_status"
    assert result.room == "Bathroom"


def test_contracted_whats_on_in_bathroom_is_room_status():
    result = route("what's on in the bathroom?")
    assert result.intent == "room_status"
    assert result.room == "Bathroom"


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


def test_generic_dehumidifier_command_requires_clarification():
    class App:
        @staticmethod
        def all_devices():
            return [
                {'id': '1', 'label': 'Dehumidifier 1', 'name': 'Tuya Zigbee Metering SmartPlug', 'category': 'device'},
                {'id': '2', 'label': 'Dehumidifier 2', 'name': 'Dehumidifier 2', 'category': 'power_device', 'switch': 'on'},
            ]

        @staticmethod
        def command_devices(_devices, _command):
            raise AssertionError('an ambiguous command must not be executed')

    answer = module._voice_dehumidifier_command(App, 'turn on dehumidifier')
    assert answer is not None
    assert answer['success'] is False
    assert answer['needs_clarification'] is True
    assert answer['matched'] == ['Dehumidifier 1', 'Dehumidifier 2']


def test_numbered_humidifier_alias_keeps_plausible_smart_plug():
    calls = []

    class App:
        @staticmethod
        def all_devices():
            return [
                {'id': '1', 'label': 'Dehumidifier 1', 'name': 'Tuya Zigbee Metering SmartPlug', 'category': 'device'},
                {'id': '2', 'label': 'Dehumidifier 2', 'name': 'Dehumidifier 2', 'category': 'power_device', 'switch': 'on'},
            ]

        @staticmethod
        def command_devices(devices, command):
            calls.append(([device['id'] for device in devices], command))
            return {'success': True, 'message': 'sent'}

    answer = module._voice_dehumidifier_command(App, 'turn on the humidifier one')
    assert answer is not None
    assert answer['success'] is True
    assert calls == [(['1'], 'on')]
