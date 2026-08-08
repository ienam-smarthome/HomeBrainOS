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
            MCPTool("hub_manage_devices", "Manage devices", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            query = str(arguments.get("query") or "").casefold()
            if "firmware" in query:
                gateways = ["hub_update_firmware"]
            elif "both" in query:
                gateways = ["hub_restart", "hub_manage_devices"]
            else:
                gateways = ["hub_restart"]
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"matches": [{"gateway": gateway} for gateway in gateways]},
            )
        if name == "hub_manage_devices":
            return MCPToolResult(name, arguments, {}, "", {"ok": True})
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
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
    ]
    answer = await agent.process_user_request("confirm", session_id="a")
    assert answer == "Restart confirmed."
    assert mcp.calls[-1] == ("hub_restart", {})


@pytest.mark.asyncio
async def test_outcome_exposes_only_real_pending_confirmation():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_restart", "arguments": {}}
        }]}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Restart hub", session_id="real")

    assert outcome.confirmation_required is True
    assert outcome.confirmation_count == 1


@pytest.mark.asyncio
async def test_bare_confirm_without_pending_action_never_reaches_model():
    ai = FakeAI([])
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("confirm", session_id="empty")

    assert outcome.confirmation_required is False
    assert "No Hubitat action is pending" in outcome.message
    assert "Nothing was executed" in outcome.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_model_confirmation_words_without_tool_call_are_not_queued():
    # UnifiedMCPAgent defaults to 9 tool-calling rounds (raised from 6 in
    # 0.10.368 -- see CHANGELOG-0.10.368.md), so this needs one canned
    # confirmation-claim response per round to exhaust the budget the same
    # way the previous 6-response version did against the old default.
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "I am ready to queue it. Please confirm."}},
        {"message": {"role": "assistant", "content": "I have queued the action."}},
        {"message": {"role": "assistant", "content": "Please confirm."}},
        {"message": {"role": "assistant", "content": "Ready to queue."}},
        {"message": {"role": "assistant", "content": "Please confirm."}},
        {"message": {"role": "assistant", "content": "I have queued it."}},
        {"message": {"role": "assistant", "content": "Please confirm."}},
        {"message": {"role": "assistant", "content": "Ready to queue."}},
        {"message": {"role": "assistant", "content": "I have queued it."}},
    ])
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Create a rule", session_id="fake")

    assert outcome.confirmation_required is False
    assert "No Hubitat action was queued or executed" in outcome.message
    assert "fake" not in agent.confirmations.pending


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
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
    ]


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
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
    ]


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
        # Never reached: confirmed_firmware_report() now answers the
        # confirm step deterministically and short-circuits before this
        # third canned response would be used. Left in place so this fake
        # would still behave sensibly if that changed.
        {"message": {"role": "assistant", "content": "Firmware update started."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request(
        "Install the available firmware update", session_id="firmware"
    )
    assert "Please confirm" in prompt
    assert "may restart" in prompt
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
    ]

    answer = await agent.process_user_request("confirm", session_id="firmware")
    # confirmed_firmware_report now answers deterministically for this
    # sensitive gateway (same treatment ConfirmedActionCoordinator already
    # gave Rule Machine writes) instead of falling through to the model's
    # third canned response above, which this no longer reaches.
    assert answer.startswith("Firmware update initiated.")
    assert "download, install, and reboot" in answer
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
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
    ]

    answer = await agent.process_user_request("confirm", session_id="group")
    assert answer == "Both actions completed."
    assert mcp.calls[-2:] == [
        ("hub_restart", {"device": "1"}),
        ("hub_restart", {"device": "2"}),
    ]


@pytest.mark.asyncio
async def test_mixed_round_replays_the_routine_action_after_confirmation():
    """Regression test for a real bug: a tool-calling round that bundles a
    routine action (turn off a light) with a sensitive one (restart the hub)
    in the same assistant message used to silently drop the routine action.
    The whole round deferred to confirmation, but resume() only replayed the
    sensitive actions list -- the routine call was never executed, never
    re-queued, and produced no error. The full round must now replay on
    confirm, in original order."""

    mcp = FakeMCP()
    calls = [
        {"function": {
            "name": "hub_manage_devices",
            "arguments": {"operation": "off", "deviceId": "9"},
        }},
        {"function": {"name": "hub_restart", "arguments": {}}},
    ]
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "restart both devices"},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": calls}},
        {"message": {"role": "assistant", "content": "Light off and hub restarted."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request(
        "turn off the light and restart the hub", session_id="mixed"
    )
    # Only the sensitive action is described as needing confirmation --
    # the routine one riding along must not inflate this count or wording.
    assert "Please confirm before I run the sensitive Hubitat action `hub_restart`." == prompt
    assert "hub_manage_devices" not in prompt
    # Nothing executed yet: only discovery calls happened so far (matches
    # the existing single-sensitive-action test's discovery call count).
    assert [name for name, _ in mcp.calls] == ["hub_search_tools", "hub_search_tools"]

    answer = await agent.process_user_request("confirm", session_id="mixed")
    assert answer == "Light off and hub restarted."
    # Both the routine and the sensitive action must have actually run,
    # in their original order, once confirmed.
    assert mcp.calls[-2:] == [
        ("hub_manage_devices", {"operation": "off", "deviceId": "9"}),
        ("hub_restart", {}),
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
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
        "hub_search_tools",
    ]
