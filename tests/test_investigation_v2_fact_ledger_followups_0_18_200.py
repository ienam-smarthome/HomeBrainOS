"""Source-backed factual claims and read-only next-step hints (0.18.200)."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_fact_ledger import factual_evidence_ledger
from investigation_v2.native_source_followup import source_path_followup


def warning():
    return {"read": 1, "operation": "hub_get_logs", "source_data": {
        "log_summary": {"warning_error_groups": [{
            "source_id": "7934", "level": "WARN",
            "message": "method runQ of device Google Nest Hub ran for 124,842ms",
            "count": 1,
            "oldest_returned": "2026-10-28 17:04:48",
            "newest_returned": "2026-10-28 17:04:48",
        }]}}}


def events():
    return {"read": 2, "operation": "hub_list_device_events",
            "read_filters": {"deviceId": "7934"},
            "source_data": {"issuer_apps": [{
                "appId": "1679", "name": "Adhan Player", "count": 11,
                "oldest": "2026-10-28T18:14:51+0000",
                "newest": "2026-10-28T18:15:02+0000",
            }]}}


def config(driver_id=None):
    identity = {"driverId": driver_id} if driver_id else {"name": "Google Cast"}
    return {"read": 3, "operation": "hub_get_device",
            "read_filters": {"deviceId": "7934", "mode": "configuration"},
            "source_data": {"device_mode": "configuration",
                            "device_identity": identity}}


def test_method_warning_receipt_distinguishes_duration_from_causation():
    facts = factual_evidence_ledger([warning(), events()], ["7934"])
    assert [x["kind"] for x in facts] == [
        "source_reported_warning", "source_attested_device_command_issuer",
    ]
    assert facts[0]["named_method"] == "runQ"
    assert facts[0]["source_reported_duration_ms"] == 124842
    assert facts[0]["evidence_reads"] == [1]
    assert facts[1]["app_id"] == "1679"
    assert facts[1]["evidence_reads"] == [2]
    assert all(x["root_cause_verified"] is False for x in facts)
    assert "causal link" in facts[1]["limits"]


def test_duplicate_log_reads_do_not_create_duplicate_facts():
    facts = factual_evidence_ledger([warning(), warning()], ["7934"])
    assert len(facts) == 1


def test_different_device_warning_not_assigned_to_target():
    other = warning()
    other["source_data"]["log_summary"]["warning_error_groups"][0]["source_id"] = "7103"
    assert factual_evidence_ledger([other], ["7934"]) == []


def test_verified_full_source_receipt_is_static_not_runtime_cause():
    source = {"read": 4, "operation": "hub_get_source", "source_data": {
        "source_complete": True, "requested_source_type": "driver",
        "requested_source_id": "55", "static_method_paths": {
            "recognized_method_count": 12, "method_rows_returned": 10}}}
    facts = factual_evidence_ledger([source], ["7934"])
    assert len(facts) == 1
    assert facts[0]["kind"] == "verified_static_source_structure"
    assert facts[0]["root_cause_verified"] is False


def test_missing_code_does_not_get_a_source_fact():
    source = {"read": 4, "operation": "hub_get_source", "source_data": {
        "source_complete": False, "requested_source_type": "driver",
        "requested_source_id": "55"}}
    assert factual_evidence_ledger([source], ["7934"]) == []


def test_initial_source_next_step_is_configuration_not_guessed_id():
    hint = source_path_followup([warning(), events()], ["7934"], set())
    assert hint["status"] == "driver_identity_not_yet_inspected"
    assert hint["model_chosen_read"]["args"]["deviceId"] == "7934"
    assert "id" not in hint["model_chosen_read"]["args"]


def test_verified_driver_identity_permits_suggestion_but_no_tool_execution():
    hint = source_path_followup(
        [warning(), events(), config("55")], ["7934"], {"55"})
    assert hint["status"] == "verified_driver_identity_available"
    assert hint["model_chosen_read"] == {
        "operation": "hub_get_source", "args": {"type": "driver", "id": "55"}}
    assert hint["evidence_read"] == 3


def test_unverified_driver_id_never_authorises_source_read():
    hint = source_path_followup(
        [warning(), config("55")], ["7934"], set())
    assert hint["status"] == "driver_identity_missing_from_configuration"
    assert "model_chosen_read" not in hint


def test_metadata_only_source_is_not_repeated():
    source = {"read": 4, "operation": "hub_get_source",
              "source_data": {"source_complete": False,
                              "requested_source_type": "driver",
                              "requested_source_id": "55"}}
    hint = source_path_followup(
        [warning(), config("55"), source], ["7934"], {"55"})
    assert hint["status"] == "source_read_already_attempted_without_complete_code"
    assert "model_chosen_read" not in hint


def test_no_warning_or_ambiguous_target_does_not_force_source():
    assert source_path_followup([events()], ["7934"], set()) is None
    assert source_path_followup([warning()], ["7934", "7103"], set()) is None

def test_app_source_does_not_mask_missing_driver_source():
    unrelated_app = {"read": 4, "operation": "hub_get_source", "source_data": {
        "source_complete": True, "requested_source_type": "app",
        "requested_source_id": "1679",
    }}
    hint = source_path_followup(
        [warning(), config("55"), unrelated_app], ["7934"], {"55"})
    assert hint["status"] == "verified_driver_identity_available"
    assert hint["model_chosen_read"]["args"] == {"type": "driver", "id": "55"}
