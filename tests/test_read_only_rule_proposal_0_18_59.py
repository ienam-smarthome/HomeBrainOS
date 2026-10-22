"""v0.18.59: an explicitly proposal-only RM task must never become a write.

Regression comes from a 2026-10-22 live benchmark: HomeBrain used ten
read-only tools but returned UNVERIFIED_MUTATION_REFUSAL and request_class=write,
rather than reviewing the wrong sensor ID and existing lighting control.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from rule_authoring_service import RuleAuthoringService
from mcp_agent_orchestrator import (
    UnifiedMCPAgent, _explicit_mutation_request, UNVERIFIED_MUTATION_REFUSAL,
)


LIVE_PROMPT = """I want to create a new Hubitat Rule Machine automation called
"Livingroom Light 1 – Night Idle OFF 2", but you must review the existing
automations and show me your complete implementation plan before making any
changes.

Devices:
- Livingroom Light 1 — device 7805
- FP300 Livingroom motion sensor — device 7764

Required behaviour:
1. Between 23:00 and 06:00, if Livingroom Light 1 is ON and the FP300 sensor
has remained inactive continuously for 10 minutes, turn the light OFF.
2. If motion becomes active during that countdown, cancel the pending OFF.
3. If the light is switched ON while motion is already inactive, the rule
must still handle that situation.
4. Do not turn the light OFF outside the permitted time window.
5. Never turn the light ON automatically or interfere with the existing
manual-off lockout.

Before creating anything:
- Read the actual devices and verify their capabilities.
- Inspect existing automations controlling Livingroom Light 1, especially
app 4019, and check whether this functionality already exists.
- Identify duplicate or conflicting automation behaviour.
- Explain the exact Rule Machine triggers, required expressions, conditions,
actions and cancellation logic.
- Account for the time window crossing midnight.
- Explain whether your available native Hubitat tools can create this rule.
- Show the proposed implementation using only supported capabilities.

Important: This is a read-only review and proposal. Do not create, modify,
disable or execute any rules or device commands. Do not queue a write for
confirmation yet. I will explicitly authorise creation separately after
reviewing your answer."""


@pytest.mark.parametrize("prompt", [
    LIVE_PROMPT,
    "I want to create a rule for my livingroom. Give me a read-only "
    "implementation plan. Do not create anything yet.",
    "Review the existing lighting rule and propose a new rule; do not "
    "create, change or queue anything until I explicitly approve.",
    "I want a Hubitat automation. Inspect app 4019 and show me a proposal "
    "before making any changes. I will authorise creation separately.",
])
def test_proposal_only_is_read_and_not_a_write(prompt):
    assert RuleAuthoringService.is_read_only_rule_design_request(prompt)
    assert not _explicit_mutation_request(prompt)
    assert not RuleAuthoringService.is_existing_rule_review_first(prompt)


@pytest.mark.parametrize("prompt", [
    "Create a new Rule Machine automation to turn the light off at midnight.",
    "Review the existing rule, and also turn off the livingroom light now.",
    "I want to create a rule. Do not write anything yet. Then disable app 4019 now.",
    "Create a rule now. Show me the proposal before making any changes.",
    "Why did app 4019 turn the light off?",
])
def test_read_only_policy_does_not_launder_independent_writes(prompt):
    assert not RuleAuthoringService.is_read_only_rule_design_request(prompt)


@pytest.mark.asyncio
async def test_model_free_design_review_survives_final_guard_with_source_receipts(monkeypatch):
    agent = UnifiedMCPAgent(object(), "unused")
    real_prompt = LIVE_PROMPT
    async def injected_review(self, prompt, conversation_history=None, *, session_id="default"):
        assert self._review_first_mode.get() is True
        assert self._mutation_requested_by_user.get() is False
        for leaf in ("hub_get_device", "hub_get_app_config", "hub_list_device_dependents"):
            self.evidence.record(
                "hub_read_apps_code" if leaf != "hub_get_device" else "hub_read_devices",
                {"tool": leaf, "args": {"appId": "4019"}},
                success=True, elapsed_ms=1, summary=leaf,
                mutates=False, effect="read", supports_live_claim=True,
            )
        text = (
            "Device 7764 is labelled FP300 Toilet sensor, not Livingroom. "
            "App 4019 already controls Livingroom Light 1 (7805). "
            "A ten-minute night rule may conflict with its existing idle OFF; "
            "current actions must be verified before designing a duplicate."
        )
        return self._unverified_mutation_guard(text)

    monkeypatch.setattr(UnifiedMCPAgent, "_process_user_request", injected_review)
    result = await agent.process_user_request_result(real_prompt)
    assert result.request_class == "live-read"
    assert result.confirmation_required is False
    assert result.confirmation_count == 0
    assert len(result.evidence) == 3
    assert result.message.startswith("**Read-only rule design review")
    assert "Toilet sensor" in result.message
    assert "app 4019" in result.message
    assert result.message != UNVERIFIED_MUTATION_REFUSAL
    assert all(row["mutates"] is False for row in result.evidence)


@pytest.mark.asyncio
async def test_design_review_rejects_unverified_claim_of_created_rule(monkeypatch):
    agent = UnifiedMCPAgent(object(), "unused")
    async def model_claim(self, prompt, conversation_history=None, *, session_id="default"):
        return self._unverified_mutation_guard("I created the new rule successfully.")
    monkeypatch.setattr(UnifiedMCPAgent, "_process_user_request", model_claim)
    outcome = await agent.process_user_request_result(LIVE_PROMPT)
    assert outcome.request_class == "live-read"
    assert outcome.confirmation_count == 0
    assert "unverified action claim" in outcome.message
    assert "I created" not in outcome.message
