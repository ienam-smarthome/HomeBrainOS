"""Offline cross-source event reconciliation for one uniquely identified target.

Synthetic representative native + deterministic data; no live Hubitat calls.
A late narrow command-on read must not erase earlier scoped command-off.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))
from focal_event_reconciliation import (
    reconcile_focal_device_events, render_focal_device_evidence,
)


QUESTION = (
    "Investigate the most recent complete ON-to-OFF cycle of Test Load 1. "
    "Which automation issued each command, and when did it use power?"
)


def fixture():
    state = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "evidence_kind": "targeted_device_lookup",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_devices", "args": {
            "labelFilter": "Test Load 1", "detailed": True,
        }},
        "details": {"reportedDeviceState": {
            "label": "Test Load 1", "deviceId": "5313",
            "reportedAttributes": {"switch": "off"},
        }},
    }
    switch = {
        "tool": "homebrain_device_history", "success": True,
        "effect": "read", "mutates": False,
        "arguments": {"name": "Test Load 1", "attribute": "switch"},
        "details": {"label": "Test Load 1", "observedEvents": [
            {"name": "switch", "value": "off",
             "date": "2026-11-01T18:07:35.273Z"},
            {"name": "switch", "value": "on",
             "date": "2026-11-01T16:31:23.288Z"},
        ]},
    }
    all_events = {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events", "success": True,
        "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": "5313",
                               "since": "2026-11-01T16:00:00Z",
                               "until": "2026-11-01T19:00:00Z"}},
        "details": {"observedEventsTruncated": True, "observedEvents": [
            {"name": "power", "value": "0", "date": "2026-11-01T18:07:06.633Z"},
            {"name": "power", "value": "88", "date": "2026-11-01T18:07:08.127Z"},
            {"name": "command-off", "type": "command",
             "date": "2026-11-01T18:07:35.001Z",
             "producedBy": {"appId": 3995, "name": "Test Controller"}},
            {"name": "switch", "value": "off", "date": "2026-11-01T18:07:35.273Z"},
            {"name": "power", "value": "81", "date": "2026-11-01T18:07:36.137Z"},
            {"name": "power", "value": "0", "date": "2026-11-01T18:07:38.130Z"},
        ]},
    }
    late_command = {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events", "success": True,
        "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "5313", "attribute": "command-on",
            "hoursBack": 24,
        }},
        "details": {"events": [
            {"name": "command-on", "type": "command",
             "date": "2026-11-01T16:31:23.210Z",
             "producedBy": {"type": "app", "id": 3995}},
        ]},
    }
    return [state, switch, all_events, late_command]


def test_reconciles_earlier_off_despite_later_narrow_on_only_read():
    facts = reconcile_focal_device_events(QUESTION, fixture())
    assert facts["deviceId"] == "5313"
    assert facts["deviceLabel"] == "Test Load 1"
    assert facts["truncatedSourceObserved"] is True
    assert facts["sourceHistoryComplete"] is False
    assert facts["latestCompleteReportedSwitchInterval"][
        "reportedOnDurationSeconds"
    ] == 5771.985
    commands = facts["attestedCommands"]
    assert len(commands) == 2  # Mixed-history OFF and filtered-page ON both count
    assert {row["name"] for row in commands} == {"command-on", "command-off"}
    assert all(row["issuerAppId"] == "3995" for row in commands)
    assert facts["reportedPowerSamples"][1]["value"] == "88.0"
    assert facts["reportedPowerSamples"][-1]["value"] == "0.0"
    assert facts["physicalPlantOperationVerified"] is False
    packet = render_focal_device_evidence(QUESTION, fixture())
    assert '"command-off"' in packet
    assert "earliest returned nonzero sample" in packet
    assert "cannot negate earlier" in packet


def test_commands_can_be_present_as_native_observed_events_both_directions():
    rows = fixture()
    rows[2]["details"]["observedEvents"].insert(0, {
        "name": "command-on", "type": "command",
        "date": "2026-11-01T16:31:23.210Z",
        "producedBy": {"type": "app", "id": 3995},
    })
    facts = reconcile_focal_device_events(QUESTION, rows)
    assert {x["name"] for x in facts["attestedCommands"]} == {
        "command-on", "command-off",
    }
    assert all(x["issuerAppId"] == "3995" for x in facts["attestedCommands"])


def test_wrong_target_ambiguous_target_or_failed_sources_fail_closed():
    data = fixture()
    assert reconcile_focal_device_events(QUESTION, data)[
        "latestCompleteReportedSwitchInterval"
    ]
    rows = fixture()
    rows[0]["success"] = False
    assert reconcile_focal_device_events(QUESTION, rows) is None
    rows = fixture()
    rows[0]["details"]["reportedDeviceState"]["deviceId"] = "9999"
    assert reconcile_focal_device_events(QUESTION, rows) is None
    rows = fixture()
    rows.append({**rows[0], "details": {"reportedDeviceState": {
        "deviceId": "7722", "label": "Test Load 1",
    }}})
    assert reconcile_focal_device_events(QUESTION, rows) is None
    rows = fixture()
    rows[2]["success"] = False
    facts = reconcile_focal_device_events(QUESTION, rows)
    assert facts is not None and facts["attestedCommands"] == []
    rows = fixture()
    rows[2]["arguments"]["args"]["deviceId"] = "9999"
    assert reconcile_focal_device_events(QUESTION, rows)[
        "attestedCommands"
    ] == []


def test_source_integrity_clock_and_actor_types_matter():
    rows = fixture()
    for event in rows[2]["details"]["observedEvents"]:
        if event["name"] == "command-off":
            event["producedBy"] = {"id": 3995, "name": "Test App"}
    facts = reconcile_focal_device_events(QUESTION, rows)
    assert next(x for x in facts["attestedCommands"]
                if x["name"] == "command-off")["issuerAppId"] is None
    rows = fixture()
    rows[2]["details"]["observedEvents"][2]["type"] = "state"
    assert all(x["name"] != "command-off" for x in
               reconcile_focal_device_events(QUESTION, rows)["attestedCommands"])
    rows = fixture()
    rows[2]["details"]["observedEvents"][2]["date"] = "2026-11-01T18:07:35"
    assert reconcile_focal_device_events(QUESTION, rows)["attestedCommands"] == []
    rows = fixture()
    assert reconcile_focal_device_events(
        "Investigate why Other Test Load 1 turned off", rows
    ) is None


def test_power_sample_and_reported_switch_interval_are_distinct_claims():
    rows = fixture()
    facts = reconcile_focal_device_events(QUESTION, rows)
    assert len(facts["reportedPowerSamples"]) == 4
    assert facts["latestCompleteReportedSwitchInterval"][
        "physicalOperatingDurationVerified"
    ] is False
    assert "Power samples are discrete" in facts["negativeClaimGuidance"]
