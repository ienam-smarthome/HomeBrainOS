from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_control_service import DeviceControlService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


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


TOILET_LIGHT = {
    "id": "9001", "label": "Toilet Light", "roomName": "Toilet",
    "capabilities": ["Actuator", "Refresh", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


@pytest.mark.asyncio
async def test_smuggled_second_action_is_stripped_and_the_routine_part_still_runs():
    """Regression test for a real live production failure: "turn off toilet
    light and restart the hub" was sent to this tool as a single call with
    device_names=["toilet light and restart the hub"]. A prompt-only fix
    (0.10.356) asked the model not to do this, but the same live model kept
    doing it anyway -- so this is the deterministic backstop: strip the
    recognisable second action, execute the routine part against the
    correctly-resolved device, and tell the user the second action needs
    its own request rather than silently dropping it or corrupting
    resolution."""

    mcp = ControlMCP([TOILET_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["toilet light and restart the hub"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    assert result.data["succeeded"][0]["id"] == "9001"
    assert "restart the hub" in result.data["note"]
    assert "ask for it separately" in result.data["note"]
    executed_commands = [
        arguments for gateway, arguments in mcp.calls
        if arguments.get("tool") == "hub_call_device_command"
    ]
    assert len(executed_commands) == 1
    assert executed_commands[0]["args"]["command"] == "off"
    # The hub must never actually be restarted from this regex match --
    # only the device command tool is called.
    assert all(
        arguments.get("tool") != "hub_restart" for _gateway, arguments in mcp.calls
    )


@pytest.mark.asyncio
async def test_ordinary_device_name_with_no_second_action_is_unaffected():
    mcp = ControlMCP([TOILET_LIGHT])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["toilet light"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    assert "note" not in result.data


BEDROOM1_LIGHT = {
    "id": "7057", "label": "Bedroom 1 Light", "roomName": "Bedroom 1",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
BEDROOM1_FLOOR_LAMP = {
    "id": "7028", "label": "My Floor Lamp", "roomName": "Bedroom 1",
    "capabilities": ["Actuator", "Refresh", "ChangeLevel", "SwitchLevel", "Light", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}
# Real device pulled live from the actual hub: a smart plug whose label
# normalizes to exactly the same string as the room "Bedroom 1" once its
# "(MQTT)" qualifier is stripped, but which lives in a different room
# ("Sockets"), not "Bedroom 1" at all.
BEDROOM1_MQTT_SOCKET = {
    "id": "7101", "label": "Bedroom1 (MQTT)", "roomName": "Sockets",
    "capabilities": ["Actuator", "Refresh", "Switch"],
    "attributes": [{"name": "switch", "dataType": "ENUM", "value": "on"}],
}


@pytest.mark.asyncio
async def test_room_name_in_device_names_acts_on_the_room_not_a_lookalike_device():
    """Regression test for a real live failure: "turn off Bedroom 1" (a
    real room containing two lights) resolved to a single, unrelated smart
    plug labelled "Bedroom1 (MQTT)" living in a different room, because
    that label happens to normalize to the exact same string as the room
    name and ordinary per-name fuzzy resolution has no room awareness.
    """

    mcp = ControlMCP([BEDROOM1_LIGHT, BEDROOM1_FLOOR_LAMP, BEDROOM1_MQTT_SOCKET])
    service = DeviceControlService(mcp, recorder)

    result = await service.execute({
        "device_names": ["Bedroom 1"],
        "device_kind": "auto",
        "command": "off",
    })

    assert result.data["success"] is True
    succeeded_ids = {item["id"] for item in result.data["succeeded"]}
    assert succeeded_ids == {"7057", "7028"}
    assert "7101" not in succeeded_ids


class FailingControlMCP(ControlMCP):
    """Same as ControlMCP, but every hub_call_device_command dispatch
    fails outright -- reproducing what was observed live for "living room
    light": both Livingroom Light 1 and Livingroom Light 2 landed in the
    "Failed:" bucket (command_sent False), not the "unverified" bucket."""

    async def call_tool(self, gateway, arguments):
        if arguments.get("tool") == "hub_call_device_command":
            self.calls.append((gateway, arguments))
            return MCPToolResult(
                "hub_manage_devices", arguments, {}, "error",
                {"success": False, "error": "Hubitat rejected the command."},
                is_error=True,
            )
        return await super().call_tool(gateway, arguments)


@pytest.mark.asyncio
async def test_dispatch_failure_records_device_control_failures_metric():
    """Regression test for a live-observed bug: a routine light/switch
    command that failed at the Hubitat dispatch layer touched none of the
    fixed outcome counters, so classify_completed_request() fell through
    to its default "success" -- the WebUI showed a green Success badge
    next to a message that literally read "Failed: <device>.". This
    asserts the new device_control_failures counter closes that gap.
    """

    mcp = FailingControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await service.execute({
            "device_names": ["Hallway Light 1", "Hallway Light 2"],
            "device_kind": "auto",
            "command": "on",
        })
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert result.data["success"] is False
    assert len(result.data["failed"]) == 2
    assert snapshot["counters"]["device_control_failures"] == 1


@pytest.mark.asyncio
async def test_successful_dispatch_does_not_record_device_control_failures_metric():
    mcp = ControlMCP([HALLWAY_LIGHT_1, HALLWAY_LIGHT_2])
    service = DeviceControlService(mcp, recorder)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await service.execute({
            "device_names": ["Hallway Light 1", "Hallway Light 2"],
            "device_kind": "auto",
            "command": "on",
        })
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert result.data["success"] is True
    assert "device_control_failures" not in snapshot["counters"]
