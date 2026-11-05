"""Native read-only authoring contract review stays separate from installed-rule audits.

A v0.18.424 live runbook review was misclassified as an existing Rule
Machine action-tree audit and fetched 240k unrelated Groovy source bytes.
This test checks the original review objective, not incident-specific IDs.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ai_investigation_routing import (
    ReadRouteDecision, decide_read_route,
    set_request_interpretation, reset_request_interpretation,
)
from investigation_intelligence import plan_investigation, assess_investigation
from investigation_objective import resolve_primary_objective
from targeted_rule_scope_policy import (
    is_native_rule_contract_review_request,
    is_existing_rule_verification_request,
    is_new_rule_design_review_request,
)
from rule_authoring_service import RuleAuthoringService
from rule_design_claim_guard import calibrate_rule_design_review

QUESTION = (
    "Review the MCP Rule Server v5.1.6 native one-time dated-trigger "
    "runbook. READ-ONLY. Verify the native trigger and log-action field "
    "types, date and time formats, year# handling, parent ID, creation "
    "structure, backup requirements and scheduler verification. "
    "Distinguish upstream-tested capabilities, installed-hub evidence and "
    "unverified assumptions. Do not invent native field values, describe "
    "unperformed source reads, or declare the design READY without "
    "independently verified typed evidence. Do not include unrelated "
    "lighting, motion or lockout guidance. Do not create, modify, clone, "
    "execute or delete any rule, open native forms or change devices. "
    "Do not queue a confirmation. Report readiness and include Technical JSON."
)

def guide_receipt():
    return {
        "success": True, "mutates": False, "effect": "read",
        "tool": "hub_get_tool_guide", "sub_tool": None,
        "arguments": {"section": "set_rule_reference"},
        "evidence_kind": "tool_result",
        "summary": "object fields: success, section, content",
    }


def test_native_runbook_request_is_proposal_contract_not_existing_rule():
    assert is_native_rule_contract_review_request(QUESTION)
    assert not is_existing_rule_verification_request(QUESTION)
    assert is_new_rule_design_review_request(QUESTION)
    assert RuleAuthoringService.is_read_only_rule_design_request(QUESTION)
    assert resolve_primary_objective(QUESTION).domain == "general"


def test_advisory_existing_rule_label_cannot_redirect_native_runbook_review():
    token = set_request_interpretation(
        QUESTION,
        ReadRouteDecision("model_led", "model_choice",
                          objective="existing_rule_verification",
                          answer_goal="verify_configuration"),
    )
    try:
        assert not is_existing_rule_verification_request(QUESTION)
        assert is_new_rule_design_review_request(QUESTION)
        assert RuleAuthoringService.is_read_only_rule_design_request(QUESTION)
        assert resolve_primary_objective(QUESTION).domain == "general"
        plan = plan_investigation(QUESTION)
        assert plan is not None
        assert plan.domain == "rule_design_review"
        req = {x.key for x in plan.requirements}
        assert req == {"native_capabilities", "typed_authoring_contract"}
        coverage = assess_investigation(plan, [guide_receipt()])
        assert coverage["evidenceComplete"] is False
        states = {x["key"]: x["state"] for x in coverage["requirements"]}
        assert states["native_capabilities"] == "checked-unverified"
        assert states["typed_authoring_contract"] == "checked-unverified"
    finally:
        reset_request_interpretation(token)


def test_model_arbitrator_corrects_existing_rule_advice_without_new_model_round():
    calls = []
    async def fake_chat(messages, tools):
        calls.append((messages, tools))
        return {
            "content": json.dumps({
                "route": "model_led",
                "objective": "existing_rule_verification",
                "answer_goal": "verify_configuration",
                "target": "Native dated-trigger runbook",
            }),
        }
    decision = asyncio.run(decide_read_route(fake_chat, QUESTION))
    assert decision.route == "model_led"
    assert decision.objective == "rule_design_review"
    assert len(calls) == 1


def test_explicit_existing_saved_rule_remains_existing_rule_verification():
    question = (
        "Read-only: verify existing rule 4259 persisted ordered triggers and "
        "actions, compare its stored action tree against the native rule "
        "authoring guide. Do not modify anything."
    )
    assert not is_native_rule_contract_review_request(question)
    assert is_existing_rule_verification_request(question)


def test_excluding_unrelated_motion_and_lockout_does_not_activate_legacy_warning():
    message = calibrate_rule_design_review(
        "This native dated-trigger runbook contract is not yet verified.",
        [guide_receipt()],
        request=QUESTION,
    )
    assert "Rule design feasibility gate" in message
    assert "23:00" not in message
    assert "06:00" not in message
    assert "manual-off lockout" not in message
    assert "Wait for Event: motion active" not in message


def test_positive_motion_design_still_has_historical_safety_gate():
    question = (
        "Review a new Rule Machine motion rule, read-only: Livingroom "
        "Light 1 off after ten minutes inactive in the 23:00 to 06:00 "
        "window. Do not create it."
    )
    assert not is_native_rule_contract_review_request(question)
    reply = calibrate_rule_design_review("Proposal.", [], request=question)
    assert "Wait for Event: motion active" in reply
    assert "23:00" in reply
