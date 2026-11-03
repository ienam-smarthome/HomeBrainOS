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


def counted_partial_evidence(label="Test Relay", target="9911"):
    """Positive truncated pair with one explicitly unshown source row."""
    from copy import deepcopy

    src = deepcopy(evidence())
    src[0]["details"]["reportedDeviceState"]["label"] = label
    src[0]["details"]["reportedDeviceState"]["deviceId"] = target
    src[0]["arguments"]["args"]["labelFilter"] = label
    src[1] = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "timestamp": "2026-11-03T07:10:54.238034+00:00",
        "summary": f"3 device events for '{label}'",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": target, "hoursBack": 24}},
    }
    src.append({
        "tool": "homebrain_device_history", "sub_tool": None,
        "success": True, "effect": "read", "mutates": False,
        "timestamp": "2026-11-03T07:10:54.240369+00:00",
        "details": {
            "label": label, "hoursBack": 24,
            "observedEvents": [
                {"name": "deviceHealth", "value": "unknown",
                 "date": "2026-11-03T07:09:52+00:00",
                 "producedBy": {"id": target, "type": "device", "label": label}},
                {"name": "deviceHealth", "value": "stale",
                 "date": "2026-11-03T07:07:42+00:00",
                 "producedBy": {"id": target, "type": "device", "label": label}},
            ],
            "sourceEventCount": 3, "analysisEventCount": 3,
            "observedEventsTruncated": True,
            "historySourceIntegrityVerified": False,
        },
    })
    src[2]["arguments"]["args"]["deviceId"] = target
    return src


def test_declared_partial_history_allows_no_cause_early_answer_after_checkpoint():
    for label, target in (
        ("Test Relay", "9911"),
        ("Heating Controller", "9922"),
        ("Ventilation Plug", "9933"),
    ):
        src = counted_partial_evidence(label, target)
        question = f"Why is {label} offline?"
        assert not ready(src, question=question, checkpoint=False)
        assert ready(src, question=question, checkpoint=True)
        assert not ready(src, question=question, domain="heating", checkpoint=True)
        assert not ready(src, question=f"Compare {label} with every device", checkpoint=True)
        assert not ready(src[:-2], question=question, checkpoint=True)


def test_partial_history_missing_row_proof_or_target_identity_never_stops():
    from copy import deepcopy

    base = counted_partial_evidence()
    edits = (
        lambda s: s[3]["details"].pop("sourceEventCount"),
        lambda s: s[3]["details"].__setitem__("sourceEventCount", 4),
        lambda s: s[3]["details"].__setitem__("analysisEventCount", 4),
        lambda s: s[3]["details"].__setitem__("observedEventsTruncated", False),
        lambda s: s[3]["details"].__setitem__("historySourceIntegrityVerified", True),
        lambda s: s[3]["details"].__setitem__("hoursBack", 48),
        lambda s: s[3]["details"].__setitem__("label", "Wrong Plug"),
        lambda s: s[3].__setitem__("timestamp", "2026-11-03T07:11:20+00:00"),
        lambda s: s[0]["details"]["reportedDeviceState"].__setitem__(
            "deviceId", "9999"),
        lambda s: s[2]["arguments"]["args"].__setitem__(
            "deviceId", "9999"),
    )
    for edit in edits:
        src = deepcopy(base)
        edit(src)
        assert not ready(src, checkpoint=True)
