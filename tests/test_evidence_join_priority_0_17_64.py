"""Cross-receipt identity joins and topology-first historical sensor planning."""
from __future__ import annotations

from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from typed_device_history_evidence import normalize_target_device_history
from causal_sensor_candidate_priority import prioritize_focal_sensor_candidates
from mcp_agent_orchestrator import AgentOutcome
from shared_investigation_completion import apply_shared_investigation_completion


def paired_evidence():
    rows = [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices", "args": {
                "labelFilter": "Example Mesh"
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "timestamp": "2026-10-15T10:28:28.234220+00:00",
            "summary": "3 device events for 'Example Mesh'",
            "arguments": {"tool": "hub_list_device_events", "args": {
                "deviceId": "7103", "hoursBack": 24, "limit": 20,
            }},
        },
        {
            "tool": "homebrain_device_history",
            "success": True,
            "timestamp": "2026-10-15T10:28:28.236525+00:00",
            "details": {
                "label": "Example Mesh",
                "hoursBack": 24,
                "observedEventsTruncated": False,
                "historySourceIntegrityVerified": False,
                "observedEvents": [
                    {
                        "name": "command-on",
                        "type": "command",
                        "date": "2026-10-15T10:10:00+0100",
                        "producedBy": {
                            "label": "Button Automation", "type": "app",
                        },
                    },
                    {
                        "name": "command-refresh",
                        "type": "command",
                        "date": "2026-10-15T06:00:00+0100",
                        "producedBy": {
                            "label": "Device Monitor", "type": "app",
                        },
                    },
                    {
                        "name": "mqttStatus", "value": "connected",
                        "date": "2026-10-13T22:35:38+0100",
                        "producedBy": {
                            "label": "Example Mesh", "deviceId": "7103",
                        },
                    },
                ],
            },
        },
    ]
    return rows


def test_direct_and_derived_receipts_join_to_one_mixed_history():
    receipt = normalize_target_device_history(paired_evidence())
    assert receipt is not None
    assert receipt["deviceId"] == "7103"
    assert receipt["joinedDerivedHistory"] is True
    assert receipt["eventSource"] == "verified-direct-derived-receipt-pair"
    assert receipt["commandCount"] == 2
    assert receipt["stateEventCount"] == 1
    assert receipt["latestReturnedStateEvent"]["attribute"] == "mqttStatus"
    assert receipt["sourceIntegrityVerified"] is False
    assert receipt["physicalCommunicationVerified"] is False


def test_no_join_across_mismatched_identity_time_count_or_window():
    rows = paired_evidence()
    rows[2]["details"]["label"] = "Another Mesh"
    assert normalize_target_device_history(rows) is None

    rows = paired_evidence()
    rows[1]["summary"] = "4 device events for 'Example Mesh'"
    assert normalize_target_device_history(rows) is None

    rows = paired_evidence()
    rows[2]["timestamp"] = "2026-10-15T10:29:28.236525+00:00"
    assert normalize_target_device_history(rows) is None

    rows = paired_evidence()
    rows[2]["details"]["hoursBack"] = 168
    assert normalize_target_device_history(rows) is None

    rows = paired_evidence()
    rows[2]["success"] = False
    assert normalize_target_device_history(rows) is None


def test_joined_history_at_shared_gate_replaces_unverified_cause():
    rows = paired_evidence()
    outcome = AgentOutcome(
        message="The hardware definitely failed to execute its commands.",
        evidence=rows, choices=[], request_class="live-read",
    )
    assessed = apply_shared_investigation_completion(
        outcome,
        "Investigate Example Mesh current health and last telemetry "
        "activity. Compare its commands, state history and device logs. Read-only.",
    )
    assert assessed.investigation_coverage["normalizedDeviceHistory"][
        "joinedDerivedHistory"
    ] is True
    assert "definitely failed" not in assessed.message
    assert assessed.metrics["outcome"] == "unresolved"


def _spec(identifier, label, *, room="Lounge", attribute="motion"):
    return {
        "name": label, "attribute": attribute,
        "candidate": {"id": str(identifier), "label": label, "room": room},
    }


def _inventory(identifier, label, *, room="Integration"):
    return {
        "id": str(identifier), "label": label, "room": room,
        "capabilities": ["MotionSensor"],
        "attributes": {"motion": "inactive"},
    }


def test_configured_sensor_outside_room_outranks_unrelated_room_sources():
    configured = "External configured motion sensor"
    automations = [{
        "name": "Configured scene",
        "actions": [{"device": "Lounge Light", "transition": "on"}],
        "triggers": [{"device": configured}],
    }]
    selected, plan = prioritize_focal_sensor_candidates(
        [_spec("11", "Room Presence One", attribute="presence"),
         _spec("12", "Room Presence Two", attribute="presence")],
        [_inventory("99", configured)],
        automations,
        subject="Lounge Light", subject_room="Lounge",
        transition="on", limit=2,
    )
    assert selected[0]["candidate"]["id"] == "99"
    assert plan["topologyUsed"] is True
    assert plan["configuredCandidatesSelected"] == 1
    assert len(selected) == 2
    assert plan["historicalEventsVerified"] is False


def test_unlinked_cross_room_sensor_not_added_and_ordinary_room_plan_unchanged():
    room = [_spec("11", "Room Sensor One"),
            _spec("12", "Room Sensor Two")]
    selected, plan = prioritize_focal_sensor_candidates(
        room, [_inventory("99", "Unrelated outside sensor")],
        [{"actions": [{"device": "Another Light", "transition": "on"}],
          "triggers": [{"device": "Unrelated outside sensor"}]}],
        subject="Lounge Light", subject_room="Lounge",
        transition="on", limit=2,
    )
    assert [r["candidate"]["id"] for r in selected] == ["11", "12"]
    assert plan["configuredCandidatesSelected"] == 0


def test_sensor_planner_does_not_take_unidentified_or_non_occupancy_candidates():
    selected, plan = prioritize_focal_sensor_candidates(
        [_spec("11", "Room Sensor One")],
        [{"id": "99", "label": "Other Source", "room": "Lounge",
          "capabilities": ["TemperatureMeasurement"],
          "attributes": {"temperature": 20}}],
        [{"actions": [{"device": "Lounge Light", "transition": "on"}],
          "triggers": [{"device": "Other Source"}]}],
        subject="Lounge Light", subject_room="Lounge",
        transition="on",
    )
    assert [r["candidate"]["id"] for r in selected] == ["11"]
    assert plan["historicalEventsVerified"] is False
