"""v0.18.153: read-only light answers remain useful when model planning hangs.

Synthetic Hue-device read-time status and device event histories only.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPToolResult
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.synthesis import assemble_grounded_answer


def make_case():
    device = "7828"
    current_args = {"tool": "hub_get_device", "args": {"deviceId": device}}
    status = project_read_receipt(
        "hub_read_devices", current_args,
        MCPToolResult("hub_read_devices", current_args, raw={}, text="",
                      data={"id": device, "attributes": {
                          "switch": "on", "networkStatus": "online",
                          "brokerPassword": "SHOULD_NOT_RENDER"}},
                      is_error=False),
        source_request_id="light-snapshot")
    events = []
    for idx, (clock, switch) in enumerate([
        ("2026-10-25T16:33:02+00:00", "off"),
        ("2026-10-25T16:33:23+00:00", "on"),
        ("2026-10-25T16:34:11+00:00", "off"),
        ("2026-10-25T21:05:36+00:00", "on"),
        ("2026-10-25T21:12:13+00:00", "on"),
        ("2026-10-26T00:08:35+00:00", "off"),
        ("2026-10-26T11:17:49+00:00", "on"),
        ("2026-10-26T11:17:54+00:00", "off"),
        ("2026-10-26T21:59:01+00:00", "on"),
        ("2026-10-26T21:59:08+00:00", "off"),
        ("2026-10-26T21:59:17+00:00", "on"),
    ]):
        events.append({"deviceId": device, "name": "switch",
                       "value": switch, "date": clock,
                       "producedBy": {"id": "7790"}})
    history_args = {"tool": "hub_list_device_events",
                    "args": {"deviceId": device, "attribute": "switch",
                             "hoursBack": 168, "limit": 50}}
    history = project_read_receipt(
        "hub_read_devices", history_args,
        MCPToolResult("hub_read_devices", history_args, raw={}, text="",
                      data={"deviceId": device, "events": events},
                      is_error=False),
        source_request_id="light-history")
    case = build_case_file("Investigate Livingroom Light 2", [status, history])
    assert len(case.records) == 11
    assert len(case.device_snapshots) == 1
    return case


def test_current_light_state_uses_snapshot_and_never_adds_mqtt_device_warning():
    case = make_case()
    report = format_investigation_report(case, [], "planning_timeout")
    assert "**Current reported status:** switch=on, networkStatus=online" in report
    assert "**Latest switch report:** on at 26 Oct 21:59:17 UTC" in report
    assert "reporting source, not necessarily" in report
    assert "An MQTT client reporting connected" not in report
    assert "SHOULD_NOT_RENDER" not in report


def test_compact_light_timeline_keeps_most_recent_three_switch_transitions():
    report = format_investigation_report(make_case(), [], "planning_timeout")
    for time in ("26 Oct 21:59:01 UTC", "26 Oct 21:59:08 UTC",
                 "26 Oct 21:59:17 UTC"):
        assert time in report
    assert "No issued command supports" in report
    assert "planning timeout" in report


def test_grounded_answer_includes_network_and_omits_unrelated_transport_claim():
    case = make_case()
    answer = assemble_grounded_answer(
        case, [], {"selected_record_ids": [r.record_id for r in case.records],
                   "hypothesis_order": []})
    assert "switch=on" in answer.text
    assert "networkStatus=online" in answer.text
    assert "MQTT client" not in answer.text
    assert "Reported power/energy values may be stale" not in answer.text
    assert "SHOULD_NOT_RENDER" not in answer.text


def test_v2_endpoint_has_host_bounded_optional_planning():
    route = (APP / "app.py").read_text().split("async def v2_test(",1)[1]
    route = route.split('@app.post("/api/chat")',1)[0]
    assert "planning_timeout_seconds=(35.0 if factual_objective is None else 15.0)" in route
    assert "model_intent_planning_skipped" in route
    assert "bootstrap_device_context=True" in route
    assert "enable_atomic_claim_validation=True" in route
