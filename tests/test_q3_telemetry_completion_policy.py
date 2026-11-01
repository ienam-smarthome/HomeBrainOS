"""Evidence-saturated, no-write single-device diagnosis stops repeated retries."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from telemetry_completion_policy import ready_for_bounded_telemetry_answer


def evidence():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "effect": "read",
            "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": "Test Relay"}},
            "details": {"reportedDeviceState": {
                "deviceId": "9911", "label": "Test Relay",
                "source": "targeted-hubitat-device-state",
                "observedAt": "2026-11-01T20:00:00+00:00",
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                },
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": "9911", "hoursBack": 24}},
            "details": {"observedEvents": [{
                "name": "deviceHealth", "value": "stale",
                "date": "2026-11-01T19:59:00+00:00",
                "producedBy": {"id": "9911", "type": "device"},
            }]},
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_get_logs",
                          "args": {"deviceId": "9911", "since": "24h"}},
            "details": {"logCount": 0},
        },
    ]


def ready(items, question="Why is Test Relay offline?",
          domain="device_telemetry", checkpoint=False):
    return ready_for_bounded_telemetry_answer(
        question, items, domain=domain,
        high_information_checkpoint_offered=checkpoint,
    )


def test_insufficient_freshness_and_driver_evidence_keeps_one_gap_check_open():
    source = evidence()
    assert not ready(source)
    assert ready(source, checkpoint=True)


def test_real_target_scoped_configuration_completes_bounded_answer_opportunity():
    src = evidence()
    src.append({
        "tool": "hub_read_devices", "sub_tool": "hub_get_device",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_device",
                      "args": {"deviceId": "9911", "mode": "configuration"}},
    })
    assert ready(src)
    assert not ready(src, question="Why is an unknown relay offline?")


def test_device_dependent_app_needs_specific_config_not_just_a_reference():
    src = evidence()
    src.append({
        "tool": "hub_read_apps_code", "sub_tool": "hub_list_device_dependents",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_list_device_dependents",
                      "args": {"deviceId": "9911"}},
        "details": {"appsUsing": [{"appId": "301"}]},
    })
    assert not ready(src)
    src.append({
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_get_app_config",
                      "args": {"appId": "302"}},
    })
    assert not ready(src)
    src[-1]["arguments"]["args"]["appId"] = "301"
    assert ready(src)


def test_not_for_unbounded_or_non_telemetry_investigations():
    src = evidence()
    assert not ready(src, checkpoint=True, domain="historical_command")
    assert not ready(src, checkpoint=True, domain="heating")
    assert not ready(src, checkpoint=True,
                     question="Compare Test Relay with all devices.")


def test_missing_scoped_log_and_cross_device_identity_fail_open():
    src = evidence()[:-1]
    assert not ready(src, checkpoint=True)
    src = evidence()
    src[0]["details"]["reportedDeviceState"]["deviceId"] = "9999"
    assert not ready(src, checkpoint=True)
    src = evidence()
    src[1]["details"]["observedEvents"] = []
    assert not ready(src, checkpoint=True)
    src = evidence()
    src.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "6666", "hoursBack": 24}},
        "details": {"observedEvents": [
            {"name": "deviceHealth", "value": "offline",
             "date": "2026-11-01T20:01:00+00:00"}
        ]},
    })
    assert not ready(src, checkpoint=True)
