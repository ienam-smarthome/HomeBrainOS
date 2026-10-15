"""Regression: model 'propose' must not suppress an explicit timed Internet block.

All gateway stubs are read-only: the test only inspects a confirmation plan,
never writes a Hubitat rule or changes any network access device.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from mcp_client import MCPTool, MCPToolResult
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_classification import requests_mutation
from rule_authoring_service import RuleAuthoringService, RULE_MACHINE_GATEWAY


def tab():
    return {
        "id": "6916", "label": "Block Tab-S9-FE", "room": "Internet",
        "commands": ["on", "off", "addTime"], "capabilities": ["Switch"],
    }


class FakeMCP:
    def __init__(self, *, missing_rule_gateway=False):
        self.calls = []
        self.missing_rule_gateway = missing_rule_gateway

    async def list_tools(self):
        tools = [
            MCPTool("hub_read_devices", "Device state", {"type": "object"}),
            MCPTool("hub_read_rules", "Rule status", {"type": "object"}),
        ]
        if not self.missing_rule_gateway:
            tools.append(MCPTool(
                RULE_MACHINE_GATEWAY, "Manage Rule Machine",
                {"type": "object", "properties": {
                    "tool": {"type": "string"}, "args": {"type": "object"},
                }},
            ))
        return tools

    async def get_cached_devices(self):
        return [tab()]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            data = {"timeZone": "Europe/London"}
        elif name == "hub_read_devices":
            data = {"devices": [tab()]}
        elif name == "hub_read_rules":
            data = {"rules": []}
        else:
            raise AssertionError(f"Unexpected write or gateway call: {name}")
        return MCPToolResult(name, arguments, {}, "", data)


class NoModel:
    async def post(self, *args, **kwargs):
        raise AssertionError("A deterministic timed block cannot need an AI proposal")

    async def aclose(self):
        return None


def agent(mcp):
    instance = UnifiedMCPAgent(
        mcp, "test-key", "gemma4:31b",
        ai_client=NoModel(), general_task_engine_enabled=True,
        rule_write_enabled=True, require_sensitive_confirmation=True,
    )
    instance.rule_authoring._now = lambda: datetime(
        2026, 10, 15, 17, 30, 0, tzinfo=timezone.utc,
    )
    return instance


@pytest.mark.parametrize("prompt", [
    "block tab s9 fe in 15 minutes",
    "block internet for Tab S9 FE in 15 minutes",
    "please block internet for tab s9 fe in 15 mins",
    "write a rule to block Tab-S9-FE in 15 minutes",
])
@pytest.mark.asyncio
async def test_scheduled_block_routes_without_model_and_queues_off_rule(prompt):
    mcp = FakeMCP()
    homebrain = agent(mcp)
    outcome = await homebrain.process_user_request_result(prompt, session_id="scheduled-tab")
    assert outcome.confirmation_required is True
    assert outcome.confirmation_count == 1
    assert outcome.request_class == "write"
    assert not any(name == RULE_MACHINE_GATEWAY for name, _ in mcp.calls)
    pending = homebrain.confirmations.pending["scheduled-tab"]
    assert len(pending.actions) == 1
    name, params = pending.actions[0]
    assert name == RULE_MACHINE_GATEWAY
    action = params["args"]["addAction"]
    assert action["deviceIds"] == ["6916"]
    assert action["command"] == "off"
    assert action["capabilityFilter"] == "Switch"
    assert params["args"]["addTrigger"]["atTime"] == "2026-10-15T18:45:00"
    assert outcome.metrics["counters"]["rule_schedule_fastpath"] == 1


@pytest.mark.asyncio
async def test_missing_rule_gateway_returns_specific_failure_without_fake_device_resolution():
    mcp = FakeMCP(missing_rule_gateway=True)
    outcome = await agent(mcp).process_user_request_result(
        "block Tab S9 FE in 15 minutes"
    )
    assert "Rule Machine write gateway is unavailable" in outcome.message
    assert "No rule was queued" in outcome.message
    assert not outcome.confirmation_required
    assert not mcp.calls


@pytest.mark.parametrize("prompt", [
    "How would you write a rule to block Tab S9 FE in 15 minutes?",
    "Explain how to create an automation to block Tab S9 FE in 15 minutes.",
    "Write a rule to block Tab S9 FE in 15 minutes without creating it.",
    "Can you show me how to block Tab S9 FE in 15 minutes?",
])
def test_design_questions_remain_read_only_even_when_schedule_grammar_matches(prompt):
    service = RuleAuthoringService(FakeMCP(), lambda *a, **kw: None)
    assert not service.is_action_request(prompt)


def test_block_action_is_a_real_mutation_request_not_a_read_only_question():
    assert requests_mutation("block tab s9 fe in 15 minutes")
    assert requests_mutation("restrict internet for tab s9 fe in 15 minutes")
    assert not requests_mutation("why was tab s9 fe blocked yesterday?")
