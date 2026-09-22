from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_world_model import (  # noqa: E402
    build_semantic_world,
    device_abilities,
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



def _large_world_devices() -> list[dict]:
    devices = [
        {
            **LIGHT,
            "id": str(index),
            "label": f"Early Room Device {index:03d}",
            "roomName": "AAA Early Room",
        }
        for index in range(120)
    ]
    devices.extend(
        [
            {
                **LIGHT,
                "id": "hall-1",
                "label": "Hallway Light 1",
                "roomName": "Hallway",
            },
            {
                **LIGHT,
                "id": "hall-2",
                "label": "Hallway Light 2",
                "roomName": "Hallway",
            },
        ]
    )
    return devices


def test_large_world_keeps_room_abilities_beyond_device_detail_cap() -> None:
    world = build_semantic_world(_large_world_devices(), max_devices=64)

    # Hallway device details sort beyond the first 64 without focus, but the
    # room-level capability model must remain complete.
    assert all(
        item["room"] != "Hallway"
        for item in world["devices"]
    )
    hallway = next(room for room in world["rooms"] if room["name"] == "Hallway")
    assert hallway["device_count"] == 2
    assert "brightness" in hallway["abilities"]
    assert hallway["details_complete"] is False


def test_focus_text_prioritizes_referenced_room_device_details() -> None:
    world = build_semantic_world(
        _large_world_devices(),
        max_devices=64,
        focus_text="increase hallway brightness",
    )

    hallway_details = [
        item for item in world["devices"] if item["room"] == "Hallway"
    ]
    assert [item["name"] for item in hallway_details] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    assert all("brightness" in item["abilities"] for item in hallway_details)


def test_bounded_render_keeps_room_capabilities_after_detail_trimming() -> None:
    world = build_semantic_world(
        _large_world_devices(),
        max_devices=64,
        focus_text="increase hallway brightness",
    )
    rendered = render_semantic_world(world, max_chars=1200)

    import json

    payload = json.loads(rendered)
    assert len(rendered) <= 1200
    hallway = next(room for room in payload["rooms"] if room["name"] == "Hallway")
    assert "brightness" in hallway["abilities"]
    assert hallway["device_count"] == 2
