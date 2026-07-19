from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_capability_filter import (  # noqa: E402
    install_control_graph_capability_filter,
    is_control_capable,
)
from control_agent_graph import ControlDeviceGraph  # noqa: E402
from control_agent_intent import ControlTargetIntent  # noqa: E402


def device(device_id: str, label: str, room: str, states: dict):
    return {
        "id": device_id,
        "name": label,
        "label": label,
        "room": room,
        "disabled": False,
        "currentStates": states,
    }


BEDROOM_LIGHT = device("7057", "Bedroom 1 Light", "Bedroom 1", {"switch": "off", "level": 80})
BEDROOM_LUX = device("7381", "FP2 Bedroom 3 Lux", "Bedroom 3", {})
LIGHT_SENSOR = device("9001", "Aqara Light Sensor T1", "Bedroom 3", {"illuminance": 12})
FAN = device("9002", "Standing Fan", "Living Room", {"switch": "on"})
EMPTY_STATE_FAN = device("9003", "Ceiling Fan", "Bedroom 2", {})
PRAYER_TIMES = device("9004", "Prayer times", "Apps", {})


def test_control_capability_prefers_actuation_evidence_and_rejects_sensor_labels():
    assert is_control_capable(BEDROOM_LIGHT) is True
    assert is_control_capable(FAN) is True
    assert is_control_capable(BEDROOM_LUX) is False
    assert is_control_capable(LIGHT_SENSOR) is False
    assert is_control_capable(PRAYER_TIMES) is False


def test_clear_actuator_survives_temporarily_empty_compact_state():
    assert is_control_capable(EMPTY_STATE_FAN) is True


def test_capability_and_command_metadata_are_valid_control_evidence():
    capability_only = {
        **BEDROOM_LUX,
        "id": "9100",
        "capabilities": ["SwitchLevel"],
    }
    command_only = {
        **BEDROOM_LUX,
        "id": "9101",
        "commands": [{"name": "setLevel"}],
    }

    assert is_control_capable(capability_only) is True
    assert is_control_capable(command_only) is True


def test_lux_and_light_sensors_are_absent_from_control_graph_and_candidates():
    install_control_graph_capability_filter()
    graph = ControlDeviceGraph(
        [BEDROOM_LIGHT, BEDROOM_LUX, LIGHT_SENSOR, FAN, EMPTY_STATE_FAN, PRAYER_TIMES]
    )

    assert [node.label for node in graph.nodes] == [
        "Bedroom 1 Light",
        "Standing Fan",
        "Ceiling Fan",
    ]

    exact = graph.resolve(ControlTargetIntent(name_hint="Bedroom 1 Light"))
    assert [node.id for node in exact.nodes] == ["7057"]

    unresolved = graph.resolve(ControlTargetIntent(name_hint="bedroom light sensor"))
    candidate_labels = [node.label for node in unresolved.candidates]
    assert "FP2 Bedroom 3 Lux" not in candidate_labels
    assert "Aqara Light Sensor T1" not in candidate_labels


def test_real_screenshot_candidate_set_keeps_only_controllable_devices():
    install_control_graph_capability_filter()
    devices = [
        BEDROOM_LIGHT,
        device("7026", "Bedroom 2 Light", "Bedroom 2", {"switch": "off"}),
        device("7058", "Bedroom 3 Light", "Bedroom 3", {"switch": "off"}),
        device("7044", "Big lamp", "Bedroom 3", {"switch": "off"}),
        BEDROOM_LUX,
    ]
    graph = ControlDeviceGraph(devices)

    assert [node.label for node in graph.nodes] == [
        "Bedroom 1 Light",
        "Bedroom 2 Light",
        "Bedroom 3 Light",
        "Big lamp",
    ]
