from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [MCPTool("set_switch", "Set switch", {"type": "object"})]

    async def get_cached_devices(self):
        return [{"id": "42", "label": "Couch Lamp", "room": "Lounge"}]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return MCPToolResult(name, arguments, {}, "ok", {"switch": "on"})


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.responses)


class FakeAI:
    _homebrain_test_client = True

    def __init__(self, responses):
        self.aio = SimpleNamespace(models=FakeModels(responses), aclose=self._close)

    async def _close(self):
        return None


def response_with_call(name, args):
    content = types.Content(
        role="model",
        parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))],
    )
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def response_with_text(text):
    content = types.Content(
        role="model",
        parts=[types.Part.from_text(text=text)],
    )
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


@pytest.mark.asyncio
async def test_sdk_native_multi_round_tool_execution():
    mcp = FakeMCP()
    ai = FakeAI([
        response_with_call("set_switch", {"device_id": "42", "state": "on"}),
        response_with_text("The couch lamp is on."),
    ])
    agent = UnifiedMCPAgent(
        mcp, "test-key", "test-model", ai_client=ai,
        require_sensitive_confirmation=False,
    )

    answer = await agent.process_user_request("Turn on the couch lamp")

    assert answer == "The couch lamp is on."
    assert mcp.calls == [("set_switch", {"device_id": "42", "state": "on"})]
    second_contents = ai.aio.models.requests[1]["contents"]
    assert second_contents[-1].role == "user"
    assert second_contents[-1].parts[0].function_response.name == "set_switch"


@pytest.mark.asyncio
async def test_manifest_contains_live_device_identity():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._build_system_instruction()
    assert "'Couch Lamp' | ID: 42 | Room: Lounge" in instruction
