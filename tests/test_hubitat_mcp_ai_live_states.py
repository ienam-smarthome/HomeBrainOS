from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_live import FastFallbackRouter, live_attributes  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List devices",
                input_schema={
                    "type": "object",
                    "properties": {
                        "detailed": {"type": "boolean"},
                        "format": {"type": "string"},
                        "fields": {"type": "array"},
                        "capabilityFilter": {"type": "string"},
                    },
                },
            )
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == "hub_list_devices"
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "devices": [
                    {
                        "id": "1",
                        "name": "Generic Zigbee Dimmer",
                        "label": "Bedroom 1 Light",
                        "room": "Bedroom 1",
                        "currentStates": {"switch": "on", "level": 70},
                    },
                    {
                        "id": "2",
                        "name": "Generic Zigbee Dimmer",
                        "label": "Bedroom 2 Light",
                        "room": "Bedroom 2",
                        "currentStates": {"switch": "on", "level": 45},
                    },
                    {
                        "id": "3",
                        "name": "Generic Zigbee Switch",
                        "label": "Hallway Light 1",
                        "room": "Hallway",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "4",
                        "name": "Generic Zigbee Switch",
                        "label": "Hallway Light 2",
                        "room": "Hallway",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "5",
                        "name": "Generic Zigbee Switch",
                        "label": "Toilet Light",
                        "room": "Toilet",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "6",
                        "name": "Smart Plug",
                        "label": "Fridge Socket",
                        "room": "Kitchen",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "7",
                        "name": "Generic Zigbee Dimmer",
                        "label": "Living Room Light",
                        "room": "Living Room",
                        "currentStates": {"switch": "off"},
                    },
                ],
                "count": 7,
                "total": 7,
            },
            is_error=False,
        )


def test_live_attributes_supports_current_states_and_detailed_attributes():
    assert live_attributes(
        {
            "currentStates": {"switch": "on", "level": 50},
            "attributes": [
                {"name": "battery", "value": 18},
                {"name": "temperature", "currentValue": 22.4},
            ],
        }
    ) == {
        "switch": "on",
        "level": 50,
        "battery": 18,
        "temperature": 22.4,
    }


def test_lights_on_uses_authoritative_summary_current_states():
    fake = FakeMCP()
    answer = asyncio.run(FastFallbackRouter(fake).answer("which lights are on"))

    assert answer["success"] is True
    assert answer["display"]["kind"] == "lights-on"
    assert answer["display"]["subtitle"] == "5 currently on"
    assert [item["title"] for item in answer["display"]["items"]] == [
        "Bedroom 1 Light",
        "Bedroom 2 Light",
        "Hallway Light 1",
        "Hallway Light 2",
        "Toilet Light",
    ]
    assert "Fridge Socket" not in answer["message"]
    assert "5 lights on" in answer["message"]

    assert fake.calls == [
        (
            "hub_list_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": ["id", "name", "label", "room", "currentStates"],
                "capabilityFilter": "Switch",
            },
        )
    ]


def test_switches_on_excludes_devices_identified_as_lights():
    fake = FakeMCP()
    answer = asyncio.run(FastFallbackRouter(fake).answer("which switches are on"))

    assert answer["display"]["subtitle"] == "1 currently on"
    assert [item["title"] for item in answer["display"]["items"]] == [
        "Fridge Socket"
    ]
