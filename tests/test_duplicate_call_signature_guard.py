from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402


class ControlMCP:
    """Two routine (no-confirmation) device-control gateway calls, no
    homebrain_ deterministic presenter involved -- unlike
    homebrain_control_devices, a raw hub_manage_devices call has no
    registered deterministic_tool_presenter entry, so it never triggers
    that unrelated early-return path, letting a test isolate the
    completed_calls duplicate-signature guard specifically.

    hub_manage_devices is not in the catalog's fixed initial declared set
    (see tool_discovery_catalog.INITIAL_TOOL_ORDER) -- it must be
    discovered via hub_search_tools first, same as production. The
    orchestrator runs that discovery itself, before the first model round,
    using the raw user prompt as the query, so declaring hub_search_tools
    here and matching any query is enough; it costs no extra scripted AI
    response since discovery is a direct MCP call, not a chat round.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("hub_manage_devices", "Manage devices", {"type": "object"}),
        ]

    async def get_cached_devices(self) -> list[dict]:
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(
                name, arguments, {}, "",
                {"matches": [{"gateway": "hub_manage_devices"}]},
            )
        return MCPToolResult(name, arguments, {}, "", {"success": True})


def _off_call(device_id: str) -> dict:
    return {
        "function": {
            "name": "hub_manage_devices",
            "arguments": {
                "tool": "hub_call_device_command",
                "args": {"deviceId": device_id, "command": "off"},
            },
        }
    }


@pytest.mark.asyncio
async def test_a_duplicate_call_earlier_in_a_round_does_not_drop_a_later_new_call():
    """Regression test: the completed_calls duplicate-signature guard used
    to `return await self._final_answer(messages)` the instant it saw a
    repeated call signature, abandoning any remaining calls in that same
    tool-calling round -- including a genuinely new mutating call with no
    tool-role reply and no evidence receipt, while the model's own
    narration could still confidently claim the whole round succeeded.

    Round 1 turns off device "1". Round 2 repeats that exact call
    (identical signature) *and* adds a new call turning off device "2" in
    the same tool-calling round. Device "2"'s command must still reach the
    hub even though it comes after the duplicate in the model's call list.
    """

    mcp = ControlMCP()
    ai = FakeAI([
        # Round 1: turn off device 1.
        {"message": {"role": "assistant", "tool_calls": [_off_call("1")]}},
        # Round 2, same turn: repeats the identical device-1 call (same
        # signature) *and* adds a new device-2 call in the same round.
        {
            "message": {
                "role": "assistant",
                "tool_calls": [_off_call("1"), _off_call("2")],
            }
        },
        # The duplicate signature ends the agentic loop via
        # _final_answer(), which issues one more chat call with no tools.
        {"message": {"role": "assistant", "content": "Done."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    await agent.process_user_request(
        "Turn off device 1, then turn off devices 1 and 2 again",
        session_id="dup-guard-test",
    )

    device_command_calls = [
        arguments for name, arguments in mcp.calls if name == "hub_manage_devices"
    ]
    device_ids_commanded = [
        call["args"]["deviceId"] for call in device_command_calls
    ]
    assert device_ids_commanded.count("1") == 1, (
        "device 1's duplicate call in round 2 must not be re-executed "
        "(would double the real-world side effect)"
    )
    assert "2" in device_ids_commanded, (
        "device 2's new call must still execute even though it follows a "
        "duplicate signature earlier in the same round"
    )
