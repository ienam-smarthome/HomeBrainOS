"""v0.18.151 — source-clock coverage and useful timeline excerpts.

Synthetic fixtures only; no Hubitat, model, or network calls.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.evidence import build_case_file
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.receipt_projection import project_read_receipt
from mcp_client import MCPToolResult


def case_with_contact_gap():
    target = "7103"
    device_args = {"tool": "hub_get_device", "args": {"deviceId": target}}
    status = project_read_receipt(
        "hub_read_devices", device_args,
        MCPToolResult("hub_read_devices", device_args, raw={}, text="",
                      data={"id": target, "attributes": {
                          "healthStatus": "offline", "deviceHealth": "unknown",
                          "mqttStatus": "connected",
                          "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
                          "switch": "off", "power": 8,
                          "brokerPassword": "HIDDEN_CREDENTIAL"}},
                      is_error=False),
        source_request_id="status",
    )
    events = []
    for time, value in [
        ("2026-10-22T21:10:25+00:00", "disconnected"),
        ("2026-10-22T21:10:30+00:00", "connected"),
        ("2026-10-23T18:48:37+00:00", "disconnected"),
        ("2026-10-23T18:48:42+00:00", "connected"),
        ("2026-10-25T00:20:21+01:00", "disconnected"),
        ("2026-10-25T00:20:27+01:00", "connected"),
    ]:
        events.append({"deviceId": target, "name": "mqttStatus",
                       "value": value, "date": time})
    events.append({
        "deviceId": target, "name": "command-on", "type": "command",
        "date": "2026-10-24T21:51:12+01:00",
        "producedBy": {"id": "3103"},
    })
    t = datetime(2026,10,26,20,54,tzinfo=timezone.utc)
    for i in range(12):
        events.append({"deviceId": target, "name": "deviceHealth",
                       "value": "stale" if i % 2 == 0 else "unknown",
                       "date": (t + timedelta(minutes=i*2)).isoformat()})
    history_args = {"tool": "hub_list_device_events",
                    "args": {"deviceId": target, "hoursBack": 381, "limit": 50}}
    history = project_read_receipt(
        "hub_read_devices", history_args,
        MCPToolResult("hub_read_devices", history_args, raw={}, text="",
                      data={"deviceId": target, "events": events}, is_error=False),
        source_request_id="history",
    )
    case = build_case_file("Why did Bedroom 3 Mesh go offline?", [status, history])
    assert len(case.records) == 19
    assert len(case.device_snapshots) == 1
    return case


def test_report_preserves_mqtt_sequence_and_command_not_just_one_row():
    report = format_investigation_report(case_with_contact_gap(), [], "model_finished")
    assert "on() issued" in report
    assert "mqttStatus = disconnected reported" in report
    assert "mqttStatus = connected reported" in report
    assert "24 Oct 20:51:12 UTC" in report
    assert "| UTC time | Observation | Source |" in report
    assert "| Local time |" not in report
    assert "Times above are UTC" in report
    assert "12 deviceHealth observations alternated" in report
    assert "19 additional observations" not in report
    assert "HIDDEN_CREDENTIAL" not in report


def test_lastseen_earlier_than_source_events_is_coverage_gap_not_causal_claim():
    report = format_investigation_report(case_with_contact_gap(), [],
                                         "semantic_intent_unavailable")
    assert "**History gap:**" in report
    assert "Mon Oct 12 01:30:01 BST 2026" in report
    assert "22 Oct 21:10:25 UTC" in report
    assert "intervening history" in report
    assert "physical failure cause" in report
    assert "historical source is not independently proven complete" in report


def test_invalid_lastseen_never_generates_a_gap_or_historical_event():
    case = case_with_contact_gap()
    case.device_snapshots[-1]["attributes"]["lastSeen"] = "unparseable"
    report = format_investigation_report(case, [], "model_finished")
    assert "**History gap:**" not in report
    assert len(case.records) == 19
