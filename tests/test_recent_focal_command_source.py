"""Source-first planning for recent focal causal provenance.

Synthetic, anonymised receipts. Presence of a source read does NOT prove the
reported switch was caused by a command from a nearby app log.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))
from skill_source_completion import pending_recent_focal_command_read


QUESTION = (
    "Investigate why Test Light most recently turned OFF. Identify any "
    "recorded OFF command, the controlling automation and relevant sensor "
    "events. Distinguish the bridge reporter from the command issuer."
)


def receipts():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "evidence_kind": "targeted_device_lookup",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": "Test Light"}},
            "details": {"reportedDeviceState": {
                "deviceId": "7828", "label": "Test Light",
                "reportedAttributes": {"switch": "off"},
                "source": "targeted-hubitat-device-state",
                "isPhysicalConnectivityProof": False,
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False, "effect": "read",
            "arguments": {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7828", "hoursBack": 24,
                         "attribute": "switch"},
            },
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "mutates": False, "effect": "read",
            "arguments": {"name": "Test Light", "attribute": "switch"},
            "details": {
                "label": "Test Light",
                "observedEvents": [{
                    "name": "switch", "value": "off",
                    "date": "2026-11-01T22:50:00.647+0000",
                    "type": "physical",
                    "producedBy": {
                        "type": "device", "id": "100", "label": "Test Bridge",
                    },
                    "triggered": [{"appId": 4020, "name": "Test Listener"}],
                }],
            },
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "mutates": False, "effect": "read",
            "arguments": {"args": {
                "since": "2026-11-01T22:45:00Z",
                "until": "2026-11-01T22:55:00Z",
            }},
            "summary": "A later unscoped completion log mentioned App 4151",
        },
    ]


def test_recent_focal_off_requires_its_own_command_source():
    plan = pending_recent_focal_command_read(QUESTION, receipts())
    assert plan == {
        "deviceId": "7828", "label": "Test Light",
        "action": "off", "hoursBack": 24,
    }


def test_post_event_log_or_bridge_reporting_does_not_satisfy_command_source():
    src = receipts()
    assert pending_recent_focal_command_read(QUESTION, src) is not None
    src.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "7828", "hoursBack": 24,
                               "attribute": "command-off"}},
        "details": {"observedEvents": []},
    })
    # A correctly scoped attempted query is final for this investigation.
    assert pending_recent_focal_command_read(QUESTION, src) is None
    src[-1]["success"] = False
    assert pending_recent_focal_command_read(QUESTION, src) is None


def test_missing_identity_focal_event_or_history_fails_closed():
    src = receipts()
    src[0]["details"]["reportedDeviceState"]["deviceId"] = "9999"
    assert pending_recent_focal_command_read(QUESTION, src) is None
    src = receipts()
    src[2]["details"]["observedEvents"][0]["value"] = "on"
    assert pending_recent_focal_command_read(QUESTION, src) is None
    src = receipts()
    src[1]["arguments"]["args"]["deviceId"] = "9999"
    assert pending_recent_focal_command_read(QUESTION, src) is None
    src = receipts()
    src[2]["arguments"]["name"] = "Other Light"
    assert pending_recent_focal_command_read(QUESTION, src) is None
    src = receipts()
    src[0]["success"] = False
    assert pending_recent_focal_command_read(QUESTION, src) is None
    src = receipts()
    src.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "success": True, "evidence_kind": "targeted_device_lookup",
        "details": {"reportedDeviceState": {
            "deviceId": "9911", "label": "Test Light"}},
    })
    assert pending_recent_focal_command_read(QUESTION, src) is None


def test_only_recent_causal_questions_get_additional_read():
    src = receipts()
    for question in (
        "Is Test Light off right now?",
        "When did Test Light turn off?",
        "Why did Test Light turn off last year?",
        "What happened to other lights?",
        "Identify the sensor that fired for Test Light.",
    ):
        assert pending_recent_focal_command_read(question, src) is None
