"""Q3 source-scoped read-admission policy, independent of device names."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from single_device_read_scope import single_device_broad_read_reason
from typed_device_history_evidence import normalize_target_device_history


def fixture(label="Relay A", target="9911"):
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True,
            "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": label, "detailed": True}},
            "details": {
                "reportedDeviceState": {
                    "deviceId": target, "label": label,
                    "source": "targeted-hubitat-device-state",
                    "observedAt": "2026-11-01T19:59:30+00:00",
                    "reportedAttributes": {"healthStatus": "offline",
                                           "mqttStatus": "connected"},
                },
            },
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": target, "hoursBack": 24}},
            "details": {"deviceId": target, "observedEvents": [
                {"name": "deviceHealth", "value": "stale",
                 "date": "2026-11-01T19:59:26+00:00",
                 "producedBy": {"id": target, "label": label,
                                "type": "device"}}
            ]},
        },
    ]


def decide(name, args, *, question="Why is Relay A offline?",
           evidence=None, domain="device_telemetry"):
    return single_device_broad_read_reason(
        question, fixture() if evidence is None else evidence, name, args,
        domain=domain,
    )


def test_source_identity_and_targeted_state_required_before_restriction():
    evidence = fixture()
    assert normalize_target_device_history(evidence)["deviceId"] == "9911"
    assert decide("hub_read_devices", {"resource": "hubitat://context"}) == (
        "whole-home-context-after-target-resolution"
    )
    assert decide("homebrain_home_snapshot", {}) == (
        "whole-home-snapshot-after-target-resolution"
    )
    assert decide("homebrain_filter_devices", {
        "attribute": "name", "operator": "contains", "value": "Different driver"
    }) == "unrelated-name-filter-after-target-resolution"
    # Real v0.18.338 regression: a local filter(deviceHealth=stale)
    # internally invokes an unscoped 207-device Hubitat list. The outer
    # filter must be admitted/blocked BEFORE that nested expensive request.
    assert decide("homebrain_filter_devices", {
        "attribute": "deviceHealth", "operator": "eq", "value": "stale",
    }) == "unscoped-attribute-filter-after-target-resolution"
    assert decide("hub_read_devices", {
        "tool": "hub_list_devices", "args": {}
    }) == "unscoped-inventory-after-target-resolution"


def test_targeted_driver_logs_and_related_device_read_remain_permitted():
    assert decide("hub_read_diagnostics", {
        "tool": "hub_get_logs", "args": {"deviceId": "9911"}
    }) is None
    assert decide("hub_read_apps_code", {
        "tool": "hub_get_source", "args": {"id": "2111", "type": "driver"}
    }) is None
    assert decide("hub_read_devices", {
        "tool": "hub_get_device", "args": {"deviceId": "9911"}
    }) is None
    assert decide("hub_read_devices", {
        "tool": "hub_list_devices", "args": {"labelFilter": "Related Sensor"}
    }) is None
    assert decide("homebrain_filter_devices", {
        "attribute": "name", "value": "Relay"
    }) is None
    assert decide("homebrain_filter_devices", {
        "attribute": "name", "value": "Relay A",
    }) is None


def test_different_domains_and_explicit_comparisons_do_not_narrow_reads():
    for domain in ("heating", "causal_lighting", "rule_design_review", None):
        assert decide("hub_read_devices", {
            "resource": "hubitat://context"
        }, domain=domain) is None
    for question in (
        "Compare Relay A with other devices' connectivity.",
        "List all devices and identify Relay A.",
        "Why is Relay A offline across the whole hub?",
        "Compare healthStatus stale across all devices including Relay A.",
    ):
        assert decide("hub_read_devices", {
            "resource": "hubitat://context"
        }, question=question) is None


def test_ambiguous_or_unsupported_identity_fails_open():
    assert decide("hub_read_devices", {"resource": "hubitat://context"},
                  question="Why is that socket offline?") is None
    evidence = fixture()
    evidence[0]["details"] = {}
    assert decide("hub_read_devices", {"resource": "hubitat://context"},
                  evidence=evidence) is None
    evidence = fixture()
    evidence.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "9922"}},
        "details": {"observedEvents": [
            {"name": "switch", "value": "off",
             "date": "2026-11-01T19:58:00+00:00"}
        ]},
    })
    assert decide("hub_read_devices", {"resource": "hubitat://context"},
                  evidence=evidence) is None


def test_same_policy_generalizes_to_non_mqtt_plugs_and_gadgets():
    evidence = fixture(label="Kitchen relay", target="2003")
    assert single_device_broad_read_reason(
        "Investigate Kitchen relay reported health.",
        evidence,
        "homebrain_filter_devices",
        {"attribute": "name", "operator": "contains", "value": "Other"},
        domain="device_telemetry",
    ) == "unrelated-name-filter-after-target-resolution"
