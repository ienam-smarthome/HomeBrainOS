from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_groups import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.reads = 0
        self.commands: list[dict] = []

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List devices",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_call_device_command",
                description="Control device",
                input_schema={
                    "type": "object",
                    "properties": {
                        "deviceId": {"type": "string"},
                        "command": {"type": "string"},
                        "params": {"type": "array"},
                    },
                },
            ),
        ]

    async def get_tool(self, name):
        return next((tool for tool in await self.list_tools() if tool.name == name), None)

    async def supported_arguments(self, name, desired):
        return desired

    async def call_tool(self, name, arguments):
        if name == "hub_list_devices":
            self.reads += 1
            hallway_state = "on" if self.reads == 1 else "off"
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "devices": [
                        {
                            "id": "1",
                            "label": "Hallway Light 1",
                            "name": "Generic Zigbee Switch",
                            "room": "Hallway",
                            "currentStates": {"switch": hallway_state},
                        },
                        {
                            "id": "2",
                            "label": "Hallway Light 2",
                            "name": "Generic Zigbee Switch",
                            "room": "Hallway",
                            "currentStates": {"switch": hallway_state},
                        },
                        {
                            "id": "3",
                            "label": "Hallway TRV",
                            "name": "Thermostatic Radiator Valve",
                            "room": "Hallway",
                            "currentStates": {"switch": "on"},
                        },
                        {
                            "id": "4",
                            "label": "Shower Light",
                            "name": "Generic Zigbee Switch",
                            "room": "Bathroom",
                            "currentStates": {"switch": "on"},
                        },
                        {
                            "id": "5",
                            "label": "HallwayCAM (MQTT)",
                            "name": "Camera",
                            "room": "Hallway",
                            "currentStates": {"switch": "on"},
                        },
                    ]
                },
                is_error=False,
            )

        if name == "hub_call_device_command":
            self.commands.append(arguments)
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="Command accepted",
                data={"success": True},
                is_error=False,
            )

        raise AssertionError((name, arguments))


def test_turn_off_hallway_lights_controls_and_verifies_both_lights(monkeypatch):
    fake = FakeMCP()

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("fast_fallback_groups.asyncio.sleep", no_sleep)
    answer = asyncio.run(
        FastFallbackRouter(fake).answer("Turn off Hallway Lights")
    )

    assert answer["success"] is True
    assert answer["intent"] == "fallback-device-group-control-confirmed"
    assert answer["matched_devices"] == 2
    assert answer["confirmed_devices"] == 2
    assert answer["failed_devices"] == 0
    assert [item["title"] for item in answer["display"]["items"]] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    assert fake.commands == [
        {"deviceId": "1", "command": "off", "params": []},
        {"deviceId": "2", "command": "off", "params": []},
    ]
    assert "Hallway TRV" not in answer["message"]
    assert "Shower Light" not in answer["message"]
    assert "HallwayCAM" not in answer["message"]


def test_group_matching_supports_all_lights_but_excludes_other_switches():
    candidates = asyncio.run(FakeMCP().call_tool("hub_list_devices", {})).data["devices"]
    matched = FastFallbackRouter._group_candidates("all lights", candidates)
    assert [item["label"] for item in matched] == [
        "Hallway Light 1",
        "Hallway Light 2",
        "Shower Light",
    ]


def test_singular_device_name_is_not_treated_as_group():
    assert FastFallbackRouter._group_request("hallway light 1") is None
