"""Regression: installed-rule audits must not become future rule proposals."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from investigation_intelligence import plan_investigation, assess_investigation
from rule_authoring_service import RuleAuthoringService
from targeted_rule_scope_policy import (
    is_existing_rule_verification_request,
    is_new_rule_design_review_request,
)


CURRENT_RULE = (
    'Perform a targeted READ-ONLY audit of existing Rule Machine app 4246 '
    '"Livingroom Light 1 – Night Idle OFF – TEST". Verify its persisted six '
    "triggers, seven ordered actions, the cancelable delay, enabled state and "
    "health. Compare existing app 4019 inactivity-off behaviour and identify "
    "duplicate rules. Do not create, modify or execute any rule or device."
)

FUTURE_RULE = (
    "I want to create a new Rule Machine automation. Review the existing "
    "controller app 4019 and propose an implementation plan, without "
    "creating or modifying anything. This is a read-only design review."
)


@pytest.mark.parametrize("request", [
    CURRENT_RULE,
    "Audit the triggers and action sequence for app 4246. Do not change anything.",
    "Verify Rule Machine app 4246 health, conditions, enabled state. Do not create another rule.",
    "Check whether app 4019 interferes with rule 4246: compare triggers and delays. Read only.",
])
def test_named_installed_rule_uses_existing_verification(request):
    assert is_existing_rule_verification_request(request)
    assert not is_new_rule_design_review_request(request)
    goal = plan_investigation(request)
    assert goal is not None
    assert goal.domain == "existing_rule_verification"
    assert "native_capabilities" not in {x.key for x in goal.requirements}


def test_existing_rule_retains_no_write_safety_classifier():
    # The original conservative classifier remains unchanged for write safety,
    # but must no longer impose future-design prose or coverage on this audit.
    assert RuleAuthoringService.is_read_only_rule_design_request(CURRENT_RULE)
    assert not is_new_rule_design_review_request(CURRENT_RULE)


def test_future_proposal_with_installed_controller_stays_proposal_only():
    assert RuleAuthoringService.is_read_only_rule_design_request(FUTURE_RULE)
    assert not is_existing_rule_verification_request(FUTURE_RULE)
    assert is_new_rule_design_review_request(FUTURE_RULE)
    assert plan_investigation(FUTURE_RULE).domain == "rule_design_review"


def receipt(tool, app_id="4246", *, details=None, kind="tool_result"):
    return {
        "tool": "hub_read_apps_code" if tool != "hub_get_rule_health" else "hub_read_rules",
        "sub_tool": tool,
        "arguments": {"tool": tool, "args": {"appId": str(app_id)}},
        "evidence_kind": kind,
        "success": True,
        "mutates": False,
        "details": details or {},
        "summary": "object fields: success, app, page, settingsKeyCount",
    }


def test_generic_config_receipt_cannot_verify_action_tree():
    plan = plan_investigation(CURRENT_RULE)
    evidence = [
        receipt("hub_get_rule_health", details={
            "appId": "4246",
            "verifiedHealth": {"stopped": False, "broken": False},
        }, kind="native_rule_evidence"),
        receipt("hub_get_app_config"),
        receipt("hub_list_apps"),
    ]
    result = assess_investigation(plan, evidence)
    states = {r["key"]: r["state"] for r in result["requirements"]}
    assert states["identity"] == "observed"
    assert states["health"] == "observed"
    assert states["stored_logic"] == "checked-unverified"
    assert states["duplicates"] == "checked-unverified"
    assert result["evidenceComplete"] is False
    assert result["domain"] == "existing_rule_verification"


def test_explicit_typed_semantics_can_satisfy_stored_logic_without_invention():
    plan = plan_investigation(CURRENT_RULE)
    health = receipt("hub_get_rule_health", details={
        "appId": "4246", "verifiedHealth": {"stopped": False},
    }, kind="native_rule_evidence")
    typed = receipt("hub_get_app_config", details={
        "appId": "4246",
        "semanticFieldsValidated": True,
        "orderedActionsValidated": True,
        "conditionsValidated": True,
        "triggerCount": 6,
        "actionCount": 7,
    }, kind="typed_existing_rule_facts")
    result = assess_investigation(plan, [health, typed])
    assert result["evidenceComplete"] is True
    assert result["status"] == "evidence-acquired"


def test_unscoped_and_genuine_whole_hub_audits_not_hijacked():
    for request in (
        "Audit my entire Hubitat hub including app 4246 and all devices and automations.",
        "Perform a comprehensive system-wide audit of rules, devices and logs.",
        "Show status of the Livingroom light.",
    ):
        assert not is_existing_rule_verification_request(request)


def test_old_manual_lockout_execution_question_keeps_historical_plan():
    request = (
        "Investigate why manual OFF motion lockout was triggered "
        "by button in app 4019"
    )
    assert plan_investigation(request).domain == "manual_motion_lockout"
