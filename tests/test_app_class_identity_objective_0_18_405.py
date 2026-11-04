"""Read-only app class identity must not become an executable-rule audit.

A live existing Rule Machine *parent type* question was incorrectly labeled
existing_rule_verification. Its partial stored-logic coverage then replaced
the answer with unrelated controller, nested IF and duplicate-rule boilerplate.
These tests protect the general identity-vs-logic boundary, not app ID 169.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ai_investigation_routing import (
    ReadRouteDecision, decide_read_route, reset_request_interpretation,
    set_request_interpretation,
)
from targeted_rule_scope_policy import (
    is_app_class_identity_question, is_existing_rule_verification_request,
)
from investigation_objective import resolve_primary_objective
from investigation_intelligence import plan_investigation, assess_investigation
from existing_rule_claim_guard import calibrate_existing_rule_verification
from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import build_observed_agent_outcome
from shared_investigation_completion import apply_shared_investigation_completion


IDENTITY_REQUEST = (
    "Investigate whether Rule Machine app instance 169 is independently verified "
    "as the native Rule Machine parent. Separate the app's displayed name, "
    "its app-type identity, and any independently verified native class "
    "relationship. Explain what remains unverified and what read-only "
    "evidence would resolve it. Do not create, modify or execute any rule."
)

OTHER_IDENTITY = (
    "Does application 4216 really belong to its built-in type/class? "
    "Check the appTypeId to namespace mapping, not just its displayed name."
)

DEEP_RULE = (
    "Read-only audit of existing Rule Machine app 4246: verify its ordered "
    "actions, triggers, delays, health and executable action tree. "
    "Also identify the parent class. Do not create any rule."
)


@pytest.mark.parametrize("question", [
    IDENTITY_REQUEST,
    OTHER_IDENTITY,
    "Verify the native parent class for app 170 from a typed app catalog.",
    "Does installed app 169's appTypeId establish its native class relationship?",
])
def test_class_identity_does_not_trigger_existing_rule_audit(question):
    assert is_app_class_identity_question(question)
    assert not is_existing_rule_verification_request(question)
    assert resolve_primary_objective(question).domain == "app_class_identity"
    plan = plan_investigation(question)
    assert plan is not None and plan.domain == "app_class_identity"
    assert {r.key for r in plan.requirements} == {
        "instance_identity", "native_class_binding"
    }
    assert "stored_logic" not in {r.key for r in plan.requirements}


def test_deep_existing_rule_action_tree_still_certified_separately():
    assert not is_app_class_identity_question(DEEP_RULE)
    assert is_existing_rule_verification_request(DEEP_RULE)
    assert resolve_primary_objective(DEEP_RULE).domain == "existing_rule_verification"
    assert plan_investigation(DEEP_RULE).domain == "existing_rule_verification"


def test_advisory_model_objective_corrected_for_identity_not_genuine_audit():
    async def bad_classifier(messages, tools):
        return {"content": json.dumps({
            "route": "model_led",
            "objective": "existing_rule_verification",
            "answer_goal": "verify_configuration",
            "target": "Rule Machine app instance 169",
            "purpose": "Verify app type",
        })}
    decision = asyncio.run(decide_read_route(bad_classifier, IDENTITY_REQUEST))
    assert decision.route == "model_led"
    assert decision.objective == "app_class_identity"
    token = set_request_interpretation(IDENTITY_REQUEST, decision)
    try:
        assert resolve_primary_objective(IDENTITY_REQUEST).domain == "app_class_identity"
        assert plan_investigation(IDENTITY_REQUEST).domain == "app_class_identity"
        assert not is_existing_rule_verification_request(IDENTITY_REQUEST)
    finally:
        reset_request_interpretation(token)

    # Same mistaken model reply does not erase a genuinely requested
    # executable-rule audit merely because its text includes a parent class.
    still_rule = asyncio.run(decide_read_route(bad_classifier, DEEP_RULE))
    assert still_rule.objective == "existing_rule_verification"


def test_invalid_specialist_route_falls_back_to_targeted_native_identity():
    async def overbroad_classifier(messages, tools):
        return {"content": json.dumps({
            "route": "system_audit",
            "objective": "system_audit",
            "answer_goal": "verify_configuration",
            "target": "app 169",
        })}
    decision = asyncio.run(decide_read_route(
        overbroad_classifier, IDENTITY_REQUEST,
    ))
    assert decision.route == "model_led"
    assert decision.objective == "app_class_identity"


def test_generic_field_names_do_not_establish_native_class_binding():
    plan = plan_investigation(IDENTITY_REQUEST)
    source = [
        {"tool": "hub_read_apps_code", "sub_tool": "hub_list_apps",
         "success": True, "mutates": False, "effect": "read",
         "evidence_kind": "tool_result",
         "arguments": {"tool": "hub_list_apps", "args": {"scope": "instances"}},
         "summary": "object fields: apps, count, filter, totalOnHub"},
        {"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
         "success": True, "mutates": False, "effect": "read",
         "evidence_kind": "tool_result",
         "arguments": {"tool": "hub_get_app_config", "args": {"appId": "169"}},
         "summary": "object fields: success, app, page, childApps, controls"},
        {"tool": "hub_read_rules", "sub_tool": "hub_get_rule_health",
         "success": True, "mutates": False, "effect": "read",
         "evidence_kind": "tool_result",
         "arguments": {"tool": "hub_get_rule_health", "args": {"appId": "169"}},
         "summary": "object fields: ok, unreadable, broken, ruleFormat, paused"},
    ]
    coverage = assess_investigation(plan, source)
    assert coverage["domain"] == "app_class_identity"
    assert coverage["evidenceComplete"] is False
    states = {x["key"]: x["state"] for x in coverage["requirements"]}
    assert states == {
        "instance_identity": "checked-unverified",
        "native_class_binding": "checked-unverified",
    }


def test_false_native_binding_without_matching_typed_source_never_certified():
    plan = plan_investigation(IDENTITY_REQUEST)
    rows = [{
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "tool_result",
        "arguments": {"tool": "hub_get_app_config", "args": {"appId": "169"}},
        "details": {
            "appId": "169", "appTypeId": "718",
            "namespace": "hubitat", "className": "Rule Machine",
            "nativeClassBindingVerified": True,
        },
    }]
    assert assess_investigation(plan, rows)["evidenceComplete"] is False


def test_shared_completion_does_not_retain_wrong_rule_action_requirements():
    prior_wrong = {
        "domain": "existing_rule_verification",
        "evidenceComplete": False,
        "requirements": [
            {"key": "stored_logic", "state": "checked-unverified"},
            {"key": "health", "state": "checked-unverified"},
        ],
        "stopRule": "Must retrieve nested IF/ordered actions",
    }
    original_message = (
        "App 169's native parent class relationship has not been established. "
        "Its displayed label is insufficient; request an authoritative "
        "typed appTypeId to built-in namespace/class relationship."
    )
    outcome = AgentOutcome(
        message=original_message, request_class="live-read",
        choices=[], investigation_coverage=prior_wrong,
        evidence=[{
            "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
            "success": True, "mutates": False, "effect": "read",
            "arguments": {"tool": "hub_get_app_config", "args": {"appId": "169"}},
            "summary": "object fields: success, app, page, controls",
        }],
    )
    obs = build_observed_agent_outcome(
        outcome, {"outcome": "success", "counters": {}, "timings_ms": {}}
    )
    tested = apply_shared_investigation_completion(obs, IDENTITY_REQUEST)
    coverage = tested.investigation_coverage
    assert coverage["domain"] == "app_class_identity"
    assert coverage["evidenceComplete"] is False
    assert {x["key"] for x in coverage["requirements"]} == {
        "instance_identity", "native_class_binding"
    }
    assert coverage["sourceChecksComplete"] is False
    assert tested.metrics["outcome"] == "unresolved"
    assert tested.message == original_message
    assert "ordered actions" not in tested.message
    assert "inactivity-OFF" not in tested.message


def test_existing_rule_claim_guard_is_defensive_against_stale_domain_label():
    message = "The parent app's native class relationship remains unverified."
    stale = {"domain": "existing_rule_verification",
             "requirements": [{"key": "stored_logic",
                               "state": "checked-unverified"}]}
    assert calibrate_existing_rule_verification(
        message, [], stale, request=IDENTITY_REQUEST,
    ) == message
    genuine = calibrate_existing_rule_verification(
        message, [], stale, request=DEEP_RULE,
    )
    assert genuine.startswith("**Read-only existing-rule verification")
