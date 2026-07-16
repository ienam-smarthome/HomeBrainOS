from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from ollama_agent_fast import OllamaMCPAgent  # noqa: E402
from routing import dedupe_current_query, is_fast_path_query  # noqa: E402


def test_common_shortcuts_use_fast_path():
    assert is_fast_path_query("What's happening at home?") is True
    assert is_fast_path_query("Which lights are on?") is True
    assert is_fast_path_query("Which batteries are low?") is True
    assert is_fast_path_query("Check the hub health status") is True
    assert is_fast_path_query("Compare Bedroom 2 and Bedroom 3 humidity") is False


def test_current_user_turn_is_not_sent_twice():
    history = [
        {"role": "assistant", "content": "Ready"},
        {"role": "user", "content": "What's happening at home?"},
    ]
    assert dedupe_current_query(history, "What's happening at home?") == [
        {"role": "assistant", "content": "Ready"},
    ]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHTTP:
    def __init__(self):
        self.posts = []

    async def post(self, url, json, timeout):
        self.posts.append(json)
        if len(self.posts) == 1:
            return FakeResponse(
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "hub_get_info",
                                    "arguments": {},
                                },
                            }
                        ],
                    }
                }
            )
        return FakeResponse(
            {
                "message": {
                    "content": "The hub is online and healthy.",
                    "tool_calls": [],
                }
            }
        )

    async def aclose(self):
        return None


class FakeMCP:
    async def list_tools(self):
        return [
            MCPTool(
                name="hub_get_info",
                description="Get Hubitat hub information",
                input_schema={"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name, arguments):
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text='{"status":"online"}',
            data={"status": "online"},
            is_error=False,
        )


def test_ollama_tool_result_includes_tool_name_and_disables_thinking():
    agent = OllamaMCPAgent(
        client=FakeMCP(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        max_tool_rounds=2,
    )
    fake_http = FakeHTTP()
    agent._http = fake_http
    agent._health_cache = (
        time.time(),
        {"online": True, "model": "qwen3.5:9b"},
    )

    answer = asyncio.run(agent.answer("Check the hub health status"))

    assert answer["success"] is True
    assert answer["message"] == "The hub is online and healthy."
    assert len(fake_http.posts) == 2
    assert fake_http.posts[0]["think"] is False
    tool_messages = [
        item
        for item in fake_http.posts[1]["messages"]
        if item.get("role") == "tool"
    ]
    assert tool_messages == [
        {
            "role": "tool",
            "tool_name": "hub_get_info",
            "content": '{"status":"online"}',
        }
    ]
