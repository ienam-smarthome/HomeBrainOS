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
    assert parse_room_status_request("show the Living Room states") == "Living Room"
    assert parse_room_status_request("check hub health status") is None
    assert parse_room_status_request("check the firmware status") is None
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


def _linked_fp2_devices():
    """Native MCP detailed devices advertise the child's parentDeviceId."""
    return _fixtures() + [
        {
            **_device(200, "FP2 Livingroom sensor (homekit)", "Living Room", {
                "motion": "active", "presence": "present", "lastActivity": "2026-10-10T14:55:00Z",
            }, ["MotionSensor", "PresenceSensor"]),
            "parentDeviceId": "7334",
        },
        {
            **_device(201, "FP2 Livingroom Lux (homekit)", "Living Room", {
                "illuminance": 0,
            }, ["IlluminanceMeasurement"]),
            "parentDeviceId": "7334",
        },
    ]


def _fp2_parent(*, health="offline", hap="connecting (live)"):
    return _device(7334, "FP2 Livingroom", "Unassigned", {
        "healthStatus": health,
        "hapStatus": hap,
        "firmware": "1.3.6",
    })


def test_parent_id_link_comes_from_native_metadata_not_labels():
    from room_status_snapshot import linked_parent_ids

    linked = _linked_fp2_devices()
    assert linked_parent_ids(linked) == ["7334"]
    assert linked_parent_ids(linked + [_fp2_parent()]) == []
    # A coincidentally named device with no parent ID is not a dependency.
    assert linked_parent_ids(_fixtures()) == []


def test_parent_offline_qualifies_all_dependent_child_telemetry():
    devices = _linked_fp2_devices()
    output = format_room_status(
        "Living Room", devices, parent_records={"7334": _fp2_parent()}
    )
    current, health = output.split("### Device health")
    assert "FP300 Livingroom sensor" in current
    assert "FP2 Livingroom sensor" not in current
    assert "FP2 Livingroom Lux" not in current
    assert "motion: active" in current  # Unrelated FP300 remains trustworthy
    assert "illuminance: 0 lux" not in current
    assert "Linked parent FP2 Livingroom (ID 7334): Offline" in health
    assert "healthStatus: offline" in health
    assert "hapStatus: connecting (live)" in health
    assert "FP2 Livingroom sensor (homekit): Parent connection offline" in health
    assert "presence=present" in health
    assert "FP2 Livingroom Lux (homekit): Parent connection offline" in health
    assert "illuminance=0" in health
    assert "freshness unverified" in health


def test_missing_parent_access_never_claims_offline_as_proven():
    output = format_room_status(
        "Living Room", _linked_fp2_devices(),
        parent_read_failures={"7334"},
    )
    current, health = output.split("### Device health")
    assert "FP2 Livingroom sensor" not in current
    assert "FP2 Livingroom Lux" not in current
    assert "Linked parent Device 7334 (ID 7334): Connection unverified" in health
    assert "Check device selection in MCP Rule Server" in health
    assert "FP2 Livingroom sensor (homekit): Parent health unverified" in health
    assert "Parent connection offline" not in health
    assert "healthStatus: offline" not in health


def test_recovered_parent_restores_child_activity_without_guessing():
    output = format_room_status(
        "Living Room", _linked_fp2_devices(),
        parent_records={"7334": _fp2_parent(health="online", hap="connected (live)")},
    )
    current = output.split("### Device health")[0]
    assert "FP2 Livingroom sensor (homekit)** — motion: active" in current
    assert "FP2 Livingroom sensor (homekit)** — presence: present" in current
    assert "FP2 Livingroom Lux (homekit)** — illuminance: 0 lux" in current
    assert "Parent connection offline" not in output
    assert "Linked parent" not in output


def test_missing_parent_health_fields_cannot_be_assumed_healthy():
    unknown = _device(7334, "FP2 Livingroom", "Unassigned", {})
    output = format_room_status(
        "Living Room", _linked_fp2_devices(),
        parent_records={"7334": unknown},
    )
    current, health = output.split("### Device health")
    assert "FP2 Livingroom sensor" not in current
    assert "FP2 Livingroom sensor (homekit): Parent health unverified" in health
    assert "Linked parent FP2 Livingroom (ID 7334): Connection unverified" in health


def test_parent_in_room_devices_is_not_queried_separately():
    from room_status_snapshot import linked_parent_ids

    devices = _linked_fp2_devices() + [_fp2_parent()]
    assert linked_parent_ids(devices) == []
    output = format_room_status("Living Room", devices)
    assert "Parent connection offline" in output
    assert "FP2 Livingroom sensor (homekit)** — motion: active" not in output


class _ParentRoomMCP(_DetailedRoomMCP):
    def __init__(self, parent=None, *, unauthorized=False):
        super().__init__()
        self.parent = parent
        self.unauthorized = unauthorized

    async def get_cached_devices(self):
        return _linked_fp2_devices()

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        if arguments["tool"] == "hub_list_devices":
            assert arguments["args"] == {"detailed": True, "roomFilter": "Living Room"}
            return MCPToolResult(
                name, arguments, {}, "ok",
                {"devices": _linked_fp2_devices(), "count": 8, "total": 8},
            )
        assert arguments == {
            "tool": "hub_get_device", "args": {"deviceId": "7334"}
        }
        if self.unauthorized:
            return MCPToolResult(
                name, arguments, {}, "Device not found",
                {"success": False, "error": "Device not found: 7334"},
                is_error=True,
            )
        return MCPToolResult(name, arguments, {}, "ok", self.parent)


@pytest.mark.asyncio
async def test_agent_probes_only_authoritative_parent_and_surfaces_offline():
    mcp = _ParentRoomMCP(_fp2_parent())
    agent = UnifiedMCPAgent(mcp, "key")
    result = await agent.process_user_request_result(
        "check livingroom status and states", session_id="parent-offline-test"
    )
    assert len(mcp.calls) == 2
    assert mcp.calls[1][1]["args"]["deviceId"] == "7334"
    current, health = result.message.split("### Device health")
    assert "FP2 Livingroom sensor" not in current
    assert "FP2 Livingroom Lux" not in current
    assert "Linked parent FP2 Livingroom (ID 7334): Offline" in health
    assert any(
        entry.get("tool") == "hub_read_devices"
        and entry.get("arguments", {}).get("tool") == "hub_get_device"
        and entry.get("success") is True
        for entry in result.evidence
    )
    assert result.metrics["counters"].get("model_rounds", 0) == 0


@pytest.mark.asyncio
async def test_agent_unreadable_parent_preserves_evidence_without_false_offline():
    mcp = _ParentRoomMCP(unauthorized=True)
    agent = UnifiedMCPAgent(mcp, "key")
    result = await agent.process_user_request_result(
        "check livingroom status and states", session_id="parent-not-selected"
    )
    assert len(mcp.calls) == 2
    assert "Connection unverified" in result.message
    assert "Check device selection in MCP Rule Server" in result.message
    assert "FP2 Livingroom sensor (homekit): Parent health unverified" in result.message
    assert "Linked parent Device 7334 (ID 7334): Offline" not in result.message
    assert any(
        row.get("arguments", {}).get("tool") == "hub_get_device"
        and row.get("success") is False
        for row in result.evidence
    )
