from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing import is_fast_path_query  # noqa: E402
from webui import render_page  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_read_rooms",
                description="Room gateway",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_get_info",
                description="Hub information",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_read_rooms":
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "rooms": [
                        {"id": 1, "name": "Living Room", "deviceCount": 12},
                        {"id": 2, "name": "Kitchen", "deviceCount": 8},
                    ]
                },
                is_error=False,
            )
        if name == "hub_get_info":
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "hubName": "C8 Pro",
                    "firmwareVersion": "2.5.1.128",
                    "localIP": "192.168.1.239",
                    "freeMemoryKB": "948304",
                    "internalTempCelsius": "46.7",
                    "uptime": "16h 30m",
                    "mcpServerVersion": "3.4.0",
                    "mcpDeviceCount": 93,
                    "mcpRuleCount": 18,
                    "safeMode": False,
                    "platformUpdate": {
                        "available": False,
                        "currentVersion": "2.5.1.128",
                    },
                },
                is_error=False,
            )
        raise AssertionError(f"Unexpected tool: {name}")


def test_room_gateway_executes_inner_tool_and_formats_rooms():
    fake = FakeMCP()
    answer = asyncio.run(FastFallbackRouter(fake).answer("List my Hubitat rooms"))

    assert fake.calls == [
        (
            "hub_read_rooms",
            {"tool": "hub_list_rooms", "args": {}},
        )
    ]
    assert answer["success"] is True
    assert answer["display"]["kind"] == "rooms"
    assert answer["display"]["subtitle"] == "2 rooms · 20 assigned devices"
    assert [item["title"] for item in answer["display"]["items"]] == [
        "Kitchen",
        "Living Room",
    ]
    assert "gateway" not in answer["message"]
    assert "inputSchema" not in answer["message"]


def test_hub_health_is_human_readable_and_structured():
    fake = FakeMCP()
    answer = asyncio.run(FastFallbackRouter(fake).answer("Check the hub health status"))

    assert answer["display"]["kind"] == "hub-health"
    assert answer["display"]["title"] == "C8 Pro"
    assert "firmware 2.5.1.128" in answer["message"]
    assert "free memory 926.1" in answer["message"]
    assert not answer["message"].lstrip().startswith("{")
    metrics = {
        item["label"]: item["value"]
        for item in answer["display"]["metrics"]
    }
    assert metrics["Free memory"] == "926.1 MB"
    assert metrics["Temperature"] == "46.7°C"
    assert {"Firmware", "Free memory", "Temperature", "MCP devices"} <= set(metrics)


def test_rules_and_attention_are_fast_paths():
    assert is_fast_path_query("List active automation rules") is True
    assert is_fast_path_query("Find devices that need attention") is True


def test_web_ui_matches_homebrain_mobile_layout_and_keeps_rich_results():
    page = render_page("Hubitat MCP AI", "0.1.3-alpha")
    assert 'class="wrap"' in page
    assert 'class="card view-card"' in page
    assert 'id="summaryCard"' in page
    assert 'id="shortcutsCard"' in page
    assert 'id="outputCard"' in page
    assert 'id="micFab"' in page
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in page
    assert "Smart shortcuts for everyday use" in page
    assert "Technical details" in page
    assert "Read answers" in page
    assert "overflow-wrap:anywhere" in page
