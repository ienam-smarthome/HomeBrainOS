from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_control_service import DeviceControlService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


# Real hallway devices pulled live from the actual Hubitat hub via
# hub_get_device -- this exact pair is what "hallway lights at 11:11pm"
# should resolve to once the smuggled time is stripped.
HALLWAY_LIGHT_1 = {
    "id": "7046", "label": "Hallway Light 1", "roomName": "Hallway",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
HALLWAY_LIGHT_2 = {
    "id": "7037", "label": "Hallway Light 2", "roomName": "Hallway",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


class ControlMCP:
    def __init__(self, devices):
        self.devices = devices
        self.calls = []

    async def get_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        if arguments.get("tool") == "hub_call_device_command":
            command = arguments["args"]["command"]
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "ok",
                {"success": True, "waitFor": {"converged": True, "value": command}},
            )
        if arguments.get("tool") == "hub_list_devices":
            return MCPToolResult(
                "hub_read_devices", arguments, {}, "ok", {"devices": self.devices}
            )
        raise AssertionError(("unexpected tool call", gateway, arguments))


def recorder(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_smuggled_time_in_device_names_is_refused_not_misexecuted():
    """The bug this guards: a request like 'turn on hallway lights at
    11:11pm' has no dedicated time parameter on this tool, so the model
    puts the whole phrase into device_names. Executing on that raw string
    either silently ignores the requested time and acts immediately (wrong)
    or fails to resolve the device at all because the name is corrupted
    (confusing). Neither is acceptable; this must refuse with a clear
    explanation instead.
    """

    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["hallway lights at 11:11pm"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.is_error is True
    assert result.data["success"] is False
    assert result.data["requested_time"] == "23:11"
    assert "one-time" in result.data["error"].lower() or "one-off" in result.data["error"].lower()
    # Must not have attempted to execute anything against the hub.
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_smuggled_time_in_room_is_also_refused():
    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "room": "hallway at 6am",
        "device_names": [],
        "device_kind": "light",
        "command": "off",
    })

    assert result.is_error is True
    assert result.data["requested_time"] == "06:00"
    assert result.data["room"] == "hallway"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_normal_immediate_command_is_unaffected_by_the_time_check():
    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Hallway Light 1"],
        "device_kind": "auto",
        "command": "on",
    })

    assert result.data["success"] is True
    assert result.data["executed"] == 1
    assert result.data["succeeded"][0]["id"] == "7046"
    executed_commands = [
        arguments for gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    ]
    assert len(executed_commands) == 1
    assert executed_commands[0]["args"]["command"] == "on"


@pytest.mark.asyncio
async def test_invalid_arguments_still_rejected_before_the_time_check():
    mcp = ControlMCP([HALLWAY_LIGHT_1])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Hallway Light 1"],
        "room": "Hallway",  # both room and device_names set -- invalid
        "device_kind": "auto",
        "command": "on",
    })

    assert result.is_error is True
    assert "Provide exactly one of room or device_names" in result.data["error"]
