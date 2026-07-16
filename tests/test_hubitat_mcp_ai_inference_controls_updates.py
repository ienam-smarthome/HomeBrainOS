from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_verified import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from ollama_agent_inference import OllamaMCPAgent  # noqa: E402
from system_presenter_v2 import present_hub_info_v2  # noqa: E402
from webui import render_page  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.list_reads = 0
        self.command_calls = []

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List devices",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_call_device_command",
                description="Control a device",
                input_schema={
                    "type": "object",
                    "properties": {
                        "deviceId": {"type": "string"},
                        "command": {"type": "string"},
                        "params": {"type": "array"},
                    },
                },
            ),
            MCPTool(
                name="hub_get_info",
                description="Hub info",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def get_tool(self, name):
        return next((tool for tool in await self.list_tools() if tool.name == name), None)

    async def call_tool(self, name, arguments):
        if name == "hub_list_devices":
            self.list_reads += 1
            state = "on" if self.list_reads == 1 else "off"
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "devices": [
                        {
                            "id": "14",
                            "name": "Generic Zigbee Switch",
                            "label": "Hallway Light 1",
                            "currentStates": {"switch": state},
                        }
                    ]
                },
                is_error=False,
            )
        if name == "hub_call_device_command":
            self.command_calls.append(arguments)
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="Command accepted",
                data={"success": True},
                is_error=False,
            )
        if name == "hub_get_info":
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "name": "Hub C8 Pro",
                    "firmwareVersion": "2.5.1.128",
                    "freeMemoryKB": "936550",
                    "internalTempCelsius": "46.2",
                    "mcpServerVersion": "3.4.0",
                    "mcpDeviceCount": 93,
                    "mcpRuleCount": 0,
                    "platformUpdate": {
                        "available": False,
                        "currentVersion": "2.5.1.128",
                        "availableVersion": "2.5.1.129",
                    },
                    "appUpdate": {
                        "installedVersion": "3.4.0",
                        "latestVersion": "3.5.0",
                        "updateAvailable": True,
                    },
                },
                is_error=False,
            )
        raise AssertionError(name)


def test_control_is_verified_after_command(monkeypatch):
    fake = FakeMCP()

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("fast_fallback_verified.asyncio.sleep", no_sleep)
    answer = asyncio.run(
        FastFallbackRouter(fake).answer("turn off hallway light 1")
    )

    assert answer["success"] is True
    assert answer["confirmed"] is True
    assert answer["initial_state"] == "on"
    assert answer["verified_state"] == "off"
    assert "confirmed off" in answer["message"]
    assert fake.command_calls == [
        {"deviceId": "14", "command": "off", "params": []}
    ]


def test_hub_health_surfaces_platform_and_mcp_updates():
    fake = FakeMCP()
    answer = asyncio.run(FastFallbackRouter(fake).answer("check hub health"))

    assert "Hub platform update available: 2.5.1.129." in answer["message"]
    assert "MCP Rule Server update available: 3.5.0." in answer["message"]
    metrics = {item["label"]: item["value"] for item in answer["display"]["metrics"]}
    assert metrics["Hub update"] == "Available 2.5.1.129"
    assert metrics["MCP app update"] == "Available 3.5.0"


def test_available_version_overrides_stale_false_platform_flag():
    message, display = present_hub_info_v2(
        {
            "name": "Hub C8 Pro",
            "firmwareVersion": "2.5.1.128",
            "platformUpdate": {
                "available": False,
                "currentVersion": "2.5.1.128",
                "availableVersion": "2.5.1.129",
            },
        }
    )
    assert "Hub platform update available: 2.5.1.129." in message
    assert display["platform_update"]["available"] is True


def test_inference_failure_is_distinct_from_server_health():
    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        inference_failure_ttl_seconds=60,
    )
    agent._health_cache = (
        1_000_000_000.0,
        {"online": True, "model": "qwen3.5:9b"},
    )
    status = agent.record_inference_failure(
        "request exceeded 40 seconds",
        state="timeout",
        elapsed_ms=40000,
    )

    assert status["ready"] is False
    assert status["state"] == "timeout"
    assert agent.recent_inference_failure()["state"] == "timeout"
    assert "server is online" in agent.fallback_reason().lower()
    assert "did not respond" in agent.fallback_reason().lower()


def test_ui_distinguishes_server_online_from_inference_timeout():
    page = render_page("Hubitat MCP AI", "0.1.7-alpha")
    assert "Ollama server online · inference" in page
    assert "Ollama diagnostics" in page
    assert "ollama_inference" in page
