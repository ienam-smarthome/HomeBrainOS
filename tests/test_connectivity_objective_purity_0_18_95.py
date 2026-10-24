"""0.18.95: a single-device MQTT incident is NOT a new Rule Machine proposal.

Live regression: 0.18.94 classified the read-only device 7103 investigation
as "rule_design_review", prepended a Rule Machine authoring banner and
appended night-light WAIT/lockout semantics. It also used unrelated room-wide
event history and stopped after finding a generic Tasmota driver inventory.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from device_incident_depth import (
    device_incident_followup, is_connectivity_root_cause_request,
)
from investigation_intelligence import plan_investigation
from investigation_objective import resolve_primary_objective
from rule_authoring_service import RuleAuthoringService
from targeted_rule_scope_policy import is_new_rule_design_review_request
from shared_investigation_completion import apply_shared_investigation_completion


QUESTION = (
    "Why does Bedroom 3 Mesh report offline while MQTT says connected? "
    "Investigate thoroughly and independently, determine when communication "
    "stopped, examine the relevant driver and automation behaviour, and "
    "establish the most likely explanation using available evidence. "
    "Distinguish confirmed findings from hypotheses. Continue with relevant "
    "read-only MCP checks when the initial device history and logs are "
    "insufficient. Do not change anything."
)

def receipt(tool, args, kind="tool_result", details=None):
    return {
        "tool": "hub_read_devices" if tool != "hub_get_logs" else "hub_read_diagnostics",
        "sub_tool": tool, "arguments": {"tool": tool, "args": args},
        "success": True, "supports_live_claim": True,
        "evidence_kind": kind, "mutates": False, "effect": "read",
        "details": details or {},
    }

LIVE_RECEIPTS = [
    receipt(
        "hub_list_devices", {"labelFilter": "Bedroom 3 Mesh"},
        "targeted_device_lookup",
        {
            "reportedDeviceState": {
                "deviceId": "7103", "label": "Bedroom 3 Mesh",
                "observedAt": "2026-10-24T12:33:21.987106+00:00",
                "reportedAttributes": {
                    "healthStatus": "offline",
                    "mqttStatus": "connected",
                    "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
                    "dataAgeSeconds": "162325",
                },
            }
        },
    ),
    receipt(
        "hub_list_device_events", {"deviceId": "7103", "hoursBack": 24, "limit": 20},
        "authoritative_device_event_history",
    ),
    receipt(
        "hub_get_logs", {"deviceId": "7103", "since": "24h", "limit": 100},
        details={"logCount": 48},
    ),
    receipt("hub_list_apps", {"scope": "instances"}),
    receipt("hub_list_drivers", {"nameFilter": "Tasmota"}),
]


def test_exact_user_question_does_not_turn_into_rule_design():
    assert resolve_primary_objective(QUESTION).is_targeted_device
    assert is_connectivity_root_cause_request(QUESTION)
    assert not RuleAuthoringService.is_read_only_rule_design_request(QUESTION)
    assert not is_new_rule_design_review_request(QUESTION)
    plan = plan_investigation(QUESTION)
    assert plan is not None
    assert plan.domain == "device_telemetry"


def test_positive_explicit_rule_proposals_still_support_read_only_review():
    real_rule_requests = [
        "Design a new automation for night motion and switch-off. "
        "This is read-only; do not create anything.",
        "I want a new Rule Machine rule for my light. Review it only and "
        "do not create or install yet.",
        "Propose a rule for disabling the TV after one hour. "
        "Please review only; do not create it.",
    ]
    for question in real_rule_requests:
        assert RuleAuthoringService.is_read_only_rule_design_request(question)
        assert is_new_rule_design_review_request(question)
        assert plan_investigation(question).domain == "rule_design_review"


def test_other_diagnostic_queries_do_not_become_rule_proposals():
    cases = [
        "Review why my automation failed. Read-only; do not change anything.",
        "Investigate which automation controls device 7103. "
        "Inspect configuration and logs only; do not modify settings.",
        "Find why my rule is not executing and review its current status. "
        "Read-only; do not change it.",
        "Why is the living room offline? Do not create a new automation. "
        "Review logs read-only.",
        "Check existing automation behaviour for a failing device. "
        "Do not change anything; read-only.",
    ]
    for query in cases:
        assert not RuleAuthoringService.is_read_only_rule_design_request(query), query


def test_app_and_driver_inventory_does_not_close_the_device_incident():
    note = device_incident_followup(QUESTION, LIVE_RECEIPTS)
    assert note is not None
    assert "installed driver implementation" in note
    assert "relevant power-saving/controlling automation" in note
    assert "independent network" in note


def test_shared_completion_uses_telemetry_and_never_appends_rule_gate():
    outcome = SimpleNamespace(
        message="The device is offline; MQTT broker state and physical power "
                "need separate verification.",
        route="unified-mcp-agent", request_class="live-read",
        evidence=LIVE_RECEIPTS,
        metrics={"outcome": "unresolved", "counters": {}},
        investigation_coverage=None,
    )
    result = apply_shared_investigation_completion(outcome, QUESTION)
    assert result.investigation_coverage["domain"] == "device_telemetry"
    assert "Rule design feasibility gate" not in result.message
    assert "Read-only rule design review" not in result.message
    assert "timing conflict" in result.message.lower() or (
        result.investigation_coverage.get("telemetryClockConsistency") is not None
    )


def test_device_incident_bypasses_switch_command_causal_branch():
    source = (ROOT / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "not connectivity_incident and not source_investigation" in source
    assert "or connectivity_incident" in source
    assert "device_incident_followup(" in source

    synth = (ROOT / "final_answer_coordinator.py").read_text(encoding="utf-8")
    assert "PRIMARY OBJECTIVE: investigate the target device's" in synth
    assert "Do not include a Rule design feasibility gate" in synth
    assert "and not is_connectivity_root_cause_request(original_user)" in synth
