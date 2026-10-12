"""0.17.38 regression: a history question cannot be consumed as app status.

These scenarios reproduce HomeBrain's 0.17.37 live output: zero model rounds,
eight current-state reads, all historical obligations 'not-checked'.
The production Rule Machine snapshot shortcut must not intercept this goal.
"""
from __future__ import annotations

from investigation_intelligence import plan_investigation, assess_investigation
from rule_machine_analysis import parse_rule_analysis_request
from motion_lockout_investigation import (
    is_motion_lockout_investigation, resolve_named_light,
)


LOCKOUT_REQUEST = (
    "Investigate the latest manual OFF of Livingroom Light 1 followed by motion. "
    "Determine whether app 4019's three-minute motion lockout actually engaged. "
    "Reconstruct the event sequence and distinguish configuration from "
    "verified historical execution. Read-only."
)


def test_history_lockout_request_bypasses_configuration_only_rule_shortcut():
    plan = plan_investigation(LOCKOUT_REQUEST)
    assert plan is not None and plan.domain == "manual_motion_lockout"
    assert parse_rule_analysis_request(LOCKOUT_REQUEST) is None
    assert is_motion_lockout_investigation(LOCKOUT_REQUEST)
    assert parse_rule_analysis_request(
        "Inspect current configuration and referenced sensor health of app 4019."
    ) == ("4019", None)


def test_rule_snapshot_cannot_steal_generic_past_transition_investigation():
    request = (
        "Investigate why app 4019 triggered after yesterday's light OFF event. "
        "Correlate actual logs and historic motion readings."
    )
    assert parse_rule_analysis_request(request) is None
    assert parse_rule_analysis_request(
        "Review app 4019 current settings and sensor health."
    ) == ("4019", None)


def test_dynamic_light_display_suffix_resolves_to_single_stable_identity():
    light = {
        "id": "4010",
        "name": "Livingroom Light 1",
        "label": "Livingroom Light 1 (💡 Lights On, 🏃 Motion Active)",
        "capabilities": ["Switch"],
    }
    found = resolve_named_light(LOCKOUT_REQUEST, [light])
    assert found and found["id"] == "4010"


def test_duplicate_stable_aliases_fail_closed_not_wrong_light():
    a = {"id": "4010", "name": "Livingroom Light 1",
         "label": "Livingroom Light 1 (Lights On)",
         "capabilities": ["Switch"]}
    b = {"id": "4011", "name": "Livingroom Light 1",
         "label": "Livingroom Light 1 (Lights Off)",
         "capabilities": ["Switch"]}
    assert resolve_named_light(LOCKOUT_REQUEST, [a, b]) is None


def test_local_device_history_is_a_first_class_coverage_source():
    goal = plan_investigation(
        "Diagnose whether Bedroom 3 Mesh device 7103 has stale MQTT telemetry."
    )
    assert goal is not None and goal.domain == "device_telemetry"
    rows = [
        {"tool": "hub_manage_devices", "sub_tool": "hub_get_device",
         "success": True, "arguments": {"tool": "hub_get_device",
                                         "args": {"deviceId": "7103"}}},
        {"tool": "homebrain_device_history", "sub_tool": None,
         "success": True, "arguments": {"name": "Bedroom 3 Mesh"},
         "details": {"observedEvents": [
             {"name": "dataAgeSeconds", "value": "74856",
              "date": "2026-10-12T22:17:38+01:00"},
             {"name": "dataAgeSeconds", "value": "74556",
              "date": "2026-10-12T22:12:38+01:00"},
             {"name": "deviceHealth", "value": "stale",
              "date": "2026-10-12T02:27:49+01:00"},
         ]}},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "arguments": {"tool": "hub_get_logs",
             "args": {"deviceId": "7103", "since": "24h"}},
         "details": {"logs": [
             {"message": "dev|7103|Bedroom 3 Mesh|Watchdog fired"}
         ]}},
    ]
    result = assess_investigation(goal, rows)
    states = {x["key"]: x["state"] for x in result["requirements"]}
    assert states["status"] == "observed"
    assert states["freshness"] == "observed"
    assert states["watchdog"] == "observed"
    assert states["command_path"] == "not-checked"
    assert result["evidenceComplete"]
