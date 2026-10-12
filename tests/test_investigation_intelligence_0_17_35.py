"""Investigation-quality contracts across independent HomeBrain domains.

Every scenario is based on actual 0.17.34 live traces, not an individual
automation's name. The contract separates source retrieval from observations
and never upgrades guesses to verified provenance.
"""
from __future__ import annotations

import json

from investigation_intelligence import (
    plan_investigation, assess_investigation,
    render_investigation_plan, render_investigation_assessment,
)


def _read(tool, args=None, *, details=None, success=True):
    return {"tool": "hub_read_devices", "sub_tool": tool,
            "arguments": {"tool": tool, "args": args or {}},
            "success": success, "details": details or {}}


def test_manual_lockout_configuration_and_live_health_not_historical_proof():
    p = plan_investigation(
        "Investigate the latest manual OFF followed by motion: did the "
        "Livingroom Light 1 three-minute motion lockout engage? Read-only."
    )
    assert p is not None and p.domain == "manual_motion_lockout"
    receipts = [
        _read("hub_get_app_config", {"appId": "4019"}),
        _read("hub_get_device", {"deviceId": "7764"},
              details={"attributes": {"motion": "active"}}),
        _read("hub_get_device", {"deviceId": "7986"}),
    ]
    v = assess_investigation(p, receipts)
    assert v["status"] == "not-established"
    assert not v["evidenceComplete"]
    assert all(x["state"] == "not-checked" for x in v["requirements"])
    assert len(v["nextMissingSources"]) == 4
    assert "historic OFF event" in render_investigation_plan(p)


def test_history_pages_without_off_or_lockout_do_not_complete_investigation():
    p = plan_investigation(
        "Investigate manual-off motion lockout for hallway light"
    )
    assert p is not None
    events = _read("hub_list_device_events", {"deviceId": "123"},
                   details={"events": [
                       {"name": "motion", "value": "active",
                        "date": "2026-10-12T20:00:00+01:00"}
                   ]})
    logs = _read("hub_get_logs", {"appId": "4019"},
                 details={"logs": []})
    a = assess_investigation(p, [events, logs])
    states = {x["key"]: x["state"] for x in a["requirements"]}
    assert states["target_off"] == "checked-unverified"
    assert states["controller"] == "checked-unverified"
    assert states["motion"] == "observed"
    assert states["execution"] == "checked-unverified"
    assert not a["evidenceComplete"]


def test_device_health_separates_stale_telemetry_from_command_reachability():
    p = plan_investigation(
        "Diagnose whether Bedroom 3 Mesh is offline or MQTT telemetry stale"
    )
    assert p is not None and p.domain == "device_telemetry"
    rows = [
        _read("hub_get_device", {"deviceId": "7103"},
              details={"attributes": {"mqttStatus": "connected",
                                      "healthStatus": "offline"}}),
        _read("hub_list_device_events", {"deviceId": "7103"},
              details={"events": [
                  {"name": "dataAgeSeconds", "value": "70056"},
                  {"name": "deviceHealth", "value": "stale"},
              ]}),
        _read("hub_get_logs", {"deviceId": "7103"},
              details={"logs": [
                  {"message": "Watchdog reconnecting after 70000s"}
              ]}),
        _read("hub_get_logs", {"since": "30m"}, details={"logs": [
            {"message": "unrelated TV power logs"}
        ]}),
    ]
    v = assess_investigation(p, rows)
    found = {x["key"]: x["state"] for x in v["requirements"]}
    assert found["status"] == "observed"
    assert found["freshness"] == "observed"
    assert found["watchdog"] == "observed"
    assert found["command_path"] == "not-checked"
    assert any("cannot receive commands" in x
               for x in p.forbidden_inferences)
    assert "not prov" not in v["status"]  # completion is evidence-based, not a claim


def test_scheduler_keys_are_not_authoritative_owner_ids():
    p = plan_investigation(
        "Analyse all scheduled jobs by owning app and handler and recommend "
        "safe efficiency improvements"
    )
    assert p is not None and p.domain == "scheduler_ownership"
    r = _read("hub_get_jobs", details={"scheduledJobs": [
        {"id": "app-4019-motion", "method": "motionStaleCheckHandler",
         "name": "app:4019", "nextRun": "2026-10-12T21:00:00Z"},
        {"id": "dev-7103-watchdog", "method": "watchdogCheck",
         "name": "device:7103", "nextRun": "2026-10-12T21:01:00Z"},
    ]})
    v = assess_investigation(p, [r, _read("hub_get_performance_stats")])
    x = {z["key"]: z["state"] for z in v["requirements"]}
    assert x["jobs"] == "observed"
    assert x["owners"] == "checked-unverified"
    assert not v["evidenceComplete"]
    assert "owner fields" in v["nextMissingSources"][0]
    assert "candidate ID prefixes" in p.stop_rule


def test_actual_scheduler_owner_fields_are_distinguished_from_prefixes():
    p = plan_investigation(
        "Analyse scheduled job ownership and handler workload"
    )
    r = _read("hub_get_jobs", details={"scheduledJobs": [
        {"appId": "4019", "method": "refresh"},
        {"name": "device:7103", "method": "watchdog"},
    ]})
    z = assess_investigation(p, [r])
    owners = next(x for x in z["requirements"] if x["key"] == "owners")
    assert owners["state"] == "observed"


def test_rendered_assessment_is_structured_no_private_tool_payload():
    p = plan_investigation(
        "Diagnose if Bedroom 3 Mesh MQTT device is offline"
    )
    raw = render_investigation_assessment(p, [
        _read("hub_get_logs", {"deviceId": "7103"},
              details={"logs": [{"message": "PRIVATE_TOKEN_DO_NOT_ECHO"}]})
    ])
    assert "PRIVATE_TOKEN_DO_NOT_ECHO" not in raw
    assert "HOST EVIDENCE SUFFICIENCY ASSESSMENT" in raw
    data = json.loads(raw.splitlines()[1])
    assert data["status"] == "partial-evidence"
    assert data["requirements"][0]["state"] == "not-checked"


def test_normal_requests_are_not_hijacked_by_investigation_plans():
    for question in (
        "Turn off Livingroom Light 1",
        "Show me all current lights",
        "Is the hall temperature 22 degrees?",
        "List active rules",
    ):
        assert plan_investigation(question) is None
