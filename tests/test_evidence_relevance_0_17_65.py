"""Live-response regressions: evidence quality, candidate exclusions, focal timing."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from causal_sensor_candidate_priority import prioritize_focal_sensor_candidates
from typed_device_history_evidence import (
    normalize_target_device_history, render_target_device_evidence_answer,
)
import mcp_agent_orchestrator as orchestrator
from mcp_agent_orchestrator import UnifiedMCPAgent


def _spec(number, label, attribute="motion"):
    return {
        "name": label, "attribute": attribute,
        "candidate": {"id": str(number), "label": label, "room": "Lounge"},
    }


def _sensor(number, label):
    return {
        "id": str(number), "label": label, "room": "Lounge",
        "capabilities": ["MotionSensor"], "attributes": {"motion": "inactive"},
    }


def test_no_configured_automation_explains_selection_gap_and_backup_devices():
    room = [
        _spec("101", "Room sensor alpha"),
        _spec("102", "Room sensor beta"),
        _spec("103", "Room sensor gamma"),
        _spec("104", "Room sensor delta"),
    ]
    selected, plan = prioritize_focal_sensor_candidates(
        room, [_sensor("105", "Room sensor epsilon")], [],
        subject="Lounge Light", subject_room="Lounge", transition="on",
        limit=4,
    )
    assert [r["candidate"]["id"] for r in selected] == [
        "101", "102", "103", "104",
    ]
    assert plan["configuredSelectionGap"] == "no-known-automations"
    assert plan["knownAutomationCount"] == 0
    assert plan["capabilityCheckedCandidateCount"] >= 4
    assert plan["historicalEventsVerified"] is False
    assert any(
        row["reason"] == "not-in-initial-probe-budget"
        for row in plan["candidateDisposition"]
        if row["id"] == "105"
    )


def test_configured_sensor_is_prioritized_but_not_claimed_as_event_cause():
    subject = "Lounge Light"
    automations = [{
        "name": "Lighting controller",
        "actions": [{"device": subject, "transition": "on"}],
        "triggers": [{"device": "Bridge occupancy 401"}],
    }]
    selected, plan = prioritize_focal_sensor_candidates(
        [_spec("101", "Room sensor alpha"),
         _spec("102", "Room sensor beta")],
        [_sensor("401", "Bridge occupancy 401")],
        automations, subject=subject, subject_room="Lounge",
        transition="on", limit=2,
    )
    assert selected[0]["candidate"]["id"] == "401"
    assert plan["configuredCandidatesSelected"] == 1
    assert plan["historicalEventsVerified"] is False


def test_device_reported_health_is_displayed_with_timestamp_and_caveat():
    events = [
        {"name": "command-refresh", "type": "command",
         "producedBy": {"name": "Watchdog", "appId": 4072}},
    ]
    evidence = [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": "Example Mesh"}},
            "details": {"reportedDeviceState": {
                "deviceId": "7103", "label": "Example Mesh",
                "observedAt": "2026-10-15T11:09:28+00:00",
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                    "switch": "off",
                },
                "source": "targeted-hubitat-device-state",
                "isPhysicalConnectivityProof": False,
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": "7103", "hoursBack": 24}},
            "details": {"observedEvents": events},
        },
    ]
    projected = normalize_target_device_history(evidence)
    assert projected is not None
    assert projected["reportedDeviceState"]["reportedAttributes"]["healthStatus"] == "offline"
    answer = render_target_device_evidence_answer(evidence, projected)
    assert "healthStatus=offline" in answer
    assert "mqttStatus=connected" in answer
    assert "11:09:28" in answer
    assert "not independently verified physical" in answer
    # Do not conflate driver-reported connected state and physical reachability.
    assert "currently connected" not in answer.lower()

    evidence[0]["details"]["reportedDeviceState"]["deviceId"] = "9999"
    no_join = normalize_target_device_history(evidence)
    assert no_join is not None
    assert no_join["reportedDeviceState"] is None


@pytest.mark.asyncio
async def test_historical_on_does_not_inspect_hours_later_off(monkeypatch):
    events = []
    fake = SimpleNamespace(
        evidence=SimpleNamespace(receipts=lambda: events),
    )
    monkeypatch.setattr(
        orchestrator, "focal_closed_transition",
        lambda *_a, **_k: {
            "end": "2026-10-14T22:45:40.112+0100",
            "deviceId": "7805",
        },
    )
    monkeypatch.setattr(
        orchestrator, "prompt_focal_transition_boundary",
        lambda *_a, **_k: "2026-10-14T19:55:00.049+0100",
    )
    monkeypatch.setattr(
        orchestrator, "has_explicit_focal_clock",
        lambda *_a, **_k: True,
    )
    await UnifiedMCPAgent._collect_focal_off_provenance(
        fake,
        user_prompt="Investigate why light turned ON at 19:55 on 14 October 2026",
        resolved_device_id="7805", requested_transition="on",
        catalog=SimpleNamespace(available_tool=lambda _name: (_ for _ in ()).throw(
            AssertionError("Later OFF must not initiate tools")
        )),
    )
