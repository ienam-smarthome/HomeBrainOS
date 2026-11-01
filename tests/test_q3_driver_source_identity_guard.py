"""Regression: source code IDs cannot be guessed from device instance IDs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from driver_source_identity_guard import (
    _linked_driver_source_ids, unverified_driver_source_read,
)


def receipts(*, source_id=None, device_id="9911", label="Generic Outlet"):
    details = {
        "reportedDeviceState": {
            "deviceId": device_id, "label": label,
            "observedAt": "2026-11-01T20:41:52+00:00",
            "reportedAttributes": {"healthStatus": "offline",
                                   "mqttStatus": "connected"},
            "source": "targeted-hubitat-device-state",
        }
    }
    if source_id is not None:
        details["driverSource"] = {"sourceCodeId": source_id}
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "effect": "read",
            "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": label}},
            "details": details,
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": device_id, "hoursBack": 24}},
            "details": {"deviceId": device_id, "observedEvents": [
                {"name": "deviceHealth", "value": "stale",
                 "date": "2026-11-01T20:39:42+00:00",
                 "producedBy": {"id": device_id,
                                "type": "device", "label": label}},
            ]},
        },
    ]


def proposed(id, *, tool="hub_read_apps_code", kind="driver"):
    return tool, {"tool": "hub_get_source",
                  "args": {"type": kind, "id": id}}


def rejected(code_id, evidence=None, domain="device_telemetry"):
    tool, args = proposed(code_id)
    return unverified_driver_source_read(
        tool, args, receipts() if evidence is None else evidence,
        domain=domain,
    )


def test_device_id_is_not_driver_source_id_even_when_numeric():
    assert rejected("9911") is True
    assert rejected("3686") is True
    assert _linked_driver_source_ids(receipts(), "9911") == frozenset()


def test_verified_source_metadata_allows_correct_driver_id_not_device_id():
    evidence = receipts(source_id="3686")
    assert _linked_driver_source_ids(evidence, "9911") == {"3686"}
    assert rejected("3686", evidence) is False
    assert rejected("9911", evidence) is True


def test_source_id_from_matching_scoped_device_config_is_admitted():
    evidence = receipts()
    evidence.append({
        "sub_tool": "hub_get_device", "tool": "hub_read_devices",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_device",
                      "args": {"deviceId": "9911", "mode": "configuration"}},
        "details": {"deviceId": "9911",
                    "deviceInfo": {"driverSourceCodeId": 3686}},
    })
    assert rejected("3686", evidence) is False


def test_unrelated_device_or_app_source_metadata_cannot_link_driver():
    evidence = receipts()
    evidence.append({
        "sub_tool": "hub_get_device", "tool": "hub_read_devices",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_device",
                      "args": {"deviceId": "9922"}},
        "details": {"deviceId": "9922",
                    "driverSource": {"sourceCodeId": "3686"}},
    })
    assert rejected("3686", evidence)
    evidence.append({
        "sub_tool": "hub_get_source", "tool": "hub_read_apps_code",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_source",
                      "args": {"type": "app", "id": "3686"}},
        "details": {"sourceCodeId": "3686"},
    })
    assert rejected("3686", evidence)


def test_no_model_source_access_for_wrong_target_even_if_source_id_same_number():
    evidence = receipts(source_id="3686")
    evidence[0]["details"]["reportedDeviceState"]["deviceId"] = "9922"
    assert rejected("3686", evidence) is False  # Fails open without a verified target.


def test_no_block_outside_telemetry_or_for_non_source_read():
    evidence = receipts()
    for domain in ("heating", "causal_lighting", "rule_design_review", None):
        assert rejected("9911", evidence, domain=domain) is False
    tool, args = proposed("9911", kind="app")
    assert not unverified_driver_source_read(tool, args, evidence, domain="device_telemetry")
    assert not unverified_driver_source_read(
        "hub_read_devices", {"tool": "hub_get_device",
                             "args": {"deviceId": "9911"}},
        evidence, domain="device_telemetry",
    )


def test_no_history_or_multitarget_evidence_does_not_assert_driver_mapping():
    evidence = receipts()
    evidence.pop()
    assert rejected("9911", evidence) is False
    evidence = receipts()
    evidence.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "9922"}},
        "details": {"deviceId": "9922", "observedEvents": [
            {"name": "deviceHealth", "value": "stale",
             "date": "2026-11-01T20:39:42+00:00"},
        ]},
    })
    assert rejected("9911", evidence) is False
