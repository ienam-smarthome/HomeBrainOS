from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402


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


@pytest.mark.asyncio
async def test_sensitive_tool_waits_for_same_session_confirmation():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_restart", "arguments": {}}
        }]}},
        {"message": {"role": "assistant", "content": "Restart confirmed."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    prompt = await agent.process_user_request("Restart hub", session_id="a")
    assert "Please confirm" in prompt
    assert not mcp.calls
    answer = await agent.process_user_request("confirm", session_id="a")
    assert answer == "Restart confirmed."
    assert mcp.calls == [("hub_restart", {})]


def test_read_only_gateway_does_not_require_confirmation():
    tool = MCPTool(
        "hub_manage_devices", "Gateway", {"type": "object"},
        annotations={"destructiveHint": True},
    )
    assert not UnifiedMCPAgent._is_sensitive(tool, {"operation": "list_devices"})
    assert UnifiedMCPAgent._is_sensitive(tool, {"operation": "set_switch"})
