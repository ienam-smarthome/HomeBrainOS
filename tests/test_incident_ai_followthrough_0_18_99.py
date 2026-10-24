"""0.18.99: AI-led read-only root-cause follow-through after real dependencies.

The decision is based on verified receipt progress, not user wording or
predefined room/device IDs. Tests never invoke live Hubitat or write tools.
"""
from __future__ import annotations
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from device_incident_depth import (
    CONNECTIVITY_EVIDENCE_PLAN, incident_progress_followup,
    is_connectivity_root_cause_request,
)
from ai_investigation_routing import (
    ReadRouteDecision, reset_request_interpretation,
    set_request_interpretation,
)

Q = "Why does Bedroom 3 Mesh say MQTT connected when the device is offline?"


def receipt(tool, args, *, success=True, details=None, mutates=False):
    return {
        "tool": "hub_read_apps_code" if "app" in tool or "dependents" in tool
                else "hub_read_devices",
        "sub_tool": tool, "arguments": {"tool": tool, "args": args},
        "success": success, "effect": "write" if mutates else "read",
        "mutates": mutates, "details": details or {},
    }


def baseline():
    return [
        receipt("hub_list_device_events", {"deviceId": "7103", "hoursBack": 24}),
        receipt("hub_get_logs", {"deviceId": "7103"}),
    ]


def test_initial_instruction_keeps_model_responsible_for_tool_choice():
    assert "actual" in CONNECTIVITY_EVIDENCE_PLAN
    assert "driver code id" in CONNECTIVITY_EVIDENCE_PLAN.casefold()
    assert "read-only" in CONNECTIVITY_EVIDENCE_PLAN
    assert "never guess a schema" in CONNECTIVITY_EVIDENCE_PLAN


def test_targeted_dependent_leads_to_one_specific_missing_evidence_checkpoint():
    assert is_connectivity_root_cause_request(Q)
    evidence = baseline() + [
        receipt("hub_list_device_dependents", {"deviceId": "7103"}),
        receipt("hub_get_logs", {"appId": "3999"}, details={"logCount": 0, "logs": []}),
    ]
    followup = incident_progress_followup(Q, evidence)
    assert followup is not None
    assert "7103" in followup
    assert "installed dependent/controlling app settings" in followup
    assert "DRIVER code" in followup
    assert "checked-empty" in followup
    assert "Never issue a write" in followup


def test_no_name_hardcoding_no_other_devices_no_status_command_routes():
    same = baseline() + [receipt("hub_list_device_dependents", {"deviceId": "7103"})]
    assert incident_progress_followup("Is Bedroom 3 Mesh online?", same) is None
    assert incident_progress_followup(Q, baseline()) is None
    # A dependency read for another device cannot authorise a device 7103 lead.
    assert incident_progress_followup(
        Q, baseline() + [receipt("hub_list_device_dependents", {"deviceId": "9999"})]
    ) is None
    assert incident_progress_followup(
        Q, same + [receipt("hub_list_device_events", {"deviceId": "9999"})]
    ) is None


def test_successful_source_attempt_does_not_get_duplicated_and_write_is_ignored():
    data = baseline() + [
        receipt("hub_list_device_dependents", {"deviceId": "7103"}),
        receipt("hub_get_app_config", {"appId": "3999"}),
        receipt("hub_get_source", {"type": "driver", "id": "3686"},
                details={"sourceRetrieved": True, "sourceCodeId": "3686"}),
    ]
    assert incident_progress_followup(Q, data) is None
    data = baseline() + [receipt(
        "hub_list_device_dependents", {"deviceId": "7103"}, mutates=True,
    )]
    assert incident_progress_followup(Q, data) is None


def test_original_ai_objective_governs_followthrough_not_incidental_words():
    question = ("Why is the bedroom plug offline? Inspect its automation "
                "dependencies; do not create new rules.")
    token = set_request_interpretation(
        question, ReadRouteDecision(
            "model_led", "model_choice", objective="device_connectivity",
        ),
    )
    try:
        assert incident_progress_followup(
            question,
            [receipt("hub_list_device_events", {"deviceId": "7501"}),
             receipt("hub_list_device_dependents", {"deviceId": "7501"})],
        ) is not None
    finally:
        reset_request_interpretation(token)


def test_orchestrator_uses_bounded_read_only_progress_checkpoint():
    text = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "CONNECTIVITY_EVIDENCE_PLAN" in text
    assert "incident_progress_followup(" in text
    assert "round_index + 1 < active_round_budget" in text
    assert "device_incident_progress_retry_used = True" in text
    assert "not self._mutation_requested_by_user.get()" in text
