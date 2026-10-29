"""Regression for the 2026-10-29 Google Nest Hub V2 live trace.

Five separate generic WARN records must not become 68 minutes of continuous
load. Gateway errors must not grant a new READ or invent driver identity.
"""
from __future__ import annotations
import sys
from pathlib import Path
APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, evidence_safe_incident_explanation)
from investigation_v2.native_evidence_coverage import gap_for_target
from investigation_v2.native_read_agent import (
    _read_manifest, _verified_gateways_for_operation, _guard)
from investigation_v2.native_source_followup import source_path_followup


def logs():
    return {"total": 10, "entries": [
        {"level": "WARN", "type": "dev", "name": "Google Nest Hub",
         "message": "dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
         "time": at}
        for at in (
            "2026-10-28 19:55:19.194",
            "2026-10-28 20:01:37.123",
            "2026-10-28 23:32:11.200",
            "2026-10-29 00:37:52.500",
            "2026-10-29 01:03:20.292",
        )
    ]}


def receipts():
    history = {"events": [
        {"name": "volume", "value": "10",
         "date": "2026-10-29T01:03:20.292+0000",
         "producedBy": {"deviceId": "7934"}},
        {"name": "volume", "value": "15",
         "date": "2026-10-29T01:03:19.220+0000",
         "producedBy": {"deviceId": "7934"}},
        {"name": "status", "value": "buffering",
         "date": "2026-10-28T19:55:19.193+0000",
         "producedBy": {"deviceId": "7934"}},
    ]}
    return [
        {"read": 2, "operation": "hub_get_logs",
         "read_filters": {"deviceId": "7934", "level": "warn"},
         "source_data": {"log_summary": compact_logs(logs())}},
        {"read": 3, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7934"},
         "source_data": {"issuer_apps": [], "count": 3,
                         "events": history["events"]}},
        {"read": 5, "operation": "hub_get_device",
         "read_filters": {"deviceId": "7934", "mode": "configuration"},
         "source_data": {"device_mode": "configuration",
                         "device_identity": {"version": 1},
                         "driver_source_metadata": {"status": "unavailable"}}},
    ]


def test_grouped_warns_retains_individual_occurrences_and_not_full_continuity():
    g = compact_logs(logs())["warning_error_groups"][0]
    assert g["count"] == 5
    assert g["oldest_returned"] == "2026-10-28 19:55:19.194"
    assert g["newest_returned"] == "2026-10-29 01:03:20.292"
    assert len(g["sample_timestamps"]) == 5
    assert g["sample_timestamps_capped"] is False


def test_incident_packet_checks_latest_warning_not_all_68_hours_or_minutes():
    packet = incident_attribution_packet(receipts(), ["7934"])
    assert packet is not None
    assert packet["warning_occurrence_selected"] == "2026-10-29T01:03:20.292000"
    assert packet["warning_period"]["oldest"] == packet["warning_period"]["newest"]
    assert packet["warning_group_sample"]["sampled_rows"] == 5
    assert packet["app_commands_within_warning_interval"] == 0
    assert packet["app_commands_within_five_minutes"] == 0
    assert len(packet["device_events_within_two_seconds"]) == 2
    answer = evidence_safe_incident_explanation(packet)
    assert "one observed warning timestamp" in answer
    assert "not evidence of continuous load" in answer
    assert "volume=10" in answer and "volume=15" in answer
    assert "No calling app is independently identified in this" in answer


def test_causal_coverage_proposes_latest_occurrence_not_broad_group_span():
    gap = gap_for_target(receipts(), ["7934"], can_read_events=True)
    assert gap["warning_window"]["oldest"].startswith("2026-10-29T01:03:20")
    assert gap["warning_window"]["newest"] == gap["warning_window"]["oldest"]
    assert gap["kind"] == "target_warning_command_issuer_unverified"


def test_source_unavailable_becomes_explicit_blocker_no_guessed_code_id():
    item = source_path_followup(receipts(), ["7934"], set())
    assert item["status"] == "driver_source_unavailable_no_attested_id"
    assert item["evidence_read"] == 5
    assert "no independently attested driver code ID" in item["limits"]
    assert "model_chosen_read" not in item


def tool(name, ops, *, read=True):
    return MCPTool(name, "Test MCP gateway", {
        "type": "object", "properties": {
            "tool": {"type": "string", "enum": ops},
            "args": {"type": "object", "additionalProperties": True}
        }, "required": ["tool", "args"],
    }, annotations={"readOnlyHint": read})


def test_gateway_repair_only_offers_live_read_authorised_mapping():
    manifest = _read_manifest([
        tool("hub_read_diagnostics", ["hub_get_logs"]),
        tool("hub_read_devices", ["hub_list_device_events"]),
        tool("hub_manage_logs", ["hub_list_device_events"], read=False),
    ])
    assert _verified_gateways_for_operation(
        "hub_list_device_events", {"deviceId": "7934"}, manifest, {}
    ) == ["hub_read_devices"]
    assert _guard("hub_read_diagnostics", {
        "tool": "hub_list_device_events", "args": {"deviceId": "7934"}
    }, manifest, {}, {"7934"}, {
        "device": {"7934"}, "app": set(), "driver": set()
    }) == "operation_not_independently_discovered"
    assert _guard("hub_read_devices", {
        "tool": "hub_list_device_events", "args": {"deviceId": "7934"}
    }, manifest, {}, {"7934"}, {
        "device": {"7934"}, "app": set(), "driver": set()
    }) is None


def test_absent_individual_timestamps_preserve_explicit_legacy_limits():
    w = receipts()
    group = w[0]["source_data"]["log_summary"]["warning_error_groups"][0]
    del group["sample_timestamps"]
    packet = incident_attribution_packet(w, ["7934"])
    assert packet["warning_occurrence_selected"] is None
    assert packet["warning_period"]["oldest"] == "2026-10-28 19:55:19.194"
    assert packet["warning_period"]["newest"] == "2026-10-29 01:03:20.292"
