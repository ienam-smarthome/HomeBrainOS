"""Source-role attribution from real device-scoped native event receipts.

The original incident used hub_read_devices/hub_list_device_events, NOT the
homebrain_device_history wrapper that v0.18.250 originally recognized.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_initiator_provenance_guard import (
    build_state_report_provenance, render_state_report_provenance,
    guard_unverified_initiator_claims,
)
from investigation_checkpoint import build_evidence_checkpoint
from synthesis_validator import validate_synthesis

QUESTION = "Investigate why Zone Alpha Light, Zone Beta Light and Pump Switch changed state"


def native(device_id="101", *, events=None, truncated=False, scoped=True):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read", "mutates": False,
        "supports_live_claim": True,
        "evidence_kind": "tool_result",
        "arguments": {"tool": "hub_list_device_events", "args": (
            {"deviceId": str(device_id), "since": "2026-10-30T14:50:00Z"}
            if scoped else {"since": "2026-10-30T14:50:00Z"})},
        "details": {
            "label": None,
            "observedEvents": events if events is not None else [{
                "name": "switch", "value": "on",
                "date": "2026-10-30T15:28:13.424+0000",
                "type": "physical",
                "producedBy": {"name": "Matter Bridge", "deviceId": "900"},
                "triggered": [{"appId": 3001, "handler": "lightSwitchHandler"}],
            }],
            "observedEventsTruncated": truncated,
        },
    }


def direct_command():
    return {"name": "command-off", "value": None,
            "date": "2026-10-30T15:11:45.944+0000",
            "type": "command", "producedBy": {
                "name": "Pump Scheduler", "appId": 3002}}


def source_reports():
    return [native("101"), native("102"), native("103",
        events=[direct_command(), {
            "name": "switch", "value": "off",
            "date": "2026-10-30T15:11:46.134+0000",
            "type": "physical",
            "producedBy": {"name": "Matter Bridge", "deviceId": "900"},
            "triggered": [{"appId": 3002, "handler": "eventHandler"}],
        }])]


def test_native_device_scoped_receipts_produce_typed_source_roles():
    packet = build_state_report_provenance(source_reports())
    assert packet["state_report_count"] == 3
    assert packet["direct_command_count"] == 1
    assert packet["reporting_devices"] == ["Matter Bridge"]
    assert packet["reported_device_ids"] == ["101", "102", "103"]
    assert packet["downstream_listener_app_ids"] == ["3001", "3002"]
    assert packet["direct_command_app_ids"] == ["3002"]
    roles = {edge["role"] for edge in packet["source_role_edges"]}
    assert roles == {"reported-state", "notified-listener", "issued-command"}
    assert packet["upstream_initiator_established"] is False
    assert packet["source_history_completeness_verified"] is False


def test_model_checkpoint_and_final_contract_see_the_same_native_evidence():
    evidence = source_reports()
    checkpoint = build_evidence_checkpoint(
        QUESTION, evidence, available_read_tools=("hub_read_devices",))
    assert checkpoint["state_report_provenance"]["state_report_count"] == 3
    assert "independently logged command" in checkpoint["next_unchecked_discriminators"][0]
    brief = render_state_report_provenance(evidence)
    assert brief and "Source-role edges" in brief
    assert '"direct_command_count":1' in brief


def test_external_verdict_from_actual_multi_device_answer_is_not_accepted():
    text = (
        "Bathroom-style scenario: the **Zone Alpha Light** and "
        "**Zone Beta Light** were operated externally via Matter Bridge.\n"
        "**Zone Alpha Light and Zone Beta Light (External Control)**\n"
        "Both lights were operated entirely outside of Hubitat's command history.\n"
        "There were no Hubitat-issued commands for these transitions.\n"
        "A sensor was observed active before the lights reported ON.\n"
        "| 15:28 | Zone Alpha Light | ON | Reported by Matter Bridge |\n"
    )
    repaired, changed = guard_unverified_initiator_claims(
        text, source_reports(), QUESTION)
    assert changed
    assert "operated externally" not in repaired
    assert "operated entirely outside" not in repaired
    assert "(External Control)" not in repaired
    assert "(Initiator unverified)" in repaired
    assert "bounded evidence does not identify an initiating" in repaired
    assert "cannot rule out unobserved command paths" in repaired
    assert "A sensor was observed active" in repaired
    assert "| 15:28 | Zone Alpha Light | ON | Reported by Matter Bridge |" in repaired


def test_validator_corrects_external_source_verdict_using_native_rows():
    evidence = source_reports()
    draft = "Zone Alpha Light and Zone Beta Light were operated externally via Matter Bridge."
    repaired, issues = validate_synthesis(
        draft, evidence, original_user=QUESTION, causal=True)
    assert "causal_unverified_initiator" in issues
    assert "operated externally" not in repaired
    assert "initiating controller" in repaired


def test_unscoped_broad_history_and_failed_receipts_do_not_authorize_roles():
    rows = [native(scoped=False), native("102")]
    rows[1]["success"] = False
    packet = build_state_report_provenance(rows)
    assert packet["state_report_count"] == 0
    assert packet["source_role_edges"] == []


def test_truncation_is_admitted_as_coverage_limit_not_zero_event_proof():
    packet = build_state_report_provenance([native(truncated=True)])
    assert packet["returned_history_truncated"] is True
    assert packet["source_history_completeness_verified"] is False
    assert packet["absence_of_matching_command_is_not_external_proof"] is True


def test_label_only_deterministic_history_requires_verified_unique_lookup():
    row = native("101")
    row["tool"] = "homebrain_device_history"
    row["sub_tool"] = None
    row["arguments"] = {"name": "Zone Alpha Light"}
    row["details"]["label"] = "Zone Alpha Light"
    assert build_state_report_provenance([row])["state_report_count"] == 0
    lookup = {
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "targeted_device_lookup",
        "details": {"reportedDeviceState": {
            "deviceId": "101", "label": "Zone Alpha Light"}},
    }
    assert build_state_report_provenance([lookup, row])["state_report_count"] == 1


def test_native_command_without_state_report_does_not_prove_external_origin():
    packet = build_state_report_provenance([native(
        events=[direct_command()], device_id="103")])
    assert packet["direct_command_count"] == 1
    assert packet["state_report_count"] == 0
    assert packet["upstream_initiator_established"] is False
