"""Regression: a correct appendix cannot excuse an unsafe executable plan."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from rule_design_claim_guard import calibrate_rule_design_review
from investigation_intelligence import plan_investigation
from shared_investigation_completion import apply_shared_investigation_completion


USER_REQUEST = """I want to create a Hubitat Rule Machine automation, but
review existing automations and show an implementation plan before changes.
Between 23:00 and 06:00, with Livingroom Light 1 ON, if FP300 sensor has
remained inactive continuously for 10 minutes, turn it OFF. Cancel pending
OFF if motion active. Handle the light turned ON while already inactive.
Do not interfere with app 4019's manual-off lockout.
This is a read-only review and proposal. Do not create or execute any
rule commands. I will explicitly authorise creation separately."""


MODEL_RESPONSE = """**Read-only rule design review — no automation or device changed.**

### 1. Device & Capability Verification
Device 7764: FP300 Toilet sensor (reported). Light 7805 switch.

### 2. Existing Automation Audit
App 4019 currently handles inactive-off, reportedly 30 seconds.

### 3. Proposed Implementation Plan
#### Logic Specification:
Required Expression: Between two times 23:00 and 06:00.
Actions:
1. Wait for event: motion active FOR 10 minutes.
2. IF Wait timed out THEN OFF.
#### How this satisfies requirements
1. The Wait for Event with a timeout ensures continuous inactivity.
2. Required Expression prevents rule execution outside the window.
3. OFF-only cannot trigger a manual-off lockout.

### 4. Technical Feasibility & Verification
Yes, hub_set_rule supports all required components, guaranteed.
I will use the hub_manage_rule_machine gateway to create a native Rule Machine rule.

### Rule design feasibility gate (read-only)
Not yet validated as a native rule.
"""


def source(leaf, value):
    key = "deviceId" if "device" in leaf else "appId"
    return {"tool": "hub_read_apps_code", "sub_tool": leaf,
            "success": True, "mutates": False, "evidence_kind": "tool_result",
            "arguments": {"tool": leaf, "args": {key: value}},
            "summary": "object fields: app, page, settingsKeyCount"}


def test_replaces_contradictory_executable_plan_not_just_append_disclaimer():
    result = calibrate_rule_design_review(
        MODEL_RESPONSE, [
            source("hub_get_device", "7764"),
            source("hub_get_app_config", "4019"),
        ], request=USER_REQUEST,
    )
    assert "FP300 Toilet sensor" in result
    assert "App 4019" in result
    assert "23:00–06:00" in result
    assert "10 minutes of uninterrupted inactivity" in result
    assert "window opens" in result
    assert "immediately before every OFF" in result
    assert "event **or**" in result
    assert "Wait timed out THEN OFF" not in result
    assert "timeout ensures continuous inactivity" not in result
    assert "Required Expression prevents rule execution" not in result
    assert "hub_set_rule supports all required components" not in result
    assert "I will use the hub_manage_rule_machine" not in result
    assert "No native write payload" in result
    assert result.count("Rule design feasibility gate") == 1
    assert result.count("**Evidence qualification:**") == 1
    assert calibrate_rule_design_review(
        result, [], request=USER_REQUEST,
    ) == result


def test_design_without_explicit_time_or_duration_keeps_generic_language():
    r = calibrate_rule_design_review(
        "### 3. Proposed Implementation Plan\n"
        "Wait for event: motion active FOR ten minutes; then OFF.\n"
        "### 4. Technical Feasibility & Verification\n"
        "Everything is supported.\n",
        [], request="Please review this proposed automation; do not create it.",
    )
    assert "the user-specified time window" in r
    assert "the requested duration" in r
    assert "Everything is supported." not in r
    assert "No native write payload" in r
    assert "### 3. Proposed rule behaviour" in r


def test_read_only_rule_design_not_vacuously_certified_by_empty_history_kinds():
    plan = plan_investigation(USER_REQUEST)
    assert plan is not None and plan.domain == "rule_design_review"
    evidence = [source("hub_get_device", "7764"),
                source("hub_get_app_config", "4019")]
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="The current sources do not establish native wait semantics.",
        evidence=evidence, metrics={"outcome": "success"},
        investigation_coverage=None,
    )
    wrapped = apply_shared_investigation_completion(outcome, USER_REQUEST)
    assert wrapped.investigation_coverage["domain"] == "rule_design_review"
    assert wrapped.investigation_coverage["sourceChecksComplete"] is False
    assert wrapped.investigation_coverage["sourceCoverage"]["sourceKindsChecked"] is None
    assert wrapped.investigation_coverage["evidenceComplete"] is False
    assert "device_history" not in str(wrapped.investigation_coverage)
