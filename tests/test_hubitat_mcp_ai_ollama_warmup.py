from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from ollama_agent_claude import ClaudeStyleOllamaAgent  # noqa: E402
from webui import render_page  # noqa: E402


class FakeMCP:
    async def list_tools(self):
        return [
            MCPTool(
                name="hub_search_tools",
                description="Search the Hubitat MCP catalog",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            ),
            MCPTool(
                name="hub_get_info",
                description="Get hub health, memory, firmware and platform information",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name, arguments):
        assert name == "hub_get_info"
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"name": "Hub C8 Pro", "freeMemoryKB": 941568},
            is_error=False,
        )


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeHTTP:
    def __init__(self):
        self.posts = []

    async def post(self, url, json, timeout):
        self.posts.append((json["model"], bool(json.get("tools")), timeout))
        index = len(self.posts)
        if index == 1:
            return FakeResponse(
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "hub_get_info",
                                    "arguments": {},
                                }
                            }
                        ],
                    }
                }
            )
        return FakeResponse(
            {"message": {"content": "Your Hub C8 Pro has 919.5 MB of free memory."}}
        )

    async def get(self, url, timeout):
        return FakeResponse(
            {
                "models": [
                    {"name": "qwen3.5:9b"},
                    {"name": "qwen3:4b"},
                ]
            }
        )


def make_agent():
    agent = ClaudeStyleOllamaAgent(
        client=FakeMCP(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        planner_model="",
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
            "models": ["qwen3.5:9b", "qwen3:4b"],
        },
    )
    agent._http = FakeHTTP()
    return agent


def test_real_question_is_not_blocked_by_old_probe_failure():
    agent = make_agent()
    agent._inference_cache = (
        time.time(),
        {
            "ready": False,
            "state": "timeout",
            "model": "qwen3.5:9b",
            "message": "Model inference timed out.",
        },
    )

    answer = asyncio.run(agent.answer("How much free memory does my hub have?"))

    assert answer["success"] is True
    assert answer["route"] == "ollama+mcp"
    assert answer["planner_model"] == "qwen3:4b"
    assert answer["message"] == "Your Hub C8 Pro has 919.5 MB of free memory."
    assert [item[0] for item in agent._http.posts] == [
        "qwen3:4b",
        "qwen3.5:9b",
    ]
    assert agent._http.posts[0][1] is True
    assert agent._http.posts[-1][1] is False


def test_ui_reports_available_or_loaded_instead_of_synthetic_timeout():
    page = render_page("Hubitat MCP AI", "0.2.1-alpha")
    assert "loads on first question" in page
    assert "runtime.model_loaded" in page
    assert "inference timed out" not in page
