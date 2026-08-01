from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402
from tool_registry import classify_tool_effect  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("hub_restart", "Restart hub", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            gateway = (
                "hub_update_firmware"
                if "firmware" in str(arguments.get("query") or "").casefold()
                else "hub_restart"
            )
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"matches": [{"gateway": gateway}]},
            )
        return MCPToolResult(name, arguments, {}, "restarting", {"ok": True})


@pytest.mark.asyncio
async def test_sensitive_tool_waits_for_same_session_confirmation():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "restart hub"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_restart", "arguments": {}}
        }]}},
        {"message": {"role": "assistant", "content": "Restart confirmed."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    prompt = await agent.process_user_request("Restart hub", session_id="a")
    assert "Please confirm" in prompt
    assert [name for name, _ in mcp.calls] == ["hub_search_tools"]
    answer = await agent.process_user_request("confirm", session_id="a")
    assert answer == "Restart confirmed."
    assert mcp.calls[-1] == ("hub_restart", {})


@pytest.mark.asyncio
async def test_confirmation_fails_closed_when_queued_tool_disappears():
    class ChangingMCP(FakeMCP):
        def __init__(self):
            super().__init__()
            self.restart_available = True

        async def list_tools(self):
            tools = [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"})
            ]
            if self.restart_available:
                tools.append(
                    MCPTool("hub_restart", "Restart hub", {"type": "object"})
                )
            return tools

    mcp = ChangingMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "restart hub"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_restart", "arguments": {}}
        }]}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request("Restart hub", session_id="changing")
    assert "Please confirm" in prompt
    mcp.restart_available = False

    answer = await agent.process_user_request("confirm", session_id="changing")

    assert "cancelled" in answer
    assert "hub_restart" in answer
    assert [name for name, _ in mcp.calls] == ["hub_search_tools"]


@pytest.mark.asyncio
async def test_sensitive_tool_rejects_empty_session_id():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "restart hub"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_restart", "arguments": {}}
        }]}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request("Restart hub", session_id="")

    assert "unique session_id is required" in prompt
    assert agent._pending == {}
    assert [name for name, _ in mcp.calls] == ["hub_search_tools"]


@pytest.mark.asyncio
async def test_firmware_update_requires_confirmation_and_runs_once():
    class FirmwareMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                MCPTool(
                    "hub_update_firmware",
                    "Install available hub firmware",
                    {
                        "type": "object",
                        "properties": {"confirm": {"type": "boolean"}},
                    },
                )
            ]

    mcp = FirmwareMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {
                    "query": "firmware update",
                },
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_update_firmware",
                "arguments": {"confirm": True},
            }
        }]}},
        {"message": {"role": "assistant", "content": "Firmware update started."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request(
        "Install the available firmware update", session_id="firmware"
    )
    assert "Please confirm" in prompt
    assert "may restart" in prompt
    assert [name for name, _ in mcp.calls] == ["hub_search_tools"]

    answer = await agent.process_user_request("confirm", session_id="firmware")
    assert answer == "Firmware update started."
    assert mcp.calls[-1] == ("hub_update_firmware", {"confirm": True})


@pytest.mark.asyncio
async def test_multiple_sensitive_device_actions_share_one_confirmation():
    mcp = FakeMCP()
    calls = [
        {"function": {"name": "hub_restart", "arguments": {"device": "1"}}},
        {"function": {"name": "hub_restart", "arguments": {"device": "2"}}},
    ]
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "restart"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": calls}},
        {"message": {"role": "assistant", "content": "Both actions completed."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request("Restart both devices", session_id="group")
    assert "2 sensitive Hubitat actions" in prompt
    assert [name for name, _ in mcp.calls] == ["hub_search_tools"]

    answer = await agent.process_user_request("confirm", session_id="group")
    assert answer == "Both actions completed."
    assert mcp.calls[-2:] == [
        ("hub_restart", {"device": "1"}),
        ("hub_restart", {"device": "2"}),
    ]


def test_read_only_gateway_does_not_require_confirmation():
    tool = MCPTool(
        "hub_manage_devices", "Gateway", {"type": "object"},
        annotations={"destructiveHint": True},
    )
    assert not classify_tool_effect(
        tool, {"operation": "list_devices"}
    ).requires_confirmation
    assert not classify_tool_effect(
        tool,
        {
            "tool": "hub_call_device_command",
            "args": {"deviceId": "1", "command": "off"},
        },
    ).requires_confirmation
    assert not classify_tool_effect(
        tool,
        {
            "tool": "hub_call_device_command",
            "args": {"deviceId": "1", "command": "ping"},
        },
    ).requires_confirmation
    assert classify_tool_effect(
        tool,
        {
            "tool": "hub_call_device_command",
            "args": {"deviceId": "1", "command": "unlock"},
        },
    ).requires_confirmation


@pytest.mark.asyncio
async def test_new_question_cancels_pending_confirmation():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "restart hub"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_restart", "arguments": {}}
        }]}},
        {"message": {"role": "assistant", "content": "The hub is online."}},
        {"message": {"role": "assistant", "content": "Nothing was restarted."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)
    await agent.process_user_request("Restart hub", session_id="replace")
    answer = await agent.process_user_request("What is the hub status?", session_id="replace")
    assert "could not retrieve verified live Hubitat evidence" in answer
    assert "replace" not in agent._pending
    assert [name for name, _ in mcp.calls] == ["hub_search_tools"]
