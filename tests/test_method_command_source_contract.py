"""Cross-domain typed-method command evidence and bounded decision-source tests.

Synthetic records model a thermostat method command. They do not prove
physical boiler state, protection status, real app behaviour or model quality.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from general_evidence_completion import assess_task_source_coverage
from method_command_source_contract import (
    typed_method_command_records, command_source_packet,
    pending_command_app_decision_log, render_command_source_packet,
)

QUESTION = (
    "Investigate why the main Thermostat is currently heating or requesting "
    "heat, considering heating setpoints, protection, Early Heating OFF, "
    "and the scheduler's most recent decisions. Do not change anything."
)


def evidence():
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "effect": "read",
        "mutates": False,
        "evidence_kind": "deterministic_device_event_history",
        "arguments": {"name": "Thermostat"},
        "details": {
            "label": "Thermostat",
            "observedEvents": [
                {
                    "name": "thermostatMode", "value": "off",
                    "date": "2026-11-01T22:30:02.791+0000",
                    "isStateChange": True, "producedBy": {
                        "type": "device", "id": "4382",
                    },
                },
                {
                    "name": "command-setThermostatMode",
                    "type": "command", "isStateChange": False,
                    "description": "Command called: setThermostatMode(off)",
                    "date": "2026-11-01T22:30:02.397+0000",
                    "producedBy": {
                        "type": "app", "id": "2710",
                        "label": "Test Thermostat OFF",
                    },
                },
            ],
        },
    }]


def test_method_command_is_positive_command_source_without_physical_proof():
    items = evidence()
    record = typed_method_command_records(items)
    assert len(record) == 1
    assert record[0]["recordedIssuerAppId"] == "2710"
    assert record[0]["name"] == "command-setThermostatMode"
    assert record[0]["physicalActuationVerified"] is False
    cov = assess_task_source_coverage(
        ["device_history", "command_history", "app_logs"], items,
    )
    assert cov.checked == ("device_history", "command_history")
    assert cov.missing == ("app_logs",)


def test_verified_target_command_gets_bounded_app_log_window_once():
    items = evidence()
    packet = command_source_packet(QUESTION, items)
    assert packet["target"] == "Thermostat"
    assert packet["physicalPlantOperationVerified"] is False
    assert packet["upstreamAutomationDecisionVerified"] is False
    plan = pending_command_app_decision_log(QUESTION, items)
    assert plan["args"] == {
        "appId": "2710", "since": "2026-11-01T22:20:02Z",
        "until": "2026-11-01T22:40:02Z", "limit": 60,
    }
    assert "physical" in render_command_source_packet(QUESTION, items).lower()
    items.append({
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": False, "arguments": {
            "tool": "hub_get_logs", "args": plan["args"],
        },
    })
    assert pending_command_app_decision_log(QUESTION, items) is None


def test_wrong_label_untrusted_producer_malformed_events_not_attested():
    items = evidence()
    items[0]["arguments"]["name"] = "Other Thermostat"
    assert typed_method_command_records(items) == []
    assert "command_history" in assess_task_source_coverage(
        ["command_history"], items,
    ).missing

    items = evidence()
    items[0]["details"]["observedEvents"][1]["producedBy"]["type"] = "device"
    assert typed_method_command_records(items)[0]["recordedIssuerAppId"] is None
    assert pending_command_app_decision_log(QUESTION, items) is None

    items = evidence()
    items[0]["details"]["observedEvents"][1]["date"] = "not-an-offset-aware-time"
    assert typed_method_command_records(items) == []
    assert command_source_packet(QUESTION, items) is None

    items = evidence()
    items[0]["details"]["observedEvents"][1]["type"] = "state"
    assert typed_method_command_records(items) == []


def test_unrelated_subject_and_nonscheduler_question_do_not_read_app_logs():
    items = evidence()
    assert command_source_packet("Check Other Thermostat", items) is None
    assert pending_command_app_decision_log(
        "What is the current mode of Thermostat?", items,
    ) is None
    assert pending_command_app_decision_log(
        "Investigate why Other Thermostat turned off.", items,
    ) is None


def test_scoped_native_method_command_is_a_positive_history_witness():
    items = [{
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "4382", "hoursBack": 24,
        }},
        "details": {
            "observedEvents": [{
                "name": "command-setThermostatMode",
                "type": "command",
                "date": "2026-11-01T22:30:02.397+00:00",
            }],
        },
    }]
    assert len(typed_method_command_records(items)) == 1
    assert "command_history" in assess_task_source_coverage(
        ["command_history"], items,
    ).checked
    items[0]["arguments"]["args"].pop("deviceId")
    assert typed_method_command_records(items) == []
