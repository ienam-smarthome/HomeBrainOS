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
        return [MCPTool("hub_restart", "Restart hub", {"type": "object"})]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return MCPToolResult(name, arguments, {}, "restarting", {"ok": True})


class FakeModels:
    def __init__(self):
        self.count = 0

    async def generate_content(self, **_kwargs):
        self.count += 1
        if self.count == 1:
            content = types.Content(role="model", parts=[
                types.Part(function_call=types.FunctionCall(name="hub_restart", args={}))
            ])
        else:
            content = types.Content(role="model", parts=[
                types.Part.from_text(text="The hub restart was confirmed.")
            ])
        return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


class FakeAI:
    _homebrain_test_client = True

    def __init__(self):
        self.aio = SimpleNamespace(models=FakeModels(), aclose=self._close)

    async def _close(self):
        return None


@pytest.mark.asyncio
async def test_sensitive_tool_is_not_called_until_same_session_confirms():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI())

    prompt = await agent.process_user_request("Restart the hub", session_id="browser-a")
    assert "Please confirm" in prompt
    assert mcp.calls == []

    answer = await agent.process_user_request("confirm", session_id="browser-a")
    assert answer == "The hub restart was confirmed."
    assert mcp.calls == [("hub_restart", {})]


@pytest.mark.asyncio
async def test_confirmation_cannot_cross_sessions():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI())
    await agent.process_user_request("Restart the hub", session_id="browser-a")
    await agent.process_user_request("confirm", session_id="browser-b")
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_sensitive_action_requires_unique_session_id():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI())
    answer = await agent.process_user_request("Restart the hub")
    assert "unique session_id is required" in answer
    assert mcp.calls == []


def test_read_only_manage_devices_gateway_does_not_require_confirmation():
    tool = MCPTool(
        "hub_manage_devices",
        "Device gateway",
        {"type": "object"},
        annotations={"destructiveHint": True},
    )
    assert not UnifiedMCPAgent._is_sensitive(tool, {"operation": "list_devices"})
    assert UnifiedMCPAgent._is_sensitive(
        tool, {"operation": "set_switch", "arguments": {"state": "on"}}
    )
