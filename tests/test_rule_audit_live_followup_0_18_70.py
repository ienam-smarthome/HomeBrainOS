"""v0.18.70 regressions from real 23 October app 4246 live audits.

Prevent these routes from becoming a whole-hub audit, future-rule proposal
or raw Groovy-source coverage when the user wants stored Rule Machine facts.
No test creates/modifies Hubitat devices or installed automations.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from adaptive_investigation_policy import source_evidence_request
from automation_diagnostic_policy import is_broad_automation_runtime_diagnostic
from composite_system_audit_policy import is_cross_domain_hub_audit_request
from health_audit_service import is_comprehensive_system_audit_request
from investigation_intelligence import plan_investigation
from rule_authoring_service import RuleAuthoringService
from targeted_rule_scope_policy import (
    is_existing_rule_verification_request, is_new_rule_design_review_request,
    is_targeted_rule_investigation, named_rule_app_ids,
)

LIVE_TEST_1 = """Perform a comprehensive READ-ONLY verification of the existing
Hubitat Rule Machine app 4246, "Livingroom Light 1 – Night Idle OFF – TEST".

This rule has already been created. This is NOT a request to design or create
another rule.

1. Retrieve actual persisted configuration, enabled state and health.
2. Verify its six triggers, seven ordered actions, 10-minute cancelable delay,
   nested IF conditions and 23:00–06:00 nighttime window.
3. Search for all Rule Machine apps with the exact same name. Return every
   matching app ID and disclose whether the inventory was complete.
4. Retrieve existing controller app 4019 and determine its actual persisted
   inactivity-OFF duration. Investigate "none" versus "30 seconds".
5. Establish whether app 4019 could switch device 7805 OFF before app 4246's
   10-minute countdown finishes.
6. Show the actual source evidence behind each conclusion. Distinguish verified
   configuration, unverified settings and runtime behaviour.

Report the investigation domain, evidence coverage and missing evidence.
Do not propose a new rule, check write feasibility, request confirmation,
modify anything or execute any device command."""

LIVE_TEST_2 = (
    "Perform a targeted READ-ONLY audit of existing Rule Machine app 4246. "
    "Verify persisted triggers, ordered actions, cancelable 10-minute delay "
    "and health. Compare app 4019 configuration and find duplicate exact-name "
    "rules. Do not propose a new rule. Do not create or modify anything."
)


@pytest.mark.parametrize("question", [LIVE_TEST_1, LIVE_TEST_2])
def test_live_app_4246_is_deep_existing_rule_not_future_design(question):
    assert named_rule_app_ids(question)[:1] == ("4246",)
    assert is_targeted_rule_investigation(question)
    assert is_existing_rule_verification_request(question)
    assert not is_new_rule_design_review_request(question)
    plan = plan_investigation(question)
    assert plan is not None and plan.domain == "existing_rule_verification"
    assert not is_comprehensive_system_audit_request(question)
    assert not is_cross_domain_hub_audit_request(question)
    assert not is_broad_automation_runtime_diagnostic(question)


def test_actual_source_evidence_is_not_raw_groovy_source():
    assert not source_evidence_request(LIVE_TEST_1)
    assert not source_evidence_request(
        "Show actual source evidence behind each rule configuration claim."
    )
    assert source_evidence_request(
        "Investigate actual source implementation of app 4019."
    )
    assert source_evidence_request(
        "Analyse the Groovy source code for app 4019."
    )


@pytest.mark.parametrize("question", [
    "Audit all rules with exact same name as app 4246 and compare persisted actions.",
    "Inspect all Rule Machine apps with the exact same name as app 4246. "
    "Verify ordered actions and delay.",
])
def test_scoped_exact_name_duplicate_listing_is_not_whole_hub_audit(question):
    assert is_targeted_rule_investigation(question)
    assert is_existing_rule_verification_request(question)
    assert not is_comprehensive_system_audit_request(question)
    assert not is_cross_domain_hub_audit_request(question)


def test_genuine_global_hub_request_is_not_hijacked():
    prompt = (
        "Perform a comprehensive audit of my entire Hubitat hub, "
        "including all rules and devices, logs, scheduled jobs and app 4246."
    )
    assert not is_targeted_rule_investigation(prompt)
    assert is_cross_domain_hub_audit_request(prompt)


@pytest.mark.parametrize("question", [
    "Review Rule Machine app 4246's current status, configuration and health. "
    "Read-only. Do not change anything.",
    "Inspect rule 4246 health. Do not propose a new rule.",
])
def test_simple_installed_rule_status_not_future_design(question):
    assert not is_new_rule_design_review_request(question)


def test_true_new_rule_proposal_keeps_read_only_design_gate():
    prompt = (
        "I want to create a NEW Rule Machine automation in the future. "
        "Review existing controller app 4019 and propose an implementation plan. "
        "This is a read-only design review. Do not create, modify or execute anything."
    )
    assert RuleAuthoringService.is_read_only_rule_design_request(prompt)
    assert is_new_rule_design_review_request(prompt)
    assert not is_existing_rule_verification_request(prompt)
    assert plan_investigation(prompt).domain == "rule_design_review"
