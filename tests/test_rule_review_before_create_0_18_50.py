"""v0.18.50: conditional create must inspect the existing rule without losing reads.

Regression for a live v0.18.49 output: three successful reads of app 4239
were replaced with 'I could not verify that this action actually ran'.
A review-before-create is a separate read-only *stage*, not a failed write.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import (  # noqa: E402
    UnifiedMCPAgent,
    UNVERIFIED_MUTATION_REFUSAL,
    _explicit_mutation_request,
)
from rule_authoring_service import RuleAuthoringService  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402

REQUEST = (
    "Create a Rule Machine automation for 60 minutes of cumulative TV-on time, "
    "resetting when Internet access is blocked and starting a fresh allowance "
    "when restored. First inspect the existing rule "
    "'Internet: Google TV block after 1hr total TV-on time'. "
    "If that rule already provides the required behaviour, do not create "
    "a duplicate. Show the verified triggers, actions, variable handling "
    "and any remaining problems."
)


@pytest.mark.parametrize("prompt", [
    REQUEST,
    "Please create a new cumulative usage automation. First inspect the "
    "existing rule Old TV Timer. If that rule already works, don't create a duplicate.",
    "Create a motion alarm. Review first the existing automation for motion. "
    "Avoid creating a duplicate.",
])
def test_review_before_create_recognised(prompt):
    assert RuleAuthoringService.is_existing_rule_review_first(prompt)


@pytest.mark.parametrize("prompt", [
    "Create a cumulative TV-on rule; block Internet after 60 minutes, then reset on unblock.",
    "Inspect existing rule TV Usage and report if it works.",
    "Create a new rule at 9PM. Then disable the old rule.",
    "Create a rule. First inspect the existing rule, then pause that old rule. "
    "Don't create a duplicate.",
    "Why was my existing rule paused?",
    "Create a scheduled TV rule at 8pm.",
])
def test_unrelated_reads_and_explicit_writes_not_swallowed(prompt):
    assert not RuleAuthoringService.is_existing_rule_review_first(prompt)


def test_conditional_intent_still_recognised_as_original_user_write():
    assert _explicit_mutation_request(REQUEST)
    # Staging reduces authority only for this invocation, not permanently.
    assert RuleAuthoringService.is_existing_rule_review_first(REQUEST)


@pytest.mark.asyncio
async def test_three_read_evidence_survives_review_guard(monkeypatch):
    class NoMCP:
        pass

    agent = UnifiedMCPAgent(NoMCP(), "unused")
    async def replay(self, prompt, conversation_history=None, *, session_id="default"):
        assert self._review_first_mode.get() is True
        assert self._mutation_requested_by_user.get() is False
        for tool, action in (
            ("hub_read_apps_code", "hub_list_apps"),
            ("hub_read_apps_code", "hub_get_app_config"),
            ("hub_read_rules", "hub_list_rule_local_variables"),
        ):
            self.evidence.record(
                tool, {"tool": action, "args": {"appId": 4239}},
                success=True, elapsed_ms=1, summary=action,
                supports_live_claim=True,
            )
        return self._unverified_mutation_guard(
            "Verified app ID 4239 and its local-variable read. The supplied "
            "configuration page did not expose the complete ordered trigger "
            "and action blocks, so cumulative timing cannot yet be verified."
        )

    monkeypatch.setattr(agent.__class__, "_process_user_request", replay)
    outcome = await agent.process_user_request_result(REQUEST)

    assert outcome.request_class == "live-read"
    assert outcome.confirmation_required is False
    assert outcome.confirmation_count == 0
    assert len(outcome.evidence) == 3
    assert all(not row.get("mutates") for row in outcome.evidence)
    assert "Read-only existing-rule review" in outcome.message
    assert "configuration page did not expose" in outcome.message
    assert outcome.message != UNVERIFIED_MUTATION_REFUSAL
    assert "no automation or device was changed" in outcome.message


@pytest.mark.asyncio
async def test_false_write_claim_blocked_during_read_only_review(monkeypatch):
    agent = UnifiedMCPAgent(object(), "unused")
    async def replay(self, prompt, conversation_history=None, *, session_id="default"):
        return self._unverified_mutation_guard(
            "I created the rule successfully and it is already counting."
        )
    monkeypatch.setattr(agent.__class__, "_process_user_request", replay)
    outcome = await agent.process_user_request_result(REQUEST)
    assert "unverified action claim" in outcome.message
    assert "I created" not in outcome.message
    assert not outcome.confirmation_required


class FakeHub:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool("hub_search_tools", "Search", {"type": "object"}),
            MCPTool("hub_get_tool_guide", "Read tool guide", {"type": "object"}),
            MCPTool("hub_read_apps_code", "Read installed app config", {"type": "object"}),
            MCPTool("hub_read_rules", "Read native rules", {"type": "object"}),
            MCPTool("hub_manage_rule_machine", "Modify native rules", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert not name.startswith("hub_manage_"), "No Hubitat writes allowed"
        if name == "hub_search_tools":
            return MCPToolResult(
                name, arguments, {}, "", {"matches": [
                    {"gateway": "hub_manage_rule_machine"}
                ]}
            )
        if name == "hub_read_apps_code":
            return MCPToolResult(
                name, arguments, {}, "App 4239 configuration identity verified",
                {"appId": 4239, "success": True, "page": {"sections": []}},
            )
        return MCPToolResult(name, arguments, {}, "", {"success": True})


class FakeTransport:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, tools):
        self.calls.append((messages, tools))
        assert all(
            t["function"]["name"] != "hub_manage_rule_machine" for t in (tools or [])
        ), "Rule write gateway must remain invisible"
        if len(self.calls) == 1:
            return {"content": "", "tool_calls": [{
                "function": {"name": "hub_read_apps_code",
                             "arguments": {"tool": "hub_get_app_config",
                                           "args": {"appId": 4239}}}
            }]}
        return {"content": (
            "App 4239 exists, but I cannot verify its ordered IF/ELSE "
            "actions or reset logic from this configuration identity page."
        )}


@pytest.mark.asyncio
async def test_live_route_never_exposes_write_tools_and_retains_read_findings(monkeypatch):
    hub = FakeHub()
    agent = UnifiedMCPAgent(hub, "unused")
    fake_transport = FakeTransport()
    agent.transport = fake_transport

    async def short_prompt(*args, **kwargs):
        return "Investigate precisely; do not change Hubitat."
    monkeypatch.setattr(agent, "_system_prompt", short_prompt)
    outcome = await agent.process_user_request_result(REQUEST)

    assert outcome.request_class == "live-read"
    assert not outcome.confirmation_required
    assert any(name == "hub_read_apps_code" for name, _ in hub.calls)
    assert all(not name.startswith("hub_manage_") for name, _ in hub.calls)
    assert "App 4239 exists" in outcome.message, (outcome.message, len(fake_transport.calls), [(len(tools or []), messages[-1].get("role")) for messages, tools in fake_transport.calls], hub.calls)
    assert "cannot verify" in outcome.message
    assert outcome.message != UNVERIFIED_MUTATION_REFUSAL
