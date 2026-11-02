"""Native Rule Machine document reads are READS, not sensitive writes.

Source: upstream toolSetRule calls toolGetRuleDocument directly when
operation="read" irrespective of boolean confirm. Only the exact, bounded
native read envelope is admitted; other sub-operations fail closed.
No live Hubitat calls occur in this suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app")
)

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from test_mcp_agent_orchestrator import FakeAI  # noqa: E402
from tool_registry import classify_tool_effect, ToolEffect  # noqa: E402


GATEWAY = "hub_manage_native_rules_and_apps"
READ = {"tool": "hub_set_rule", "args": {
    "operation": "read", "rule_id": 42, "confirm": True,
}}


def gateway(name=GATEWAY):
    return MCPTool(
        name, "Native Rule Machine gateway", {"type": "object"},
        annotations={"destructiveHint": True, "mutates": True},
    )


@pytest.mark.parametrize("gateway_name", [GATEWAY, "hub_manage_rule_machine"])
@pytest.mark.parametrize("confirm", [None, False, True])
def test_explicit_bounded_native_read_is_nonmutating(gateway_name, confirm):
    payload = {"operation": "read", "rule_id": 42}
    if confirm is not None:
        payload["confirm"] = confirm
    effect = classify_tool_effect(
        gateway(gateway_name), {"tool": "hub_set_rule", "args": payload}
    )
    assert effect is ToolEffect.READ
    assert not effect.mutates
    assert not effect.requires_confirmation


@pytest.mark.parametrize("read_args", [
    {},
    {"sections": ["settings"]},
    {"sections": ["settings"], "limit": 50},
    {"sections": ["settings"], "cursor": "", "limit": 25},
    {"sections": ["triggers", "actions"]},
])
def test_bounded_paginated_read_arguments_only(read_args):
    args = {"tool": "hub_set_rule", "args": {
        "operation": "read", "rule_id": 42, "args": read_args,
    }}
    assert classify_tool_effect(gateway(), args) is ToolEffect.READ


@pytest.mark.parametrize("bad_args", [
    {"tool": "hub_set_rule", "args": {"operation": "create", "rule_id": 42}},
    {"tool": "hub_set_rule", "args": {"operation": "update", "rule_id": 42}},
    {"tool": "hub_set_rule", "args": {"operation": "form", "rule_id": 42}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": True}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": "42"}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 0}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42, "confirm": "true"}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "changes": [{"part": "action", "value": {}}]}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "args": {"changes": []}}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "args": {"sections": ["settings", "settings"]}}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "args": {"cursor": ""}}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "args": {"sections": ["settings"], "limit": True}}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "args": {"sections": ["settings"], "limit": 101}}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42,
                                    "args": {"sections": ["bogus"]}}},
    {"tool": "hub_set_rule", "args": {"operation": "read", "rule_id": 42},
     "unexpected": "option"},
    {"tool": "hub_set_rule", "args": {"rule_id": 42}},
    {"tool": "hub_delete_native_app", "args": {"operation": "read", "rule_id": 42}},
])
def test_read_lookalikes_and_all_writes_fail_closed(bad_args):
    assert classify_tool_effect(gateway(), bad_args).mutates


class NativeReadOnlyMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool("hub_search_tools", "Search", {"type": "object"}),
            gateway(),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {
                "matches": [{"gateway": GATEWAY}],
            })
        assert name == GATEWAY and arguments == READ, (
            "No native writes or unverified form reads allowed"
        )
        return MCPToolResult(name, arguments, {}, "", {
            "rule_id": 42, "validation": {"structuralIssues": [], "uiChecked": False},
            "triggers": {"1": "When time is 10:00 PM"},
            "actions": [{"id": "1", "value": {"method": "getOnOffSwitch"}}],
            "settings": [
                {"name": "atTime1", "type": "time", "value": "22:00"},
                {"name": "onOff.1", "type": "bool", "value": "false"},
            ],
        })


@pytest.mark.asyncio
async def test_model_native_read_avoids_confirmation_and_is_classified_as_read():
    mcp = NativeReadOnlyMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_search_tools",
                         "arguments": {"query": "hub_set_rule"}}
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": GATEWAY, "arguments": READ}
        }]}},
        *[{"message": {"role": "assistant", "content": (
            "Rule 42 has a 22:00 time trigger and a reported Switch OFF "
            "setting. The parent ID and one-time date semantics are unknown."
        )}} for _ in range(12)],
    ])
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b", ai_client=ai)
    result = await agent.process_user_request_result(
        "Read-only: inspect the native Rule Machine configuration for rule 42. "
        "Do not open forms, create rules or modify anything.",
        session_id="native-read-no-confirm",
    )
    assert result.request_class == "live-read"
    assert not result.confirmation_required
    assert result.confirmation_count == 0
    assert result.message.startswith("Rule 42 has a 22:00 time trigger")
    assert not agent.confirmations.pending
    assert any(name == GATEWAY for name, _ in mcp.calls)
    receipts = [item for item in result.evidence if item.get("tool") == GATEWAY]
    assert len(receipts) == 1
    assert receipts[0]["mutates"] is False
    assert receipts[0]["effect"] == "read"
    assert all(not item.get("mutates") for item in result.evidence)


@pytest.mark.asyncio
async def test_model_generated_native_create_cannot_gain_write_authority():
    mcp = NativeReadOnlyMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": "hub_search_tools",
                         "arguments": {"query": "hub_set_rule"}}
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {"name": GATEWAY, "arguments": {
                "tool": "hub_set_rule",
                "args": {"operation": "create", "confirm": True,
                         "name": "Unapproved", "parent_id": 1},
            }}
        }]}},
        *[{"message": {"role": "assistant", "content": "No native write occurred."}}
          for _ in range(16)],
    ])
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b", ai_client=ai)
    result = await agent.process_user_request_result(
        "Read-only: inspect rule 42, do not change anything",
        session_id="native-deny",
    )
    assert not result.confirmation_required
    assert not agent.confirmations.pending
    assert not any(name == GATEWAY for name, _ in mcp.calls)
