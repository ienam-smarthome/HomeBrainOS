"""Typed recent command issuer sources vs state reporters and nearby logs."""
from __future__ import annotations

from test_recent_focal_command_source import QUESTION, receipts
from recent_command_issuer_sources import (
    recent_command_issuer_sources, render_recent_command_issuer_sources,
)


def test_reporter_listener_and_later_generic_log_do_not_identify_issuer():
    result = recent_command_issuer_sources(QUESTION, receipts())
    assert result["targetDeviceId"] == "7828"
    assert result["focalState"] == "off"
    assert result["commandHistorySourceChecked"] is False
    assert result["commandIssuerVerifiedByTypedSource"] is False
    assert result["recordedCommandWitnesses"] == []
    packet = render_recent_command_issuer_sources(QUESTION, receipts())
    assert "unscoped" in packet.lower()
    assert "not certify" in packet.lower()


def test_target_scoped_typed_command_is_a_recorded_command_not_physical_cause():
    rows = receipts()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7828", "hoursBack": 24, "attribute": "command-off",
        }},
        "details": {"observedEvents": [{
            "name": "command-off", "date": "2026-11-01T22:49:59.000Z",
            "producedBy": {"appId": 88, "name": "Test Command App"},
        }]},
    })
    result = recent_command_issuer_sources(QUESTION, rows)
    assert result["commandHistorySourceChecked"] is True
    assert result["commandIssuerVerifiedByTypedSource"] is True
    witness = result["recordedCommandWitnesses"][0]
    assert witness["recordedCommandAppId"] == "88"
    assert witness["secondsRelativeToStateReport"] == -1.647
    assert witness["causalEffectVerified"] is False


def test_after_report_command_remains_separately_recorded_not_cause():
    rows = receipts()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "mutates": False,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "7828", "attribute": "command-off",
                               "hoursBack": 24}},
        "details": {"observedEvents": [{
            "name": "command-off", "date": "2026-11-01T22:50:01.236Z",
            "producedBy": {"appId": 4151},
        }]},
    })
    result = recent_command_issuer_sources(QUESTION, rows)
    assert result["recordedCommandWitnesses"][0]["secondsRelativeToStateReport"] == 0.589
    assert result["recordedCommandWitnesses"][0]["causalEffectVerified"] is False


def test_empty_successful_source_check_is_not_proof_that_no_command_existed():
    rows = receipts()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7828", "attribute": "command-off",
        }},
        "details": {"observedEvents": []},
    })
    result = recent_command_issuer_sources(QUESTION, rows)
    assert result["commandHistorySourceChecked"] is True
    assert result["commandIssuerVerifiedByTypedSource"] is False
    assert result["sourceHistoryIsNotComplete"] is True


def test_wrong_device_command_is_not_focal_provenance():
    rows = receipts()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "9911", "attribute": "command-off",
        }},
        "details": {"observedEvents": [{
            "name": "command-off", "date": "2026-11-01T22:50:01.236Z",
            "producedBy": {"appId": 4151},
        }]},
    })
    result = recent_command_issuer_sources(QUESTION, rows)
    assert result["commandHistorySourceChecked"] is False
    assert result["recordedCommandWitnesses"] == []
