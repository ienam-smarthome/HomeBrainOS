from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_room_inventory import FastFallbackRouter  # noqa: E402
from hub_cpu_probe import parse_cpu_info  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


class FakeRoomMCP:
    async def list_tools(self):
        return [
            MCPTool("hub_list_rooms", "rooms", {"type": "object", "properties": {}}),
            MCPTool("hub_list_devices", "devices", {"type": "object", "properties": {}}),
        ]

    async def supported_arguments(self, _name, desired):
        return desired

    async def call_tool(self, name, arguments):
        if name == "hub_list_rooms":
            data = {
                "rooms": [
                    {"id": "1", "name": "Apps"},
                    {"id": "2", "name": "Bedroom 1"},
                ]
            }
        elif name == "hub_list_devices":
            data = {
                "devices": [
                    {
                        "id": "101",
                        "label": "HomeBrain Report",
                        "room": "Apps",
                        "deviceType": "Virtual Device",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "102",
                        "label": "MCP Status Display",
                        "room": {"name": "Apps"},
                        "deviceType": "Virtual Display",
                        "currentStates": {"status": "ready"},
                    },
                    {
                        "id": "201",
                        "label": "Bedroom 1 Light",
                        "room": "Bedroom 1",
                        "deviceType": "Generic Zigbee Light",
                        "currentStates": {"switch": "off"},
                    },
                ]
            }
        else:
            raise AssertionError(f"Unexpected tool: {name}")
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_list_apps_routes_directly_to_mcp_fast():
    decision = classify_query("List Apps")
    assert decision.route == "mcp-fast"


def test_list_apps_returns_only_devices_in_exact_apps_room():
    answer = asyncio.run(FastFallbackRouter(FakeRoomMCP()).answer("List Apps"))

    assert answer["success"] is True
    assert answer["intent"] == "fallback-room-devices"
    assert answer["room"] == "Apps"
    assert "HomeBrain Report" in answer["message"]
    assert "MCP Status Display" in answer["message"]
    assert "Bedroom 1 Light" not in answer["message"]
    assert answer["display"]["kind"] == "room-device-inventory"
    assert answer["display"]["metrics"][0]["value"] == "2"


def test_explicit_room_wording_also_matches():
    answer = asyncio.run(
        FastFallbackRouter(FakeRoomMCP()).answer("Show devices under Apps room")
    )
    assert answer["intent"] == "fallback-room-devices"
    assert answer["room"] == "Apps"


def test_hub_info_load_and_percent_format_returns_percentage():
    cpu = parse_cpu_info("CPU Load/Load% 0.6 / 15.0 %")
    assert cpu["available"] is True
    assert cpu["mode"] == "percent"
    assert cpu["load_average"] == 0.6
    assert cpu["percent"] == 15.0
    assert cpu["value"] == "15%"
    assert cpu["derived_percent"] is False


def test_load_average_and_processors_derives_percentage():
    cpu = parse_cpu_info("Processors: 4\nLoad average: 0.6")
    assert cpu["available"] is True
    assert cpu["mode"] == "percent"
    assert cpu["percent"] == 15.0
    assert cpu["value"] == "15.0%"
    assert cpu["derived_percent"] is True
