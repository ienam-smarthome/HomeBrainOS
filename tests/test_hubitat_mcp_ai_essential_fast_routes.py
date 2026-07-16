from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_essentials import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


class FakeMCP:
    timeout_seconds = 2

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List devices",
                input_schema={"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name, arguments):
        assert name == "hub_list_devices"
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=[
                {
                    "id": "1",
                    "label": "Bedroom 1 FP300",
                    "room": "Bedroom 1",
                    "currentStates": {"motion": "active", "battery": 90},
                },
                {
                    "id": "2",
                    "label": "Hallway Motion",
                    "room": "Hallway",
                    "currentStates": {"motion": "inactive", "battery": 80},
                },
                {
                    "id": "3",
                    "label": "Kitchen Linptech",
                    "room": "Kitchen",
                    "currentStates": {"motion": "active", "battery": 75},
                },
            ],
            is_error=False,
        )


def test_spoken_number_device_label_stays_on_verified_fast_control():
    assert classify_query("turn off bedroom one light").route == "mcp-fast"
    assert classify_query("turn on dehumidifier one").route == "mcp-fast"


def test_pronoun_one_still_uses_ai_planner():
    assert classify_query("turn off the one in the bedroom").route == "ollama-planner"
    assert classify_query("turn it off").route == "ollama-planner"


def test_direct_weather_and_motion_reads_are_fast():
    for query in (
        "What is the weather?",
        "what is the weather tomorrow",
        "will it rain today",
        "Which motion sensors are active?",
        "where is motion active",
    ):
        assert classify_query(query).route == "mcp-fast", query


def test_active_motion_sensor_answer_uses_live_current_states():
    answer = asyncio.run(
        FastFallbackRouter(FakeMCP()).answer("Which motion sensors are active?")
    )

    assert answer["success"] is True
    assert answer["intent"] == "fallback-motion-active"
    assert answer["display"]["kind"] == "motion-active"
    assert answer["display"]["metrics"][0]["value"] == "2"
    assert {item["title"] for item in answer["display"]["items"]} == {
        "Bedroom 1 FP300",
        "Kitchen Linptech",
    }


def test_spoken_number_match_resolves_numeric_label_without_ai():
    match, alternatives = FastFallbackRouter._match_device(
        "bedroom one light",
        [
            {"id": "1", "label": "Bedroom 1 Light"},
            {"id": "2", "label": "Bedroom 2 Light"},
        ],
    )
    assert match is not None
    assert match["label"] == "Bedroom 1 Light"
    assert alternatives == []
