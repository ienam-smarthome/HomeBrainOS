"""v0.18.48 regression: compound usage budgets must fail transparently, not silently."""
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
    answer = RuleAuthoringService.unsupported_stateful_authoring_message(prompt)
    assert answer is not None
    assert "No automation was created or queued" in answer
    assert "persistent cumulative-usage controller" in answer
    assert "existing rules and device states remain unchanged" in answer


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
    assert RuleAuthoringService.unsupported_stateful_authoring_message(prompt) is None


@pytest.mark.asyncio
async def test_unsupported_rule_does_no_hubitat_io_and_reports_capability_boundary():
    class NoCallsMCP:
        def __getattr__(self, name):
            raise AssertionError("No Hubitat tool should be touched: " + name)

    agent = UnifiedMCPAgent(NoCallsMCP(), "unused")
    result = await agent.process_user_request_result(ACTUAL_REQUEST)
    assert result.request_class == "write"
    assert not result.confirmation_required
    assert result.confirmation_count == 0
    assert result.evidence == []
    assert "No automation was created or queued" in result.message
    assert "Rule Machine" in result.message
    assert "UNVERIFIED_MUTATION_REFUSAL" not in result.message
    assert "action actually ran" not in result.message
    assert "existing rules and device states remain unchanged" in result.message
