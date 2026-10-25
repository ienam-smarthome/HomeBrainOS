"""Phase A/B golden replay: no false claims AND no loss of useful commands."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from investigation_v2 import build_case_file

FIXTURE = Path(__file__).parent / "fixtures" / "investigation_v2_overnight.json"


def replay():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return build_case_file(fixture["question"], fixture["receipts"])


def test_golden_incident_keeps_every_command_and_reported_level():
    case = replay()
    assert len(case.records) == 8
    commands = [e for e in case.records if e.stage == "command_issued"]
    assert [(e.action, e.producer_id) for e in commands] == [
        ("command-on", "1251"), ("command-setLevel", "4019"),
        ("command-setLevel", "4019"), ("command-off", "4246"),
        ("command-setLevel", "4019"), ("command-off", "1251"),
    ]
    assert [(e.action, e.value) for e in case.records if e.stage == "state_reported"] == [
        ("level", "60"), ("level", "30")]
    assert all(e.target_id == "7805" for e in case.records)


def test_off_command_never_proves_off_state():
    case = replay()
    assert len([e for e in case.records if e.action == "command-off"]) == 2
    assert not any(e.action == "switch" and e.value == "off" for e in case.records)
    assert "Unverified: physical execution" in case.evidence_brief()
    assert "00:41:40.085" in case.evidence_brief()
    assert "00:49:52.008" in case.evidence_brief()
    assert "01:09:41.597" in case.evidence_brief()


def test_page_reach_does_not_upgrade_source_integrity():
    c = replay().coverage[0]
    assert c.page_reaches_start is True
    assert c.source_integrity_verified is False
    assert c.source_complete is False
    assert c.truncated is True
    assert c.requested_filters == {"hoursBack": 24, "limit": 50}


def test_uk_fallback_orders_absolute_instants_and_preserves_offsets():
    data = json.loads(FIXTURE.read_text())
    original = data["receipts"][0]["details"]["windowEvents"]
    original.extend([
        {"name": "switch", "value": "on", "date": "2026-10-25T01:30:00+00:00"},
        {"name": "switch", "value": "off", "date": "2026-10-25T01:30:00+01:00"},
    ])
    case = build_case_file(data["question"], data["receipts"])
    stamps = [datetime.fromisoformat(e.timestamp_utc) for e in case.records]
    assert stamps == sorted(stamps)
    bst, gmt = [e for e in case.records if e.action == "switch"]
    assert bst.timestamp_original.endswith("+01:00")
    assert gmt.timestamp_original.endswith("+00:00")
    assert bst.timestamp_utc != gmt.timestamp_utc


def test_offset_free_ambiguous_hour_rejected_not_fold_guessed():
    data = json.loads(FIXTURE.read_text())
    data["receipts"][0]["details"]["windowEvents"].append({
        "name": "switch", "value": "on", "date": "2026-10-25T01:30:00"})
    case = build_case_file(data["question"], data["receipts"])
    assert len(case.records) == 8
    assert any("missing offset" in err for err in case.errors)


def test_conflicting_target_row_is_not_evidence_of_target_action():
    data = json.loads(FIXTURE.read_text())
    data["receipts"][0]["details"]["windowEvents"].append({
        "name": "command-off", "deviceId": "9999", "date": "2026-10-25T00:47:00+01:00"})
    case = build_case_file(data["question"], data["receipts"])
    assert len(case.records) == 8
    assert any("target mismatch" in e for e in case.errors)


def test_conflicting_response_target_quarantines_entire_event_collection():
    data = json.loads(FIXTURE.read_text())
    data["receipts"][0]["details"]["deviceId"] = "9999"
    case = build_case_file(data["question"], data["receipts"])
    assert not case.records
    assert case.coverage[0].returned_rows == 0
    assert any("response target" in err for err in case.errors)


def test_duplicates_merge_references_without_repeating_observation():
    data = json.loads(FIXTURE.read_text())
    details = data["receipts"][0]["details"]
    details["observedEvents"] = deepcopy(details["windowEvents"][:1])
    case = build_case_file(data["question"], data["receipts"])
    assert len(case.records) == 8
    assert len(case.records[0].raw_references) == 2


def test_empty_success_and_failure_do_not_prove_no_actions():
    data = json.loads(FIXTURE.read_text())
    read = data["receipts"][0]
    read["details"]["windowEvents"] = []
    case = build_case_file(data["question"], [read, {**read, "success": False}])
    assert not case.records
    assert [c.succeeded for c in case.coverage] == [True, False]
    assert all(c.source_complete is False for c in case.coverage)


def test_only_explicit_complete_integrity_can_assert_completeness():
    data = json.loads(FIXTURE.read_text())
    details = data["receipts"][0]["details"]
    details.update(sourceComplete=True, historySourceIntegrityVerified=True,
                   observedEventsTruncated=False)
    assert build_case_file(data["question"], data["receipts"]).coverage[0].source_complete is True
    details.pop("sourceComplete")
    assert build_case_file(data["question"], data["receipts"]).coverage[0].source_complete is None


def test_triggered_listener_not_mistaken_for_issuer():
    data = json.loads(FIXTURE.read_text())
    e = data["receipts"][0]["details"]["windowEvents"][0]
    e.pop("producedBy")
    e["triggered"] = [{"appId": 4019}]
    case = build_case_file(data["question"], data["receipts"])
    assert case.records[0].producer_id is None


def test_generic_mqtt_and_temperature_have_no_device_specific_routing():
    data = json.loads(FIXTURE.read_text())
    source = data["receipts"][0]
    source["arguments"]["args"]["deviceId"] = "7103"
    source["details"]["deviceId"] = "7103"
    source["details"]["events"] = [
        {"name": "mqttStatus", "value": "disconnected", "date": "2026-10-24T09:00:00Z"},
        {"name": "temperature", "value": 57.2, "date": "2026-10-24T09:01:00Z"},
    ]
    source["details"].pop("windowEvents")
    case = build_case_file("Investigate a device fault", [source])
    assert [(e.action, e.value) for e in case.records] == [
        ("mqttStatus", "disconnected"), ("temperature", "57.2")]


def test_app_log_statement_is_not_command_issued_even_with_on_text():
    read = {"tool": "hub_manage_logs", "sub_tool": "hub_get_logs", "success": True,
            "arguments": {"args": {"appId": "4019"}}, "details": {"logs": [{
                "date": "2026-10-25T00:42:00+01:00", "name": "on",
                "message": "called on()"}]}}
    case = build_case_file("Why?", [read])
    assert len(case.records) == 1
    assert case.records[0].stage == "app_log_statement"
    assert case.records[0].producer_id is None


def test_unrecognized_payload_does_not_invent_records():
    case = build_case_file("Why?", [{"tool": "hub_read_rules", "success": True,
                                     "summary": "command-off happened at 01:00", "details": {}}])
    assert not case.records
    assert len(case.coverage) == 1


def test_malformed_input_is_recorded_without_crashing():
    case = build_case_file("question", [None, "bad", {"tool": "hub_read_devices", "success": False}])
    assert len(case.coverage) == 1
    assert len(case.errors) == 3
