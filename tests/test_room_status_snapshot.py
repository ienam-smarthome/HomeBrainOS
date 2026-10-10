"""Regression gates for deterministic, source-grounded room-status answers."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from room_status_snapshot import (  # noqa: E402
    format_room_status, parse_room_status_request, resolve_room,
)


def _device(device_id, label, room, attrs, caps=()):
    return {
        "id": str(device_id), "name": label, "label": label, "room": room,
        "capabilities": list(caps), "attributes": dict(attrs),
    }


def _fixtures():
    return [
        _device(7304, "Seeed Studio MR60BHA2 MQTT", "Living Room", {
            "sensorStatus": "offline", "mqttStatus": "connecting",
            "lastMessage": "offline", "lastError": "MQTT connect failed: MqttException",
            "switch": "on", "motion": "inactive", "presence": "not present",
            "illuminance": 8.7, "heartRate": 92,
        }, ["MotionSensor", "PresenceSensor", "IlluminanceMeasurement", "Switch"]),
        _device(101, "FP300 Livingroom sensor", "Living Room", {
            "motion": "active", "temperature": 23.6, "humidity": 45,
            "illuminance": 39, "battery": 100,
        }, ["MotionSensor", "TemperatureMeasurement", "RelativeHumidityMeasurement"]),
        _device(102, "Livingroom Light 1", "Living Room", {
            "switch": "off", "level": 50,
        }, ["Switch", "SwitchLevel", "Light"]),
        _device(103, "Livingroom Light 2", "Living Room", {
            "switch": "off", "level": 40,
        }, ["Switch", "Light"]),
        _device(104, "FP2 Livingroom socket", "Living Room", {"switch": "on"}, ["Switch"]),
        _device(105, "Kitchen Linptech", "Kitchen", {"illuminance": 69}, ["IlluminanceMeasurement"]),
    ]


def test_room_status_parser_is_narrow_and_resolves_name_alias():
    assert parse_room_status_request("check livingroom status and states") == "livingroom"
    assert parse_room_status_request("show the Living Room states") == "Living Room"\n    assert parse_room_status_request("check hub health status") is None\n    assert parse_room_status_request("check the firmware status") is None
    assert parse_room_status_request("why did the livingroom light turn on?") is None
    assert resolve_room("livingroom", _fixtures()) == "Living Room"
    assert resolve_room("unknown room", _fixtures()) is None


def test_offline_sensor_never_contaminates_current_occupancy_or_lux():
    output = format_room_status("Living Room", _fixtures())
    current = output.split("### Device health")[0]
    health = output.split("### Device health")[1]
    assert "FP300 Livingroom sensor" in current
    assert "motion: active" in current
    assert "illuminance: 39 lux" in current
    assert "Seeed Studio" not in current
    assert "8.7" not in current
    assert "Kitchen Linptech" not in output
    assert "**Seeed Studio MR60BHA2 MQTT: Offline.**" in health
    assert "sensorStatus: offline" in health
    assert "mqttStatus: connecting" in health
    assert "MQTT connect failed: MqttException" in health
    assert "Last reported, freshness unverified" in health
    assert "motion=inactive" in health
    assert "presence=not present" in health
    assert "illuminance=8.7" in health
    assert "switch=on" in health


def test_lights_and_room_environment_use_distinct_device_sources():
    output = format_room_status("Living Room", _fixtures())
    assert "Livingroom Light 1** — off (level 50%, last stored if off)" in output
    assert "Livingroom Light 2** — off (level 40%, last stored if off)" in output
    assert "FP2 Livingroom socket** — on" in output
    assert "temperature: 23.6°C" in output
    assert "humidity: 45%" in output
    assert "battery: 100%" in output


def test_no_health_observation_is_not_a_claim_all_online():
    devices = [_device(101, "Room sensor", "Living Room", {"motion": "inactive"})]
    output = format_room_status("Living Room", devices)
    assert "does **not** verify that every device is online" in output
    assert "Room sensor** — motion: inactive" in output


def test_unknown_room_and_partial_read_do_not_invent_complete_coverage():
    assert "No verified device records" in format_room_status("Kitchen", _fixtures()[:2])
    output = format_room_status("Living Room", _fixtures(), has_more=True)
    assert "Coverage warning" in output


class _DetailedRoomMCP:
    def __init__(self):
        self.calls = []

    async def get_cached_devices(self):
        return _fixtures()

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name != "hub_read_devices":
            raise AssertionError(name)
        if arguments != {
            "tool": "hub_list_devices",
            "args": {"detailed": True, "roomFilter": "Living Room"},
        }:
            raise AssertionError(arguments)
        return MCPToolResult(
            name, arguments, {}, "ok",
            {"devices": _fixtures(), "count": 6, "total": 6, "hasMore": False},
        )


@pytest.mark.asyncio
async def test_agent_room_status_direct_path_reads_once_and_keeps_offline_separate():
    mcp = _DetailedRoomMCP()
    agent = UnifiedMCPAgent(mcp, "key")
    outcome = await agent.process_user_request_result(
        "check livingroom status and states", session_id="room-status-regression"
    )
    message = outcome.message
    assert len(mcp.calls) == 1
    assert "Detailed room read" in message
    assert "### Device health" in message
    assert "MQTT connect failed: MqttException" in message
    assert "8.7" not in message.split("### Device health")[0]
    assert "Seeed Studio" not in message.split("### Device health")[0]
    assert any(item.get("tool") == "hub_read_devices" and item.get("success") for item in outcome.evidence)
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0
