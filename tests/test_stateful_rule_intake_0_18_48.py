"""0.18.49: stateful usage authoring uses live capability guides, never a blanket refusal."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from rule_authoring_service import RuleAuthoringService  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402


ACTUAL_REQUEST = (
    "Create a NEW, independent Hubitat automation named "
    "'Google TV — 60-minute cumulative allowance'. Monitor TV device 4221 "
    "and accumulate its ON duration across multiple sessions. Pause counting "
    "when TV switches OFF without resetting. When accumulated ON time reaches "
    "3600 seconds, block Internet access for device 6923. When Internet access "
    "for device 6923 is manually restored, reset the accumulated counter to "
    "zero and begin a fresh 3600-second allowance, immediately if TV 4221 is "
    "already ON. Preserve the counter and timing state across Hubitat restarts. "
    "Do not change, disable, replace or reuse existing rule 3985. First inspect "
    "the available Rule Machine capabilities and confirm the proposed automation "
    "can implement these requirements correctly. Present the configuration for "
    "approval before creating or enabling it."
)


@pytest.mark.parametrize("prompt", [
    ACTUAL_REQUEST,
    "Create a rule to block TV after a total of 1 hour of ON time. "
    "Restart the timer once it is unblocked.",
    "Set up an automation to accumulate usage across sessions, "
    "then reset when internet access is restored.",
])
def test_stateful_rule_authoring_detected_without_device_specific_nouns(prompt):
    assert RuleAuthoringService.is_stateful_authoring_request(prompt) is True


@pytest.mark.parametrize("prompt", [
    "Block Google TV internet now.",
    "Create a Rule Machine rule: turn off bedroom light at 10pm every day.",
    "Schedule the tablet to be unblocked at 7am every day.",
    "How would a cumulative timer reset after unblocking?",
    "Inspect rule 3985 and report whether it resets its timer.",
    "Why did Google TV unblock itself?",
    "Do not create any rules; explain accumulated TV use.",
    "Investigate total of 1 hour of usage and reset on unblocking.",
])
def test_compound_gate_does_not_swallow_reads_or_supported_schedules(prompt):
    assert RuleAuthoringService.is_stateful_authoring_request(prompt) is False


@pytest.mark.asyncio
async def test_no_authoring_gateway_fails_closed_without_hub_writes():
    class RestrictedMCP:
        calls = 0

        async def list_tools(self):
            return []

        def __getattr__(self, name):
            raise AssertionError("No permitted MCP capability: " + name)

    mcp = RestrictedMCP()
    agent = UnifiedMCPAgent(mcp, "unused")
    outcome = await agent.process_user_request_result(ACTUAL_REQUEST)
    assert outcome.request_class == "write"
    assert not outcome.confirmation_required
    assert not outcome.evidence
    assert outcome.message.startswith("No automation was created or queued.")
    assert "hub_manage_rule_machine" in outcome.message
    assert mcp.calls == 0


@pytest.mark.parametrize("prompt", [
    "create a rule to block google tv internet after TV has been on for a total "
    "of 1hr. Once, unblocked resume timer for 1hour then block Google TV",
])
def test_real_claude_wording_reaches_capability_path(prompt):
    assert RuleAuthoringService.is_stateful_authoring_request(prompt)
