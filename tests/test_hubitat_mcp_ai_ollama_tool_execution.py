from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from ollama_agent_claude import ClaudeStyleOllamaAgent  # noqa: E402


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_search_tools",
                description="Search the Hubitat MCP tool catalog",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            ),
            MCPTool(
                name="hub_list_devices",
                description="List Hubitat devices and their current states",
                input_schema={"type": "object", "properties": {"filter": {"type": "string"}}},
            ),
            MCPTool(
                name="hub_get_info",
                description="Read Hubitat hub information",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_read_diagnostics",
                description="Read device health and other diagnostics",
                input_schema={"type": "object", "properties": {"tool": {"type": "string"}, "args": {"type": "object"}}},
            ),
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            data = {
                "tools": [
                    {
                        "name": "hub_list_devices",
                        "description": "List live devices and states",
                    }
                ]
            }
        elif name == "hub_list_devices":
            data = {
                "devices": [
                    {
                        "id": "1",
                        "label": "Livingroom TRV",
                        "currentStates": {"battery": 12},
                    },
                    {
                        "id": "2",
                        "label": "Fridge Door",
                        "currentStates": {"battery": 17},
                    },
                ]
            }
        else:
            data = {"name": "Hub C8 Pro"}
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def make_agent(http):
    agent = ClaudeStyleOllamaAgent(
        client=FakeMCP(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        planner_model="qwen3.5:9b",
        planner_timeout_seconds=45,
        response_timeout_seconds=90,
        max_tool_rounds=3,
    )
    agent._health_cache = (
        time.time(),
        {
            "online": True,
            "model": "qwen3.5:9b",
            "model_present": True,
            "models": ["qwen3.5:9b"],
        },
    )
    agent._http = http
    return agent


def test_json_printed_by_qwen_is_executed_as_a_tool_call():
    class HTTP:
        def __init__(self):
            self.posts = 0

        async def post(self, url, json, timeout):
            self.posts += 1
            if self.posts == 1:
                return FakeResponse(
                    {
                        "message": {
                            "content": (
                                '{"name":"hub_list_devices","parameters":'
                                '{"tool":"hub_list_devices","args":{"filter":"battery"}}}'
                            )
                        }
                    }
                )
            return FakeResponse(
                {
                    "message": {
                        "content": (
                            "Two devices need attention: Livingroom TRV at 12% and "
                            "Fridge Door at 17%."
                        )
                    }
                }
            )

    agent = make_agent(HTTP())
    answer = asyncio.run(agent.answer("Find devices that need attention"))

    assert answer["route"] == "ollama+mcp"
    assert answer["message"].startswith("Two devices need attention")
    assert agent.client.calls == [
        ("hub_list_devices", {"filter": "battery"})
    ]
    assert answer["tools_used"][0]["name"] == "hub_list_devices"


def test_missing_native_tool_call_triggers_generic_mcp_discovery():
    class HTTP:
        def __init__(self):
            self.posts = 0

        async def post(self, url, json, timeout):
            self.posts += 1
            if self.posts == 1:
                return FakeResponse(
                    {
                        "message": {
                            "content": "I do not have enough information about the home yet."
                        }
                    }
                )
            if self.posts == 2:
                return FakeResponse(
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "hub_list_devices",
                                        "arguments": {},
                                    }
                                }
                            ],
                        }
                    }
                )
            return FakeResponse(
                {
                    "message": {
                        "content": (
                            "The live snapshot shows two low-battery devices: "
                            "Livingroom TRV at 12% and Fridge Door at 17%."
                        )
                    }
                }
            )

    agent = make_agent(HTTP())
    answer = asyncio.run(agent.answer("What's happening at home?"))

    assert answer["route"] == "ollama+mcp"
    assert "live snapshot" in answer["message"]
    assert agent.client.calls[0] == (
        "hub_search_tools",
        {"query": "What's happening at home?"},
    )
    assert agent.client.calls[1] == ("hub_list_devices", {})
    assert "not enough information" not in answer["message"].lower()


def test_tool_json_detection_does_not_treat_normal_text_as_a_call():
    assert ClaudeStyleOllamaAgent._looks_like_tool_json(
        '{"name":"hub_get_info","arguments":{}}'
    ) is True
    assert ClaudeStyleOllamaAgent._looks_like_tool_json(
        "Your hub is online and healthy."
    ) is False
