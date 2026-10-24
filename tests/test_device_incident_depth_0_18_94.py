"""0.18.94: replay live 0.18.93 device 7103 MQTT/offline diagnosis.

Regression: 0.18.93 checked state, 24h events (14), scoped logs (45)
and stopped with five calls and no driver/automation evidence. The real
historical telemetry counters differed by hundreds of hours. This suite
checks one bounded follow-up and avoids imposing it on ordinary status reads.
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from device_incident_depth import (
    device_incident_followup, is_connectivity_root_cause_request,
)


def evidence(leaf, args, kind="tool_result", success=True):
    return {
        "tool": "hub_read_devices" if leaf != "hub_get_logs" else "hub_read_diagnostics",
        "sub_tool": leaf, "success": success, "mutates": False,
        "effect": "read", "evidence_kind": kind,
        "arguments": {"tool": leaf, "args": args},
    }


QUESTION = (
    "Why does Bedroom 3 Mesh (device 7103) report offline while MQTT "
    "says connected? Investigate thoroughly, determine when communication "
    "stopped and explain the most likely cause using available evidence. "
    "This is read-only; do not change anything."
)

SCOPED_BASELINE = [
    evidence("hub_list_devices", {"labelFilter": "Bedroom 3 Mesh"},
             "targeted_device_lookup"),
    evidence("hub_list_device_events", {"deviceId": "7103", "hoursBack": 24, "limit": 20},
             "authoritative_device_event_history"),
    evidence("hub_get_logs", {"deviceId": "7103", "since": "24h", "limit": 100}),
]


def test_01893_root_cause_investigation_requires_more_than_three_baseline_sources():
    assert is_connectivity_root_cause_request(QUESTION)
    note = device_incident_followup(QUESTION, SCOPED_BASELINE)
    assert note is not None
    assert "READ ONLY" in note
    assert "driver implementation" in note
    assert "automation configuration" in note
    assert "independent network" in note
    assert "Do not repeat" in note
    assert "Never invent" in note


def test_driver_and_automation_reads_are_recognised_but_upstream_still_missing():
    evidence_set = SCOPED_BASELINE + [
        evidence("hub_get_source", {"id": "92", "type": "driver"}),
        evidence("hub_get_app_config", {"appId": "3950"}),
    ]
    note = device_incident_followup(QUESTION, evidence_set)
    assert note is not None
    assert "installed driver implementation" not in note
    assert "controlling automation configuration" not in note
    assert "independent network" in note


def test_independent_upstream_receipt_completes_discriminators():
    data = SCOPED_BASELINE + [
        evidence("hub_get_source", {"id": "92", "type": "driver"}),
        evidence("hub_get_app_config", {"appId": "3950"}),
        {
            "tool": "read_only_upstream_probe", "success": True,
            "mutates": False, "effect": "read",
            "evidence_kind": "physical_network_reachability",
        },
    ]
    assert device_incident_followup(QUESTION, data) is None


def test_simple_snapshot_and_other_causal_event_queries_do_not_force_driver_reads():
    assert not is_connectivity_root_cause_request(
        "What is the current status of device 7103?"
    )
    assert not is_connectivity_root_cause_request(
        "Why did the living room light turn off at 08:30?"
    )
    assert device_incident_followup(
        "Is device 7103 online?", SCOPED_BASELINE
    ) is None


def test_historical_offline_has_no_required_active_switch_interval():
    source = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "device_incident_followup_used = False" in source
    assert "followup = device_incident_followup(" in source
    assert '"device_incident_depth_retry"' in source
    assert "not is_connectivity_root_cause_request(user_prompt)" in source
    assert "catalog.expose_read_gateways(" in source


def test_failed_read_and_app_source_cannot_masquerade_as_driver_source():
    baseline = SCOPED_BASELINE + [
        evidence("hub_get_source", {"id": "1410", "type": "app"}),
        evidence("hub_get_source", {"id": "92", "type": "driver"}, success=False),
    ]
    assert "installed driver implementation" in device_incident_followup(
        QUESTION, baseline
    )
