from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402
from tool_registry import (  # noqa: E402
    ToolEffect,
    classify_tool_effect,
    control_devices_tool,
    home_snapshot_tool,
)


def gateway(name: str, **annotations: object) -> MCPTool:
    return MCPTool(name, name, {"type": "object"}, annotations=annotations)


class GatewayMCP:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self):
        return [gateway("hub_manage_devices", destructiveHint=True)]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"success": True, "devices": []},
        )


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            gateway("hub_read_devices"),
            {"tool": "hub_get_device_events", "args": {"command": "off"}},
            ToolEffect.READ,
        ),
        (
            gateway("hub_manage_devices", destructiveHint=True),
            {"tool": "hub_list_devices", "args": {}},
            ToolEffect.READ,
        ),
        (
            gateway("hub_manage_devices", destructiveHint=True),
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "off"},
            },
            ToolEffect.ROUTINE_WRITE,
        ),
        (
            gateway("hub_manage_devices", destructiveHint=True),
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "lock"},
            },
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_manage_future", readOnlyHint=True),
            {"tool": "hub_do_something_new", "args": {}},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_manage_destructive_ops"),
            {"tool": "hub_remove_device", "args": {"deviceId": "42"}},
            ToolEffect.DESTRUCTIVE_WRITE,
        ),
        (
            gateway("hub_manage_native_rules_and_apps"),
            {"tool": "hub_set_rule_paused", "args": {"paused": True}},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("hub_update_firmware", readOnlyHint=True),
            {"confirm": True},
            ToolEffect.SENSITIVE_WRITE,
        ),
        (
            gateway("future_unknown_tool"),
            {},
            ToolEffect.SENSITIVE_WRITE,
        ),
    ],
)
def test_structured_tool_effect_classification(tool, arguments, expected):
    assert classify_tool_effect(tool, arguments) is expected


def test_local_tools_declare_their_effects():
    assert classify_tool_effect(home_snapshot_tool(), {}) is ToolEffect.READ
    assert (
        classify_tool_effect(control_devices_tool(), {"command": "off"})
        is ToolEffect.ROUTINE_WRITE
    )


def test_effect_properties_define_write_and_confirmation_policy():
    assert ToolEffect.READ.mutates is False
    assert ToolEffect.ROUTINE_WRITE.mutates is True
    assert ToolEffect.ROUTINE_WRITE.requires_confirmation is False
    assert ToolEffect.SENSITIVE_WRITE.requires_confirmation is True
    assert ToolEffect.DESTRUCTIVE_WRITE.requires_confirmation is True


def test_effect_registry_is_authoritative_for_manage_read_calls():
    tool = gateway("hub_manage_devices", destructiveHint=True)
    arguments = {"tool": "hub_list_devices", "args": {}}

    assert classify_tool_effect(tool, arguments) is ToolEffect.READ
    assert classify_tool_effect(tool, arguments).mutates is False
    assert classify_tool_effect(tool, arguments).requires_confirmation is False


@pytest.mark.asyncio
async def test_manage_read_executes_without_confirmation_or_write_classification():
    mcp = GatewayMCP()
    arguments = {"tool": "hub_list_devices", "args": {}}
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": arguments}
        }]}},
        {"message": {"role": "assistant", "content": "Inventory checked."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Inspect the device inventory", session_id="read"
    )

    assert outcome.message == "Inventory checked."
    assert outcome.request_class == "live-read"
    assert mcp.calls == [("hub_manage_devices", arguments)]
    assert outcome.evidence[0]["effect"] == ToolEffect.READ.value
    assert outcome.evidence[0]["mutates"] is False


@pytest.mark.asyncio
async def test_routine_manage_write_executes_without_confirmation():
    mcp = GatewayMCP()
    arguments = {
        "tool": "hub_call_device_command",
        "args": {"deviceId": "42", "command": "off"},
    }
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": arguments}
        }]}},
        {"message": {"role": "assistant", "content": "Switch turned off."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Run the routine device command", session_id="routine"
    )

    assert outcome.message == "Switch turned off."
    assert outcome.request_class == "write"
    assert mcp.calls == [("hub_manage_devices", arguments)]
    assert outcome.evidence[0]["effect"] == ToolEffect.ROUTINE_WRITE.value


@pytest.mark.asyncio
async def test_sensitive_manage_write_still_waits_for_confirmation():
    mcp = GatewayMCP()
    arguments = {
        "tool": "hub_call_device_command",
        "args": {"deviceId": "42", "command": "unlock"},
    }
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_manage_devices", "arguments": arguments}
        }]}},
        {"message": {"role": "assistant", "content": "Lock opened."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    prompt = await agent.process_user_request(
        "Run the sensitive device command", session_id="sensitive"
    )

    assert "Please confirm" in prompt
    assert not mcp.calls

    answer = await agent.process_user_request("confirm", session_id="sensitive")

    assert answer == "Lock opened."
    assert mcp.calls == [("hub_manage_devices", arguments)]


def test_evidence_receipt_records_structured_effect():
    agent = UnifiedMCPAgent(object(), "key", ai_client=object())
    token = agent._evidence.set([])
    try:
        agent._record_evidence(
            "hub_manage_devices",
            {
                "tool": "hub_call_device_command",
                "args": {"deviceId": "42", "command": "on"},
            },
            success=True,
            elapsed_ms=3,
            summary="command sent",
        )
        receipt = (agent._evidence.get() or [])[0]
    finally:
        agent._evidence.reset(token)

    assert receipt["effect"] == ToolEffect.ROUTINE_WRITE.value
    assert receipt["mutates"] is True
