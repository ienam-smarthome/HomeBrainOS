"""Live regression: 8 Gemma rounds / 3 blocked proposals / false success.

An explicitly authorised native TEST rule must not be created active and
then disabled when the user requires an atomic inert creation. An advisory
model plan also must not veto user write authority before confirmation.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from native_rule_creation_staging import (
    demands_atomic_disabled_rule_creation, render_atomic_staging_stop,
)
from request_outcome_policy import classify_completed_request
from api_response_builder import build_agent_response
from mcp_agent_orchestrator import (
    UnifiedMCPAgent, AgentOutcome, _explicit_mutation_request,
)


TEST_WRITE = """Create a native Hubitat Rule Machine automation named
"Livingroom Light 1 - Night Idle OFF - TEST".
I am authorising the creation of a TEST rule subject to confirmation.
Use Livingroom Light 1 7805 and FP400 7978. Only during 23:00-06:00
turn OFF after 10 uninterrupted minutes of inactivity, cancel for active
motion, recheck all states immediately before OFF. Never turn ON.
Read the native Rule Machine tool guide and check exact name duplicates.
Create the rule DISABLED from the outset. Only proceed if native tool can
guarantee disabled-at-creation. Do not create active and then disable.
Present the exact native write and require my confirmation before executing.
Do not modify app 4019 or issue device commands.
"""


@pytest.mark.parametrize("prompt", [
    TEST_WRITE,
    "Create a Rule Machine automation for light 7805. Create it "
    "disabled from the outset, not active then disabled.",
    "Please build a native Hubitat rule. Do not create the rule active, "
    "because it must be disabled when initially created.",
])
def test_safe_disabled_first_requirement_does_not_depend_on_llm(prompt):
    assert _explicit_mutation_request(prompt)
    assert demands_atomic_disabled_rule_creation(prompt)


@pytest.mark.parametrize("prompt", [
    "Create a native Rule Machine automation using light 7805.",
    "Review a proposed rule and show what it would do. Do not create "
    "anything now; any new rule should start disabled.",
    "Why did my disabled native Rule Machine rule run?",
    "Disable rule 3992",
])
def test_staging_boundary_does_not_capture_other_requests(prompt):
    assert not demands_atomic_disabled_rule_creation(prompt)


@pytest.mark.asyncio
async def test_disabled_first_request_returns_without_model_or_write_calls():
    class NoWriteMCP:
        def __init__(self):
            self.calls = []
        async def list_tools(self, *args, **kwargs):
            self.calls.append("list_tools")
            return []
        async def call_tool(self, *args, **kwargs):
            raise AssertionError("Never call a Hubitat write")
    mcp = NoWriteMCP()
    agent = UnifiedMCPAgent(mcp, "test")
    async def no_model(*args, **kwargs):
        raise AssertionError("Do not consume model rounds for unsupported atomic create")
    agent.transport.chat = no_model
    result = await agent.process_user_request_result(TEST_WRITE)
    assert result.request_class == "write"
    assert result.confirmation_required is False
    assert result.confirmation_count == 0
    assert result.evidence == []
    assert "nothing was created or queued" in result.message
    assert "disabled from" in result.message
    assert "create-then-disable" in result.message
    assert mcp.calls == ["list_tools"]


def test_stage_stop_is_explicit_and_never_claims_native_create_support():
    message = render_atomic_staging_stop()
    assert "No Hubitat rule or device write was sent" in message
    assert "not been verified" in message
    assert "could briefly leave the rule active" in message
    assert "nothing was created or queued" in message


def _outcome(*, confirm=False, writes=False):
    return AgentOutcome(
        message="Rule creation safely stopped — nothing created or queued.",
        request_class="write",
        evidence=[{"tool": "hub_read_devices", "success": True, "mutates": False}]
            + ([{"tool": "hub_manage_rule_machine", "success": True,
                 "mutates": True}] if writes else []),
        choices=[], confirmation_required=confirm,
        confirmation_count=1 if confirm else 0,
    )


@pytest.mark.parametrize("counter", [
    "rule_create_staging_unverified",
    "proposal_write_attempts_blocked",
    "write_unverified_no_confirmation",
])
def test_no_write_receipt_never_gets_a_positive_success_badge(counter):
    metrics = {"outcome": "success", "counters": {counter: 1},
               "timings_ms": {"total": 94110}}
    result = build_agent_response(_outcome(), model="gemma4:31b",
                                  elapsed_ms=94110, version="0.18.63")
    # Supply actual metrics through the observed production contract.
    from observed_agent_outcome import build_observed_agent_outcome
    output = build_agent_response(
        build_observed_agent_outcome(_outcome(), metrics),
        model="gemma4:31b", elapsed_ms=94110, version="0.18.63",
    )
    assert output["success"] is False
    assert output["status_verification"] == "no-write-performed"
    assert output["metrics"]["outcome"] == "unresolved"
    assert output["outcome_presentation"]["value"] == "unresolved"
    assert not output["confirmation_required"]
    assert not output["evidence"][-1]["mutates"]


def test_pending_confirmation_is_not_conflated_with_failed_write():
    from observed_agent_outcome import build_observed_agent_outcome
    metrics = {"outcome": "success",
               "counters": {"proposal_write_attempts_blocked": 1}}
    output = build_agent_response(
        build_observed_agent_outcome(_outcome(confirm=True), metrics),
        model="free", elapsed_ms=1, version="0.18.63",
    )
    assert output["confirmation_required"] is True
    assert output["success"] is True


def test_outcome_classifier_not_positive_for_staging_and_no_write():
    assert classify_completed_request({"rule_create_staging_unverified": 1}) == "unresolved"
    assert classify_completed_request({"proposal_write_attempts_blocked": 3}) == "unresolved"
    assert classify_completed_request({"write_unverified_no_confirmation": 1}) == "unresolved"
    assert classify_completed_request({}) == "success"


def test_general_task_propose_cannot_override_separate_write_confirmation():
    code = (ROOT / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert 'task_plan = replace(task_plan, operation="write")' in code
    assert 'and not self._mutation_requested_by_user.get()' in code
    assert 'if self.confirmation_policy.requires_confirmation(effect)' in code or (
        'and self.confirmation_policy.requires_confirmation(effect)' in code
    )
