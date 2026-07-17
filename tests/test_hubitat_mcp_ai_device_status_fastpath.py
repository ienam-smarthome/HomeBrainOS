from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_status import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


class FakeDeviceMCP:
    async def list_tools(self):
        return [
            MCPTool("hub_list_rooms", "rooms", {"type": "object", "properties": {}}),
            MCPTool("hub_list_devices", "devices", {"type": "object", "properties": {}}),
        ]

    async def supported_arguments(self, _name, desired):
        return desired

    async def call_tool(self, name, arguments):
        if name == "hub_list_rooms":
            data = {"rooms": [{"id": "1", "name": "Apps"}]}
        elif name == "hub_list_devices":
            data = {
                "devices": [
                    {
                        "id": "501",
                        "label": "Dehumidifier 1",
                        "room": "Livingroom",
                        "deviceType": "Tuya Local Dehumidifier",
                        "currentStates": {
                            "switch": "on",
                            "power": 312.4,
                            "humidity": 57,
                            "temperature": 21.5,
                            "healthStatus": "online",
                        },
                    },
                    {
                        "id": "502",
                        "label": "Dehumidifier 2",
                        "room": "Bedroom 3",
                        "deviceType": "Tuya Local Dehumidifier",
                        "currentStates": {"switch": "off", "humidity": 61},
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


def test_show_device_status_routes_to_mcp_fast():
    assert classify_query("Show dehumidifier 1").route == "mcp-fast"


def test_show_device_returns_live_mcp_status():
    answer = asyncio.run(
        FastFallbackRouter(FakeDeviceMCP()).answer("Show dehumidifier 1")
    )

    assert answer["success"] is True
    assert answer["intent"] == "fallback-device-status"
    assert answer["device_label"] == "Dehumidifier 1"
    assert "Switch: On" in answer["message"]
    assert "Power: 312.4W" in answer["message"]
    assert answer["display"]["kind"] == "device-status"
    metrics = {
        item["label"]: item["value"]
        for item in answer["display"]["metrics"]
    }
    assert metrics["Switch"] == "On"
    assert metrics["Humidity"] == "57%"
    assert metrics["Temperature"] == "21.5°C"


def test_spoken_number_matches_digit_device_label():
    answer = asyncio.run(
        FastFallbackRouter(FakeDeviceMCP()).answer("Show dehumidifier one")
    )
    assert answer["success"] is True
    assert answer["device_label"] == "Dehumidifier 1"


def test_unhandled_fast_path_does_not_claim_ollama_is_unavailable():
    answer = asyncio.run(
        FastFallbackRouter(FakeDeviceMCP()).answer("Show hub logs and errors")
    )
    assert answer["success"] is False
    assert answer["intent"] == "fallback-unsupported"
    assert answer["fast_path_unhandled"] is True
    assert "Ollama was not attempted" in answer["message"]
    assert "Ollama is unavailable" not in answer["message"]
