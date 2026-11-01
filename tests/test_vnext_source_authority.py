"""Synthetic evidence-authority tests; no claims of measured model quality."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from source_authority_packet import (
    pending_telemetry_configuration_read, telemetry_source_authority,
    render_telemetry_authority,
)

QUESTION = "Investigate why Test Relay reports offline while MQTT reports connected. Do not change anything."


def receipts(device_id="9911", label="Test Relay"):
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "effect": "read", "mutates": False,
            "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": label}},
            "details": {"reportedDeviceState": {
                "deviceId": device_id, "label": label,
                "source": "targeted-hubitat-device-state",
                "observedAt": "2026-11-01T20:00:00+00:00",
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                    "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
                    "dataAgeSeconds": "162325",
                },
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": device_id, "hoursBack": 24}},
            "details": {"observedEvents": [{
                "name": "deviceHealth", "value": "stale",
                "date": "2026-11-01T19:59:00+00:00",
                "producedBy": {"id": device_id, "type": "device"},
            }]},
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_get_logs",
                          "args": {"deviceId": device_id, "since": "24h"}},
            "details": {"logCount": 0},
        },
    ]


def test_plan_one_extra_read_only_configuration_only_for_verified_subject():
    items = receipts()
    assert pending_telemetry_configuration_read(QUESTION, items) == {
        "deviceId": "9911", "mode": "configuration",
    }
    assert pending_telemetry_configuration_read(
        "Investigate why Other Relay is offline.", items,
    ) is None
    assert pending_telemetry_configuration_read(
        "Compare Test Relay with all devices reporting offline.", items,
    ) is None
    assert pending_telemetry_configuration_read(QUESTION, items[:-1]) is None
    copy = receipts()
    copy[-1]["arguments"]["args"]["deviceId"] = "9912"
    assert pending_telemetry_configuration_read(QUESTION, copy) is None
    copy = receipts()
    copy.append({
        "sub_tool": "hub_get_device", "success": False,
        "arguments": {"tool": "hub_get_device",
                      "args": {"deviceId": "9911", "mode": "configuration"}},
    })
    assert pending_telemetry_configuration_read(QUESTION, copy) is None


def test_source_authority_keeps_driver_clock_and_broker_layers_separate():
    items = receipts()
    clock = {
        "deviceId": "9911",
        "sourcesAgree": False,
        "physicalTelemetryProven": False,
        "metadataAgeHoursAtRead": 502.3,
        "reportedDataAgeHours": 45.1,
    }
    authority = telemetry_source_authority(QUESTION, items, clock=clock)
    assert authority["targetDeviceId"] == "9911"
    assert authority["historicalRowsReturned"] == 1
    assert authority["reportedAttributes"]["mqttStatus"] == "connected"
    assert authority["independentBrokerPacketsVerified"] is False
    assert authority["verifiedInstalledDriverBehaviour"] is False
    assert authority["physicalCauseEstablished"] is False
    assert authority["temporalClocks"]["sourcesAgree"] is False
    text = render_telemetry_authority(authority)
    assert "502.3" in text and "45.1" in text
    assert "not verified" in text and "CONFLICTING METADATA CLOCKS" in text
    assert "LWT" not in text  # no invented source mechanism
    assert "Do not assert" in text


def test_no_cross_target_broker_attestation_or_unverified_source_admission():
    items = receipts()
    items.append({
        "success": True, "effect": "read",
        "evidence_kind": "mqtt_broker_packet_evidence",
        "details": {
            "verifiedForDeviceId": "5555",
            "independentObservationVerified": True,
        },
    })
    assert telemetry_source_authority(
        QUESTION, items, clock=None,
    )["independentBrokerPacketsVerified"] is False
    items[-1]["details"]["verifiedForDeviceId"] = "9911"
    assert telemetry_source_authority(
        QUESTION, items, clock=None,
    )["independentBrokerPacketsVerified"] is True
    assert telemetry_source_authority("Investigate Other Relay", items,
                                      clock=None) is None


def test_model_claims_cannot_turn_scheduled_writes_into_read_only_scope():
    items = receipts()
    items[-1]["success"] = False
    assert pending_telemetry_configuration_read(QUESTION, items) is None
    items = receipts()
    items[1]["details"]["observedEvents"] = []
    assert pending_telemetry_configuration_read(QUESTION, items) is None
