"""General read-only recovery after an unauthorized model tool proposal.

Replays mixed write/read function batches against fake MCP capabilities.
No test contacts Hubitat, Home Assistant or the network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402


class ReadRecoveryMCP:
    def __init__(self, *, has_diagnostics=True):
        self.calls = []
        self.has_diagnostics = has_diagnostics

    async def list_tools(self):
        result = [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("hub_manage_devices", "Manage devices", {"type": "object"}),
            MCPTool(
                "hub_manage_virtual_device", "Create virtual devices",
                {"type": "object"},
            ),
        ]
        if self.has_diagnostics:
            result.append(MCPTool(
                "hub_read_diagnostics", "Read hub metrics",
                {"type": "object"},
            ))
        return result

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {
                "results": [
                    {"tool": "hub_create_device", "gateway": "hub_manage_devices"},
                    *([{"tool": "hub_get_metrics", "gateway": "hub_read_diagnostics"}]
                      if self.has_diagnostics else []),
                ],
            })
        if name == "hub_read_diagnostics":
            return MCPToolResult(name, arguments, {}, "", {
                "current": {"timestamp": "2026-11-04T01:00:00Z"},
                "healthAlerts": [],
            })
        raise AssertionError("A management tool was executed in a read-only test")


def model_call(name, arguments):
    return {"message": {"role": "assistant", "tool_calls": [
        {"function": {"name": name, "arguments": arguments}},
    ]}}


@pytest.mark.asyncio
async def test_unauthorized_write_batch_switches_to_installed_read_tools():
    mcp = ReadRecoveryMCP()
    unauthorized = {"message": {"role": "assistant", "tool_calls": [
        {"function": {"name": "hub_manage_devices", "arguments": {
            "tool": "hub_create_device",
            "args": {"label": "Must never be created", "deviceTypeId": "42"},
        }}},
        {"function": {"name": "hub_read_diagnostics", "arguments": {
            "tool": "hub_get_metrics",
        }}},
    ]}}
    ai = FakeAI([
        unauthorized,
        model_call("hub_read_diagnostics", {"tool": "hub_get_metrics"}),
        {"message": {"role": "assistant", "content":
            "Hub metrics were reported. The other requested checks are unverified."}},
    ] * 3)
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    result = await agent.process_user_request_result(
        "Read-only: check the hub metrics and installed devices. "
        "Do not create or change anything.",
        session_id="read-recovery-a",
    )

    assert result.confirmation_required is False
    assert all(name not in {"hub_manage_devices", "hub_manage_virtual_device"}
               for name, _ in mcp.calls)
    assert len([1 for name, _ in mcp.calls if name == "hub_read_diagnostics"]) == 1
    assert any(row.get("sub_tool") == "hub_get_metrics"
               for row in result.evidence)
    assert len(ai.requests) >= 2
    first_tools = {
        t["function"]["name"] for t in ai.requests[0][1]["json"]["tools"]
    }
    second_tools = {
        t["function"]["name"] for t in ai.requests[1][1]["json"]["tools"]
    }
    # v0.18.391: no unsupported first-round model write proposal should
    # be invited by the schema. The fake model deliberately ignores the
    # declared tool list to verify the independent atomic execution guard.
    assert "hub_manage_devices" not in first_tools
    assert "hub_manage_virtual_device" not in first_tools
    assert "hub_read_diagnostics" in first_tools
    assert "hub_manage_devices" not in second_tools
    assert "hub_manage_virtual_device" not in second_tools
    assert "hub_read_diagnostics" in second_tools
    recovery_context = str(ai.requests[1][1]["json"]["messages"])
    assert "HOST READ-ONLY RECOVERY" in recovery_context
    assert "No mutation is authorized" in recovery_context


@pytest.mark.asyncio
async def test_recovery_never_invents_a_missing_read_tool():
    mcp = ReadRecoveryMCP(has_diagnostics=False)
    ai = FakeAI([
        model_call("hub_manage_devices", {
            "tool": "hub_create_device", "args": {"deviceTypeId": "99"},
        }),
        {"message": {"role": "assistant", "content":
            "The requested live observation could not be verified."}},
    ] * 4)
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    result = await agent.process_user_request_result(
        "Read-only: verify hub metrics and device state. Do not change anything.",
        session_id="read-recovery-b",
    )

    assert result.confirmation_required is False
    assert not any(name.startswith("hub_manage_") for name, _ in mcp.calls)
    assert not any(name == "hub_read_diagnostics" for name, _ in mcp.calls)
    assert "hub_read_diagnostics" not in {
        t["function"]["name"] for t in ai.requests[1][1]["json"]["tools"]
    }
    assert "HOST READ-ONLY RECOVERY" in str(
        ai.requests[1][1]["json"]["messages"]
    )


@pytest.mark.asyncio
async def test_read_only_first_round_preserves_normal_read_without_write_recovery():
    mcp = ReadRecoveryMCP()
    ai = FakeAI([
        model_call("hub_read_diagnostics", {"tool": "hub_get_metrics"}),
        {"message": {"role": "assistant", "content":
            "A hub metrics read succeeded; no claim about other checks."}},
    ] * 4)
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    result = await agent.process_user_request_result(
        "Read-only: check hub metrics. Do not change anything.",
        session_id="initial-read-only-tools",
    )

    visible = {
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    }
    assert "hub_read_diagnostics" in visible
    assert "hub_search_tools" in visible
    assert "hub_manage_devices" not in visible
    assert "hub_manage_virtual_device" not in visible
    assert any(name == "hub_read_diagnostics" for name, _ in mcp.calls)
    assert not any(name.startswith("hub_manage_") for name, _ in mcp.calls)
    assert result.confirmation_required is False
