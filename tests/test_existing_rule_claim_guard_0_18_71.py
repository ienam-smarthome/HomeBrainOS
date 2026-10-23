"""v0.18.71: model confidence must not exceed retained evidence for app 4246."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from existing_rule_claim_guard import calibrate_existing_rule_verification
from investigation_intelligence import plan_investigation, assess_investigation


REQUEST = (
    "Verify the existing Rule Machine app 4246, persisted ordered actions, "
    "delay and health. Check duplicate names and compare app 4019. "
    "Do not create or modify anything."
)

CLAIM = """**Read-only rule design review — no automation or device was changed or queued for approval.**

### Rule 4246: Persisted Logic & Health
**Health:** Healthy/Active.
**Triggers:** Six verified triggers.
**Ordered Actions:** Seven conditions; cancelable ten-minute delay.
**Exact-Name Duplicates:** No other rules with the exact label.
**App 4019:** Inactive OFF after 30 seconds; motion lockout 208 minutes.
"""


def receipt(tool: str, app: str, kind="tool_result", details=None):
    return {
        "tool": "hub_read_rules" if "health" in tool or "variable" in tool else "hub_read_apps_code",
        "sub_tool": tool,
        "success": True,
        "mutates": False,
        "evidence_kind": kind,
        "arguments": {"tool": tool, "args": {"appId": app}},
        "details": details or {},
        "summary": "object fields: app, page, settingsKeyCount, childApps",
    }


def coverage(rows):
    plan = plan_investigation(REQUEST)
    assert plan and plan.domain == "existing_rule_verification"
    return assess_investigation(plan, rows)


def test_generic_receipt_does_not_certify_model_claims():
    rows = [
        receipt("hub_get_rule_health", "4246", "native_rule_evidence", {
            "appId": "4246", "verifiedHealth": {"stopped": False, "broken": False},
        }),
        receipt("hub_list_rule_local_variables", "4246", "native_rule_evidence", {
            "appId": "4246", "returnedVariableCount": 0, "numericVariables": [],
        }),
        receipt("hub_get_rule_health", "4019", "native_rule_evidence", {
            "appId": "4019", "verifiedHealth": {"stopped": False},
        }),
        receipt("hub_get_app_config", "4246"),
        receipt("hub_get_app_config", "4019"),
        receipt("hub_list_rules", "4246"),
    ]
    analysis = coverage(rows)
    assert analysis["evidenceComplete"] is False
    msg = calibrate_existing_rule_verification(CLAIM, rows, analysis, request=REQUEST)
    assert "Read-only existing-rule verification" in msg
    assert "Read-only rule design review" not in msg
    assert "App 4246: stopped=false, broken=false" in msg
    assert "App 4019: stopped=false" in msg
    assert "0 local variable(s) returned" in msg
    for unsafe in ("Six verified triggers", "No other rules with the exact label",
                   "Inactive OFF after 30 seconds", "208 minutes",
                   "Seven conditions", "Healthy/Active."):
        assert unsafe not in msg
    assert "Not independently verified" in msg
    assert "Investigation remains partial" in msg


def test_source_health_with_no_actual_typed_fields_not_marked_verified():
    rows = [receipt("hub_get_rule_health", "4246", "tool_result",
                    {"appId": "4246", "verifiedHealth": {"broken": False}})]
    msg = calibrate_existing_rule_verification(CLAIM, rows, coverage(rows), request=REQUEST)
    assert "App 4246: broken=false" not in msg
    assert "No typed rule-health" in msg


def test_successful_page_read_only_not_enough_even_with_generic_settings_keys():
    rows = [receipt("hub_get_app_config", "4246", details={
        "appId": "4246", "settingsKeyCount": 42, "settingsNote": "present",
    })]
    msg = calibrate_existing_rule_verification(CLAIM, rows, coverage(rows), request=REQUEST)
    assert "settingsKeyCount" not in msg
    assert "typed" in msg.lower()
    assert "App 4246: stopped=false" not in msg


def test_typed_semantic_evidence_can_preserve_synthesis():
    rows = [
        receipt("hub_get_rule_health", "4246", "native_rule_evidence", {
            "appId": "4246", "verifiedHealth": {"stopped": False}
        }),
        receipt("hub_get_app_config", "4246", "typed_existing_rule_facts", {
            "appId": "4246", "semanticFieldsValidated": True,
            "orderedActionsValidated": True, "conditionsValidated": True,
            "triggerCount": 6, "actionCount": 7,
        }),
    ]
    analysis = coverage(rows)
    assert analysis["evidenceComplete"] is True
    rendered = calibrate_existing_rule_verification(
        "Six triggers and seven actions were source-verified.", rows, analysis, request=REQUEST
    )
    assert "Six triggers and seven actions" in rendered


def test_foreign_domain_not_rewritten():
    rows = []
    assert calibrate_existing_rule_verification(
        CLAIM, rows, {"domain": "rule_design_review"}, request=REQUEST
    ) == CLAIM.strip()


def test_forged_health_boolean_does_not_validate_state():
    rows = [receipt("hub_get_rule_health", "4246", "native_rule_evidence", {
        "appId": "4246", "verifiedHealth": {"stopped": "false", "broken": 0},
    })]
    msg = calibrate_existing_rule_verification(CLAIM, rows, coverage(rows), request=REQUEST)
    assert "App 4246: stopped=false, broken=false" not in msg
