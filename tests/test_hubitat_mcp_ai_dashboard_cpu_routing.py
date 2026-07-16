from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_dashboard import FastFallbackRouter  # noqa: E402
from hub_cpu_probe import parse_cpu_info  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent  # noqa: E402
from routing_policy import classify_query  # noqa: E402
from webui import render_page  # noqa: E402


class FakeMCP:
    timeout_seconds = 2

    async def supported_arguments(self, _name, desired):
        return desired

    async def get_tool(self, _name):
        return None

    async def list_tools(self):
        return []

    async def call_tool(self, name, arguments):
        assert name in {"hub_list_devices", "hub_get_info"}
        if name == "hub_get_info":
            data = {
                "name": "Hub C8 Pro",
                "localIP": "not-an-ip",
                "firmwareVersion": "2.5.1.128",
                "freeMemoryKB": "913817",
                "internalTempCelsius": "49.4",
                "databaseSizeKB": "205",
                "uptimeFormatted": "1d 4h 10m",
            }
        else:
            data = [
                {
                    "id": "1",
                    "label": "Bathroom Humidity",
                    "room": "Bathroom",
                    "currentStates": {"humidity": 65, "battery": 90},
                },
                {
                    "id": "2",
                    "label": "Hallway Sensor",
                    "room": "Hallway",
                    "currentStates": {"humidity": 50, "battery": 80},
                },
                {
                    "id": "3",
                    "label": "Hallway Light 1",
                    "room": "Hallway",
                    "type": "Generic Zigbee Dimmer",
                    "currentStates": {"switch": "on", "level": 70},
                },
                {
                    "id": "4",
                    "label": "Bedroom Light",
                    "room": "Bedroom 1",
                    "type": "Light",
                    "currentStates": {"switch": "off"},
                },
            ]
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_cpu_parser_handles_percent_and_load_average():
    percent = parse_cpu_info("CPU Usage 12.5%")
    assert percent["available"] is True
    assert percent["mode"] == "percent"
    assert percent["value"] == "12.5%"

    average = parse_cpu_info("Processors 4\nLoad Average 0.34")
    assert average["available"] is True
    assert average["mode"] == "load-average"
    assert average["processors"] == 4
    assert average["value"] == "0.34"


def test_responsive_queries_use_authoritative_fast_route():
    for query in (
        "list all devices",
        "show all lights",
        "compare humidity in the bathroom and hallway",
        "Show hub CPU and free memory",
    ):
        assert classify_query(query).route == "mcp-fast", query


def test_room_humidity_comparison_is_structured_and_accurate():
    answer = asyncio.run(
        FastFallbackRouter(FakeMCP()).answer(
            "compare humidity in the bathroom and hallway"
        )
    )
    assert answer["success"] is True
    assert answer["intent"] == "fallback-compare-humidity"
    assert "Bathroom averages 65.0%" in answer["message"]
    assert "Hallway averages 50.0%" in answer["message"]
    assert answer["display"]["kind"] == "room-environment-comparison"


def test_all_lights_inventory_does_not_wait_for_ollama():
    answer = asyncio.run(FastFallbackRouter(FakeMCP()).answer("show all lights"))
    assert answer["success"] is True
    assert answer["intent"] == "fallback-light-inventory"
    assert answer["display"]["metrics"][0]["value"] == "2"
    assert {item["title"] for item in answer["display"]["items"]} == {
        "Hallway Light 1",
        "Bedroom Light",
    }


def test_adaptive_agent_does_not_downgrade_qwen35_to_qwen3():
    agent = AdaptiveFinalAnswerAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    installed = ["qwen3:4b", "qwen3.5:9b"]
    assert agent._resolve_planner_model(installed) == "qwen3.5:9b"
    assert agent._resolve_routine_model(installed) == "qwen3.5:9b"

    installed.append("qwen3.5:4b")
    assert agent._resolve_planner_model(installed) == "qwen3.5:4b"


def test_web_dashboard_removes_duplicate_connection_tiles():
    page = render_page("Hubitat MCP AI", "0.2.8-alpha")
    assert "Lights on" in page
    assert "Motion active" in page
    assert "Low batteries" in page
    assert "MCP connection" not in page
    assert "Ollama connection" not in page
    assert "MCP tools</div>" not in page
    assert "/api/dashboard" in page
