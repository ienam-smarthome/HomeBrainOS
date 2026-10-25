"""Universal AI investigation goal fidelity and verified-source scope tests.

All cases use simulated model replies and read-only evidence. No Hubitat calls.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from ai_investigation_routing import (
    ReadRouteDecision, decide_read_route,
    set_request_interpretation, reset_request_interpretation,
)
from investigation_intelligence import plan_investigation
from investigation_objective import resolve_primary_objective
from evidence_source_scope import (
    source_app_scope_error, verified_investigation_app_ids,
)

QUESTION = (
    "Why does the bedroom controller sometimes keep the fan ON after the "
    "room has been empty? Inspect its installed app, its actual inputs, "
    "command history and relevant logs. Read only."
)


def model_reply(*, objective: str, goal: str):
    async def model(_messages, tools):
        assert tools == []
        return {"content": json.dumps({
            "route": "model_led", "objective": objective,
            "answer_goal": goal, "target": "the bedroom controller",
            "purpose": "determine the most supported reason for the symptom",
        })}
    return model


def test_diagnosis_over_existing_app_remains_explanation_not_certification():
    decision = asyncio.run(decide_read_route(model_reply(
        objective="existing_rule_verification", goal="diagnose_cause",
    ), QUESTION))
    assert decision.answer_goal == "diagnose_cause"
    assert decision.objective == "general_investigation"
    token = set_request_interpretation(QUESTION, decision)
    try:
        assert resolve_primary_objective(QUESTION).domain == "general"
        assert plan_investigation(QUESTION) is None
    finally:
        reset_request_interpretation(token)


def test_explicit_rule_verification_still_uses_existing_rule_contract():
    question = "Verify App 5012's exact installed action tree and current settings."
    decision = asyncio.run(decide_read_route(model_reply(
        objective="general_investigation", goal="verify_configuration",
    ), question))
    assert decision.objective == "existing_rule_verification"
    token = set_request_interpretation(question, decision)
    try:
        assert resolve_primary_objective(question).is_rule
        assert plan_investigation(question).domain == "existing_rule_verification"
    finally:
        reset_request_interpretation(token)


def test_legacy_interpretation_without_goal_remains_compatible():
    async def model(_messages, _tools):
        return {"content": '{"route":"model_led","objective":"existing_rule_verification"}'}
    d = asyncio.run(decide_read_route(model, QUESTION))
    assert d.objective == "existing_rule_verification"
    assert d.answer_goal is None


def test_no_model_claim_can_grant_fast_system_report_scope():
    d = asyncio.run(decide_read_route(model_reply(
        objective="existing_rule_verification", goal="diagnose_cause",
    ), QUESTION))
    assert d.route == "model_led"


def typed_app_receipt(app_id="5012", *, payload_app_id=None):
    return {
        "success": True, "mutates": False, "effect": "read",
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "evidence_kind": "typed_existing_rule_partial_settings",
        "arguments": {"tool": "hub_get_app_config",
                      "args": {"appId": app_id, "includeSettings": True}},
        "details": {"appId": payload_app_id or app_id,
                    "settingsReadable": True},
    }


def test_read_source_must_match_host_verified_controller_app():
    receipts = [typed_app_receipt("5012")]
    assert verified_investigation_app_ids(receipts) == frozenset({"5012"})
    assert source_app_scope_error(
        "homebrain_read_groovy_source", {"appId": "5012"}, receipts, QUESTION,
    ) is None
    denied = source_app_scope_error(
        "homebrain_read_groovy_source", {"appId": "5040"}, receipts, QUESTION,
    )
    assert "Source target mismatch" in denied
    assert "5012" in denied and "5040" in denied


def test_explicit_multi_app_comparison_permits_both_named_apps():
    receipts = [typed_app_receipt("5012")]
    request = "Compare the implementation of App 5012 with App 5040; read only."
    assert source_app_scope_error(
        "homebrain_read_groovy_source", {"appId": "5040"}, receipts, request,
    ) is None


def test_unverified_or_unrelated_evidence_cannot_anchor_source_identity():
    row = typed_app_receipt("5012", payload_app_id="5040")
    assert not verified_investigation_app_ids([row])
    assert source_app_scope_error(
        "homebrain_read_groovy_source", {"appId": "5040"}, [row], QUESTION,
    ) is None
    assert source_app_scope_error(
        "hub_read_apps_code", {"tool": "hub_get_app_config",
                               "args": {"appId": "5040"}},
        [typed_app_receipt("5012")], QUESTION,
    ) is None


def test_source_matching_does_not_override_user_write_safety():
    # A source scope check is a READ-only preflight, never a write authority.
    receipts = [typed_app_receipt()]
    assert source_app_scope_error(
        "hub_manage_rule_machine", {"appId": "5012"}, receipts, QUESTION,
    ) is None
    route = ReadRouteDecision(
        "model_led", "model_choice", objective="general_investigation",
        answer_goal="diagnose_cause",
    )
    assert route.answer_goal == "diagnose_cause"
