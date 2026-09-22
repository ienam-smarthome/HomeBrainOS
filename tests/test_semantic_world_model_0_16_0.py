from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_world_model import (  # noqa: E402
    build_semantic_world,
    device_abilities,
    is_brightness_device,
    render_semantic_world,
    semantic_device_kinds,
)


LIGHT = {
    "id": "7805",
    "label": "Livingroom Light 1",
    "roomName": "Living Room",
    "capabilities": ["Light", "Switch", "SwitchLevel", "ColorTemperature"],
    "commands": ["on", "off", "setLevel", "setColorTemperature"],
    "attributes": [
        {"name": "switch", "value": "on"},
        {"name": "level", "value": 65},
        {"name": "colorTemperature", "value": 3000, "unit": "K"},
    ],
}

TRV = {
    "id": "7331",
    "label": "Livingroom TRV",
    "roomName": "Living Room",
    "capabilities": [
        "Thermostat",
        "ThermostatHeatingSetpoint",
        "TemperatureMeasurement",
        "Switch",
    ],
    "commands": [
        {"name": "setHeatingSetpoint"},
        {"name": "on"},
        {"name": "off"},
    ],
    "attributes": [
        {"name": "temperature", "value": 20.1, "unit": "°C"},
        {"name": "heatingSetpoint", "value": 21.0, "unit": "°C"},
        {"name": "switch", "value": "on"},
    ],
}


def test_world_model_derives_semantic_abilities_without_protocol_details() -> None:
    assert device_abilities(LIGHT) >= {
        "switch",
        "brightness",
        "color_temperature",
    }
    assert device_abilities(TRV) >= {
        "switch",
        "heating_setpoint",
        "temperature",
    }
    assert semantic_device_kinds(LIGHT)[0] == "light"
    assert "thermostat" in semantic_device_kinds(TRV)


def test_world_model_contains_canonical_names_rooms_and_abilities_but_no_ids_or_state() -> None:
    world = build_semantic_world([LIGHT, TRV])
    rendered = render_semantic_world(world)

    assert "Living Room" in rendered
    assert "Livingroom Light 1" in rendered
    assert "Livingroom TRV" in rendered
    assert "heating_setpoint" in rendered
    assert "brightness" in rendered

    # The semantic planner gets identity/capability vocabulary, not protocol
    # addresses, raw command names, or current-state evidence.
    assert "7805" not in rendered
    assert "7331" not in rendered
    assert "setHeatingSetpoint" not in rendered
    assert "setLevel" not in rendered
    assert '"value":65' not in rendered
    assert '"value":21' not in rendered
    assert world["live_state"] is False


def test_world_model_room_summary_aggregates_control_abilities() -> None:
    world = build_semantic_world([LIGHT, TRV])
    room = world["rooms"][0]

    assert room["name"] == "Living Room"
    assert room["devices"] == ["Livingroom Light 1", "Livingroom TRV"]
    assert "brightness" in room["abilities"]
    assert "heating_setpoint" in room["abilities"]


def test_render_world_is_bounded_and_drops_devices_cleanly() -> None:
    devices = [
        {
            **LIGHT,
            "id": str(index),
            "label": f"Very Long Light Device {index:02d}",
            "roomName": "Living Room",
        }
        for index in range(30)
    ]
    rendered = render_semantic_world(
        build_semantic_world(devices, max_devices=30),
        max_chars=900,
    )

    assert len(rendered) <= 900
    assert "Very Long Light Device 00" in rendered



def test_unlabelled_switchlevel_dimmer_is_semantic_brightness_device() -> None:
    hallway_dimmer = {
        "id": "h1",
        "label": "Hallway Main",
        "roomName": "Hallway",
        "capabilities": ["Switch", "SwitchLevel"],
        "commands": ["on", "off", "setLevel"],
        "attributes": [
            {"name": "switch", "value": "on"},
            {"name": "level", "value": 45},
        ],
    }

    assert is_brightness_device(hallway_dimmer) is True
    assert "brightness" in device_abilities(hallway_dimmer)
    assert "light" in semantic_device_kinds(hallway_dimmer)

    world = build_semantic_world([hallway_dimmer])
    assert world["rooms"] == [{
        "name": "Hallway",
        "abilities": ["brightness", "switch"],
        "devices": ["Hallway Main"],
    }]


def test_switchlevel_fan_is_not_reinterpreted_as_brightness() -> None:
    fan = {
        "id": "fan1",
        "label": "Hallway Fan",
        "roomName": "Hallway",
        "capabilities": ["Switch", "SwitchLevel", "FanControl"],
        "commands": ["on", "off", "setLevel", "setSpeed"],
        "attributes": [
            {"name": "switch", "value": "on"},
            {"name": "level", "value": 50},
            {"name": "speed", "value": "medium"},
        ],
    }

    assert is_brightness_device(fan) is False
    assert "brightness" not in device_abilities(fan)
    assert "fan_speed" in device_abilities(fan)


def test_switchlevel_shade_is_not_reinterpreted_as_brightness() -> None:
    shade = {
        "id": "shade1",
        "label": "Hallway Blind",
        "roomName": "Hallway",
        "capabilities": ["SwitchLevel", "WindowShade"],
        "commands": ["setLevel", "setPosition", "open", "close"],
        "attributes": [{"name": "level", "value": 50}],
    }

    assert is_brightness_device(shade) is False
    assert "brightness" not in device_abilities(shade)



def test_hue_dimmer_remote_parent_level_telemetry_is_not_a_brightness_actuator() -> None:
    remote_parent = {
        "id": "3927",
        "label": "Hallway dimmer",
        "roomName": "",
        "capabilities": ["Battery", "PushableButton", "SwitchLevel"],
        "commands": ["setLevel"],
        "attributes": [
            {"name": "battery", "value": 82},
            {"name": "level", "value": None},
        ],
    }
    hallway_light_1 = {
        "id": "7829",
        "label": "Hallway Light 1",
        "roomName": "Hallway",
        "capabilities": [
            "Actuator", "ChangeLevel", "Light", "Refresh", "Switch", "SwitchLevel"
        ],
        "commands": ["on", "off", "setLevel", "startLevelChange", "stopLevelChange"],
        "attributes": [{"name": "level", "value": 50}],
    }
    hallway_light_2 = {
        **hallway_light_1,
        "id": "7830",
        "label": "Hallway Light 2",
    }

    assert is_brightness_device(remote_parent) is False
    assert "brightness" not in device_abilities(remote_parent)
    assert is_brightness_device(hallway_light_1) is True
    assert is_brightness_device(hallway_light_2) is True

    world = build_semantic_world([remote_parent, hallway_light_1, hallway_light_2])
    hallway = next(room for room in world["rooms"] if room["name"] == "Hallway")
    assert hallway["devices"] == ["Hallway Light 1", "Hallway Light 2"]
    assert "brightness" in hallway["abilities"]


def test_bare_level_attribute_does_not_create_mutating_brightness_ability() -> None:
    telemetry_only = {
        "id": "telemetry1",
        "label": "Remote level telemetry",
        "capabilities": ["Battery"],
        "attributes": [{"name": "level", "value": 50}],
    }

    assert is_brightness_device(telemetry_only) is False
    assert "brightness" not in device_abilities(telemetry_only)
