"""Regression for v0.18.33: generic historical explanation drifted to Linptech."""
from __future__ import annotations
import sys
from copy import deepcopy
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from skill_source_completion import (
    pending_scoped_explanation_command_read, block_unscoped_historical_logs,
)
from requested_device_explanation import render_requested_device_explanation


QUESTION = (
    "Explain the difference between a Hubitat switch=off state event, "
    "a command-off event, an automation execution log and physical device "
    "acknowledgement. Which evidence is available for Bedroom 3 Mesh on "
    "12 October 2026? Identify what remains unverified. Read-only."
)


def receipts():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False,
            "evidence_kind": "targeted_device_lookup",
            "arguments": {"tool": "hub_list_devices", "args": {
                "labelFilter": "Bedroom 3 Mesh", "detailed": True,
            }},
            "details": {"reportedDeviceState": {
                "deviceId": "7103", "label": "Bedroom 3 Mesh",
                "reportedAttributes": {"switch": "off", "healthStatus": "offline"},
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False,
            "arguments": {"tool": "hub_list_device_events", "args": {
                "deviceId": "7103", "hoursBack": 168, "limit": 50,
            }},
            "summary": "50 device events for Bedroom 3 Mesh",
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "mutates": False,
            "arguments": {
                "name": "Bedroom 3 Mesh", "hours_back": 168,
            },
            "details": {
                "label": "Bedroom 3 Mesh",
                "historySourceIntegrityVerified": False,
                "observedEventsTruncated": True,
                "observedEvents": [{
                    "name": "deviceHealth", "value": "stale",
                    "date": "2026-10-18T20:45:19.418+0100",
                    "producedBy": {"label": "Bedroom 3 Mesh",
                                   "id": "7103", "type": "device"},
                }],
            },
        },
    ]


def test_generic_explanatory_question_obligates_targeted_command_history():
    assert pending_scoped_explanation_command_read(QUESTION, receipts()) == {
        "deviceId": "7103",
        "label": "Bedroom 3 Mesh",
        "hoursBack": 168,
        "action": "off",
    }


def test_existing_command_read_even_if_failed_does_not_repeat_paid_or_mcp_work():
    evidence = receipts()
    evidence.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7103", "hoursBack": 168,
            "attribute": "command-off",
        }},
    })
    assert pending_scoped_explanation_command_read(QUESTION, evidence) is None


@pytest.mark.parametrize("alteration", [
    "missing_lookup", "wrong_identity", "ambiguous_target", "no_horizon",
])
def test_no_unverified_identity_or_horizon_can_authorize_source_read(alteration):
    evidence = receipts()
    if alteration == "missing_lookup":
        evidence.pop(0)
    elif alteration == "wrong_identity":
        evidence[0]["details"]["reportedDeviceState"]["label"] = "Kitchen Plug"
    elif alteration == "ambiguous_target":
        evidence.append({
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {
                "deviceId": "7104", "label": "Bedroom 3 Mesh",
            }},
        })
    elif alteration == "no_horizon":
        evidence.pop(1)
    assert pending_scoped_explanation_command_read(QUESTION, evidence) is None


def test_only_dated_named_command_evidence_questions_trigger_extension():
    evidence = receipts()
    for question in [
        "Explain the difference between switch and command.",
        "Explain Bedroom 3 Mesh's device status today.",
        "What is the current command-off state for Bedroom 3 Mesh?",
        "Analyze command-off evidence in October without a specific year.",
    ]:
        assert pending_scoped_explanation_command_read(question, evidence) is None


def test_model_log_attempt_is_blocked_if_unscoped_but_scoped_app_allowed():
    ev = receipts()
    assert block_unscoped_historical_logs(QUESTION, ev,
        "hub_read_diagnostics", {"tool": "hub_get_logs", "args": {
            "since": "30m", "limit": 100,
        }})
    assert not block_unscoped_historical_logs(QUESTION, ev,
        "hub_read_diagnostics", {"tool": "hub_get_logs", "args": {
            "deviceId": "7103", "since": "2026-10-11T23:00:00Z",
            "until": "2026-10-12T02:00:00Z",
        }})
    assert not block_unscoped_historical_logs(QUESTION, ev,
        "hub_read_diagnostics", {"tool": "hub_get_logs", "args": {
            "appId": 3950, "since": "2026-10-11T23:00:00Z",
        }})
    assert not block_unscoped_historical_logs(
        "Audit all recent hub warnings in 30m", ev,
        "hub_read_diagnostics", {"tool": "hub_get_logs", "args": {"since": "30m"}})


def test_irrelevant_log_sensor_does_not_replace_subject_or_trigger_second_investigation():
    text = render_requested_device_explanation(
        QUESTION, receipts(), "Linptech Kitchen sensor",
    )
    assert text
    assert "Bedroom 3 Mesh" in text
    assert "device 7103" in text
    assert "Linptech" not in text
    assert "switch=off" in text
    assert "command-off" in text
    assert "Physical acknowledgement" in text
    assert "Command history:" in text
    assert "truncated" in text
    assert "12 October 2026" in text
    assert "unresolved" in text


def test_positive_command_receipt_is_reported_but_not_falsely_acknowledged():
    ev = receipts()
    ev.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7103", "attribute": "command-off", "hoursBack": 168,
        }},
        "details": {"events": [{
            "name": "command-off", "date": "2026-10-17T15:00:00+0100",
            "producedBy": {"type": "app", "id": "3103"},
        }]},
    })
    result = render_requested_device_explanation(QUESTION, ev, "Kitchen Sensor")
    assert "1 command event(s)" in result
    assert "must match the requested historical boundary" in result
    assert "physical acknowledgement" in result.casefold()


def test_not_an_open_ended_selection_or_new_user_device_target():
    assert render_requested_device_explanation(
        "Choose a recent incident to investigate", receipts(), "Kitchen"
    ) is None
    assert render_requested_device_explanation(
        "Explain whether Linptech Kitchen sensor caused Bedroom 3 Mesh to go off.",
        receipts(), "Linptech Kitchen sensor"
    ) is None
