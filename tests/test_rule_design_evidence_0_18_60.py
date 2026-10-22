"""v0.18.60: proposal-only evidence scope and fail-closed RM semantics."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from investigation_intelligence import plan_investigation, assess_investigation
from rule_design_claim_guard import calibrate_rule_design_review
from rule_authoring_service import RuleAuthoringService


PROMPT = """
I want to create a Hubitat Rule Machine automation called
Livingroom Light 1 - Night Idle OFF but review the existing automations
and show me a complete implementation plan before making any changes.
Use Livingroom Light 1 device 7805 and FP300 Livingroom device 7764.
Between 23:00 and 06:00, if the light is on and the sensor is inactive
continuously 10 minutes, turn it off. If motion becomes active, cancel.
Do not interfere with app 4019 manual-off lockout.
Important: This is a read-only review and proposal. Do not create,
modify, disable or execute any rules or device commands. Do not queue
a write for confirmation yet. I will explicitly authorise creation
separately after reviewing your answer.
"""


def receipt(name, arg):
    key = "deviceId" if "device" in name else "appId"
    if name == "hub_get_tool_guide":
        args = {}
    else:
        args = {key: str(arg)}
    return {"success": True, "mutates": False, "tool": (
        "hub_read_devices" if name == "hub_get_device"
        else "hub_read_apps_code"), "sub_tool": name,
        "arguments": {"tool": name, "args": args},
        "evidence_kind": "tool_result",
        "summary": "object fields: id, label, room, sections"}


def test_proposal_preempts_manual_lockout_historical_classifier():
    assert RuleAuthoringService.is_read_only_rule_design_request(PROMPT)
    goal = plan_investigation(PROMPT)
    assert goal is not None
    assert goal.domain == "rule_design_review"
    assert {"devices", "current_rule", "native_capabilities"}.issubset(
        {x.key for x in goal.requirements})
    assert "manual" not in goal.objective.lower()
    assert "historical" not in goal.stop_rule.lower()


def test_config_identity_reads_are_coverage_not_rule_semantics():
    goal = plan_investigation(PROMPT)
    sources = [
        receipt("hub_get_device", "7805"),
        receipt("hub_get_device", "7764"),
        receipt("hub_get_app_config", "4019"),
        receipt("hub_list_device_dependents", "7805"),
    ]
    a = assess_investigation(goal, sources)
    assert a["domain"] == "rule_design_review"
    assert a["evidenceComplete"] is False
    assert a["status"] == "not-established"
    states = {r["key"]: r["state"] for r in a["requirements"]}
    assert states["devices"] == "checked-unverified"
    assert states["current_rule"] == "checked-unverified"
    assert states["native_capabilities"] == "not-checked"
    assert states["dependencies"] == "checked-unverified"
    assert "device_history" not in str(a)
    assert "app_logs" not in str(a)


SAMPLE_REPLY = """**Read-only rule design review — no automation or device was changed.**
### Existing automations
App 4019 is currently configured to turn lights off after 30 seconds.
Since the proposed rule only sends an OFF command, it will not trigger
or interfere with the lockout.
### Native creation
I will use the `hub_manage_rule_machine` gateway to create a native Rule Machine rule.
Can my tools create this? Yes. The `hub_set_rule` tool supports all required components.
Rule Machine natively handles time windows that cross midnight.
Action: Wait for Event: motion active, timeout 10 minutes; after that turn OFF.
"""


def test_unsupported_native_claims_are_calibrated_and_timing_warned():
    result = calibrate_rule_design_review(SAMPLE_REPLY, [
        receipt("hub_get_app_config", "4019")])
    assert "The current evidence does not verify" in result
    assert "The installed Rule Machine's cross-midnight" in result
    assert "its effect on the existing manual-off lockout is not verified" in result
    assert "I will use the" not in result
    assert "Rule design feasibility gate" in result
    assert "23:00 entry" in result
    assert "final" in result
    assert "06:00" in result
    assert "event versus timeout" in result
    assert "30 seconds" in result  # original observed claim remains qualified by appendix
    assert calibrate_rule_design_review(result, []) == result


def test_generic_source_success_cannot_certify_complex_writer():
    receipts = [receipt("hub_get_tool_guide", "")]
    assert "not yet validated" in calibrate_rule_design_review(
        "This needs a conditional timed wait.", receipts).lower()
    receipts.append({
        "success": True, "evidence_kind": "typed_native_rule_design_schema",
        "details": {"completeCombinedSemanticsVerified": False},
    })
    assert "feasibility gate" in calibrate_rule_design_review(
        "Proposed only", receipts)
    receipts[-1]["details"]["completeCombinedSemanticsVerified"] = True
    assert calibrate_rule_design_review("Verified supported design.", receipts) == (
        "Verified supported design."
    )


def test_non_proposals_still_use_historical_lockout_plan():
    historic = "Investigate why manual OFF motion lockout was triggered by button in app 4019"
    assert not RuleAuthoringService.is_read_only_rule_design_request(historic)
    goal = plan_investigation(historic)
    assert goal is not None
    assert goal.domain == "manual_motion_lockout"
