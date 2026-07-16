from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from ollama_agent_natural import NaturalHubitatOllamaAgent  # noqa: E402


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []

    async def post(self, url, json, timeout):
        self.posts.append(
            {
                "model": json["model"],
                "has_tools": bool(json.get("tools")),
                "timeout": timeout,
            }
        )
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return FakeResponse(value)

    async def get(self, url, timeout):
        return FakeResponse({"models": []})


class FakeMCP:
    timeout_seconds = 5

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_search_tools",
                description="Search the MCP catalogue",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            ),
            MCPTool(
                name="hub_list_devices",
                description="List Hubitat devices and current states",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_get_info",
                description="Read Hubitat hub information",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name, arguments):
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=[],
            is_error=False,
        )


def fallback_response():
    items = [
        {
            "icon": "🔌",
            "title": f"Always on socket {index}",
            "value": "On",
            "tone": "success",
        }
        for index in range(1, 20)
    ]
    items.extend(
        [
            {
                "icon": "💡",
                "title": "Bedroom 2 Light",
                "value": "On",
                "tone": "success",
            },
            {"icon": "🏃", "title": "Kitchen Motion", "value": "Active"},
            {
                "icon": "🪫",
                "title": "Livingroom TRV",
                "value": "12%",
                "tone": "danger",
            },
            {
                "icon": "🪫",
                "title": "Fridge Door",
                "value": "17%",
                "tone": "warning",
            },
        ]
    )
    return {
        "success": True,
        "intent": "fallback-home-status",
        "message": "Live home status",
        "display": {
            "kind": "home-status",
            "title": "What's happening",
            "subtitle": "Live Hubitat MCP device states",
            "metrics": [
                {"label": "Lights on", "value": "1", "icon": "💡"},
                {"label": "Switches on", "value": "19", "icon": "🔌"},
                {"label": "Motion active", "value": "1", "icon": "🏃"},
                {"label": "Low batteries", "value": "2", "icon": "🪫"},
            ],
            "items": items,
        },
    }


def make_agent(responses, *, item_limit=6):
    async def provider(query):
        return fallback_response()

    agent = NaturalHubitatOllamaAgent(
        client=FakeMCP(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        planner_model="",
        routine_model="",
        planner_timeout_seconds=45,
        response_timeout_seconds=90,
        routine_response_timeout_seconds=55,
        planner_tool_limit=6,
        tool_result_limit_chars=6000,
        max_tool_rounds=3,
        fallback_provider=provider,
        evidence_item_limit=item_limit,
    )
    agent._health_cache = (
        time.time(),
        {
            "online": True,
            "model": "qwen3.5:9b",
            "model_present": True,
            "models": ["qwen3.5:9b", "qwen3:4b"],
        },
    )
    agent._http = FakeHTTP(responses)
    return agent


def test_planner_timeout_recovers_with_compact_mcp_evidence_and_routine_model():
    agent = make_agent(
        [
            TimeoutError("planner took too long"),
            {
                "message": {
                    "content": (
                        "One light is on, motion is active in the kitchen, and two "
                        "batteries need attention."
                    )
                }
            },
        ]
    )

    answer = asyncio.run(agent.answer("What's happening at home?"))

    assert answer["success"] is True
    assert answer["route"] == "ollama+mcp"
    assert answer["evidence_source"] == "mcp-recovery"
    assert answer["planner_model"] == "qwen3:4b"
    assert answer["response_model"] == "qwen3:4b"
    assert "One light is on" in answer["message"]
    assert [call["model"] for call in agent._http.posts] == [
        "qwen3:4b",
        "qwen3:4b",
    ]
    assert agent._http.posts[0]["timeout"] == 25.0
    assert agent._http.posts[1]["has_tools"] is False


def test_direct_tools_are_preferred_over_catalogue_search_for_home_snapshot():
    agent = make_agent([{"message": {"content": "unused"}}])
    selected = agent._select_compact_tools(
        "What's happening at home?",
        asyncio.run(FakeMCP().list_tools()),
    )
    names = [tool.name for tool in selected]
    assert "hub_list_devices" in names
    assert "hub_search_tools" not in names
    assert len(names) <= 4


def test_fallback_display_is_compacted_when_final_synthesis_times_out():
    agent = make_agent(
        [
            TimeoutError("planner timeout"),
            TimeoutError("response timeout"),
        ],
        item_limit=4,
    )

    answer = asyncio.run(agent.answer("What's happening at home?"))

    assert answer["route"] == "fallback-compact"
    assert answer["elapsed_ms"] < 120000
    titles = [item["title"] for item in answer["display"]["items"]]
    assert "Livingroom TRV" in titles
    assert "Fridge Door" in titles
    assert "Bedroom 2 Light" in titles
    assert not any(title.startswith("Always on socket") for title in titles)
    assert "routine items were omitted" in answer["display"]["note"]


def test_device_evidence_counts_other_switches_without_dumping_every_name():
    agent = make_agent([{"message": {"content": "unused"}}])
    rows = [
        {
            "id": index,
            "label": f"Socket {index}",
            "currentStates": {"switch": "on"},
        }
        for index in range(1, 20)
    ]
    rows.extend(
        [
            {
                "id": 100,
                "label": "Bedroom 2 Light",
                "type": "Dimmer Light",
                "currentStates": {"switch": "on"},
            },
            {
                "id": 101,
                "label": "Livingroom TRV",
                "currentStates": {"battery": 12},
            },
        ]
    )

    evidence = agent._device_evidence("What's happening at home?", rows)
    encoded = json.dumps(evidence)

    assert evidence["counts"]["lights_on"] == 1
    assert evidence["counts"]["other_switches_on"] == 19
    assert evidence["other_switches_on_count"] == 19
    assert evidence["lights_on"] == ["Bedroom 2 Light"]
    assert evidence["low_batteries"] == [
        {"name": "Livingroom TRV", "battery": 12.0}
    ]
    assert "Socket 1" not in encoded
