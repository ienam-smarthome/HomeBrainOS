"""User-reproduced: delayed Internet block cannot show Success on native server.

All calls below are synthetic. No device or hub write tools are provided;
a native schema mismatch must stop before identity/confirmation work.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from mcp_agent_orchestrator import (
    UnifiedMCPAgent, _explicit_mutation_request,
    _verified_schedule_write_intent,
)
from request_metrics import RequestMetrics
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService

NATIVE_GUIDE = (
    "## Set Rule Reference\n"
    'hub_set_rule(operation:"create",args:{parent_id,name,changes:[...]},confirm:true) '
    "creates a native Rule-5.1 child under Rule Machine. "
    "Typed trigger/action fields must be inspected, cannot assume shortcuts."
)


class NoModel:
    async def post(self, *_args, **_kwargs):
        raise AssertionError("Rule authoring fast path must not spend model rounds")

    async def aclose(self):
        return None


class Server:
    def __init__(self, guide=NATIVE_GUIDE):
        self.guide = guide
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool(RULE_MACHINE_GATEWAY, "Manage RM", {
                "type": "object", "properties": {
                    "tool": {"type": "string"}, "args": {"type": "object"}
                }
            }),
            MCPTool("hub_get_tool_guide", "Read guide", {"type": "object"}),
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == "hub_get_tool_guide", "No write/device/inventory call allowed"
        assert arguments == {"section": "set_rule_reference"}
        if self.guide is None:
            raise RuntimeError("Installed guide unavailable")
        return MCPToolResult(name, arguments, {}, "", {"content": self.guide})


def _rules():
    return RuleAuthoringService(Server(), lambda *_args, **_kwargs: None)


@pytest.mark.parametrize("prompt", [
    "block TV after 15mins",
    "block TV in 15 minutes",
    "please turn off TV in 15 minutes",
    "block internet for TV at 4pm",
])
def test_authorised_future_action_is_a_write_not_live_read(prompt):
    assert _verified_schedule_write_intent(prompt, _rules())
    # The old immediate-control parser may reject a delayed request, which
    # was the cause of the observed incorrect live-read label.
    assert _explicit_mutation_request(prompt) or _verified_schedule_write_intent(prompt, _rules())


@pytest.mark.parametrize("prompt", [
    "why was the TV blocked after 15 minutes?",
    "How could I write a rule to block TV after 15mins?",
    "Write a rule to block TV after 15mins without creating it.",
    "block TV after 15mins. Do not change anything.",
    "please block TV now",
])
def test_non_authoring_prompt_does_not_acquire_schedule_write_authority(prompt):
    assert not _verified_schedule_write_intent(prompt, _rules())


@pytest.mark.asyncio
@pytest.mark.parametrize("guide, expected_counter", [
    (NATIVE_GUIDE, "rule_writer_native_unsupported"),
    (None, "rule_writer_contract_unverified"),
])
async def test_live_user_prompt_receives_write_and_unresolved_not_success(guide, expected_counter):
    mcp = Server(guide)
    agent = UnifiedMCPAgent(
        mcp, "synthetic-test-key", "gemma4:31b",
        ai_client=NoModel(), rule_write_enabled=True,
        require_sensitive_confirmation=True,
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        result = await agent.process_user_request_result(
            "block TV after 15mins", session_id="no-write-native-test"
        )
        assert result.request_class == "write"
        assert not result.confirmation_required
        assert result.confirmation_count == 0
        assert metrics.completed_outcome() == "unresolved"
        assert metrics.snapshot()["counters"][expected_counter] == 1
        assert not any(c["mutates"] for c in result.evidence)
        assert len(mcp.calls) == 1
        assert "No rule write was queued or executed" in result.message if guide else "No write was queued or executed" in result.message
    finally:
        metrics.reset(token)


@pytest.mark.asyncio
async def test_legacy_contract_still_queues_only_after_device_validation_and_confirmation():
    # This test proves the new counters do not incorrectly downgrade the
    # legacy supported API itself. It doesn't exercise a real rule write.
    mcp = Server("set_rule_reference hub_set_rule name addTrigger and addAction legacy shortcuts")
    service = RuleAuthoringService(mcp, lambda *_args, **_kwargs: None)
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        assert await service._rule_writer_contract() == "legacy-shortcut"
        assert metrics.completed_outcome() == "success"
        assert "rule_writer_native_unsupported" not in metrics.snapshot()["counters"]
    finally:
        metrics.reset(token)
