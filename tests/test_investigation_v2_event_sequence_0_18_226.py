"""v0.18.226: actual Hubitat event sequence, not an invented physical cause.

Replays reported source events from 12 October: command -> independently
device-issuer-attested lastSeen -> switch=off -> later healthStatus=offline.
Checks strict identity, bounded chronology, partial source and configuration.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_temporal_lead import (
    verified_temporal_lead, temporal_lead_brief,
)
from investigation_v2.native_provenance import event_summary
from test_investigation_v2_temporal_lead_0_18_225 import receipts


def timeline():
    rows = receipts()
    raw_events = [
        {"name": "command-on",
         "date": "2026-10-24T21:51:12.157+0100",
         "producedBy": {"appId": "3103", "name": "Ikea Rodret Dimmer"}},
        {"name": "healthStatus", "value": "offline",
         "date": "2026-10-12T01:33:46.925+0100",
         "producedBy": {"deviceId": "7103", "name": "Bedroom 3 Mesh"}},
        {"name": "switch", "value": "off",
         "date": "2026-10-12T01:30:01.914+0100",
         "producedBy": {"deviceId": "7103", "name": "Bedroom 3 Mesh"}},
        {"name": "lastSeen", "value": "Mon Oct 12 01:30:01 BST 2026",
         "date": "2026-10-12T01:30:01.908+0100",
         "producedBy": {"deviceId": "7103", "name": "Bedroom 3 Mesh"}},
        {"name": "command-off",
         "date": "2026-10-12T01:30:01.743+0100",
         "producedBy": {"appId": "3950",
                        "name": "Power saving: Bedroom 3 Mesh off @night"}},
    ]
    rows[1]["source_data"] = event_summary({"events": raw_events})
    rows.append({
        "read": 4,
        "operation": "hub_get_app_config",
        "read_filters": {"appId": "3950"},
        "source_data": {
            "source_app_id_matches_request": True,
            "app_section_present": True, "settings_key_count": 82,
            "settings_values_projected": False,
            "requested_app_id": "3950", "label":
                "Power saving: Bedroom 3 Mesh off @night",
        },
    })
    return rows


def test_command_then_own_device_states_then_offline_is_properly_ordered():
    result = verified_temporal_lead(timeline(), ["7103"])
    assert result["app_id"] == "3950"
    assert result["absolute_gap_seconds"] == .743
    events = result["observed_event_sequence"]
    assert [e["attribute"] for e in events] == [
        "lastSeen", "switch", "healthStatus"]
    assert [e["seconds_after_command"] for e in events] == [
        .165, .171, 225.182]
    assert [e["value"] for e in events] == [
        "Mon Oct 12 01:30:01 BST 2026", "off", "offline"]
    assert all(e["read"] == 2 for e in events)
    assert result["app_config_metadata_reads"] == [4]
    assert result["mechanism_verified"] is False
    assert result["physical_command_delivery_verified"] is False
    assert result["clock_alignment_verified"] is False
    brief = temporal_lead_brief(result)
    for phrase in ("0.165s after the command",
                   "0.171s after the command",
                   "3m 45.182s after the command",
                   "switch=off", "healthStatus=offline",
                   "App configuration metadata was also retrieved",
                   "actual action settings and historical execution were not verified",
                   "not a verified cause"):
        assert phrase in brief
    assert "switch-state event strengthens" in brief
    assert "does not prove power physically switched" in brief
    assert "definitely caused" not in brief


def test_unrelated_device_cannot_supply_state_confirmation():
    rows = timeline()
    source = rows[1]["source_data"]
    for event in source["events"]:
        if event["name"] in ("switch", "healthStatus", "lastSeen"):
            event["producedBy"]["deviceId"] = "9999"
    result = verified_temporal_lead(rows, ["7103"])
    assert result["observed_event_sequence"] == []
    brief = temporal_lead_brief(result)
    assert "switch-state event" in brief
    assert "a `switch=off` event" not in brief


def test_malicious_actor_app_cannot_be_used_as_device_confirmation():
    rows = timeline()
    for event in rows[1]["source_data"]["events"]:
        if event["name"] == "switch":
            event["producedBy"] = {"appId": "3950", "name": "Not target"}
    result = verified_temporal_lead(rows, ["7103"])
    assert [e["attribute"] for e in result["observed_event_sequence"]] == [
        "lastSeen", "healthStatus"]


def test_wrong_or_unverified_config_id_is_not_counted():
    rows = timeline()
    rows[2]["source_data"]["source_app_id_matches_request"] = False
    assert verified_temporal_lead(rows, ["7103"])["app_config_metadata_reads"] == []
    rows = timeline()
    rows[2]["read_filters"]["appId"] = "9999"
    assert verified_temporal_lead(rows, ["7103"])["app_config_metadata_reads"] == []


def test_no_unjustified_offline_or_switch_inference_from_bare_command():
    rows = timeline()
    rows[1]["source_data"]["events"] = [
        e for e in rows[1]["source_data"]["events"]
        if e["name"].startswith("command-")]
    result = verified_temporal_lead(rows, ["7103"])
    assert result is not None
    assert result["observed_event_sequence"] == []
    assert "a `switch=off` event" not in temporal_lead_brief(result)


def test_far_later_status_and_switch_event_do_not_attach_to_command():
    rows = timeline()
    for e in rows[1]["source_data"]["events"]:
        if e["name"] in ("switch", "healthStatus"):
            e["date"] = "2026-10-29T18:31:46.801+0000"
    result = verified_temporal_lead(rows, ["7103"])
    assert [e["attribute"] for e in result["observed_event_sequence"]] == [
        "lastSeen"]


def test_duplicate_pages_do_not_create_duplicate_sequence_events():
    rows = timeline()
    rows.append({**copy.deepcopy(rows[1]), "read": 5})
    result = verified_temporal_lead(rows, ["7103"])
    assert len(result["observed_event_sequence"]) == 3
    assert result["later_on_commands"] == 1


def test_full_event_page_counts_commands_beyond_five_issuer_samples():
    rows = timeline()
    source_events = [
        {"name": "command-on",
         "date": f"2026-10-19T21:50:{n:02d}.778+0100",
         "producedBy": {"appId": "3103", "name": "Ikea Rodret Dimmer"}}
        for n in range(11)]
    # Build an actual projection with a 5-sample limit to validate that
    # the independent 80-row event page supplies the full bounded count.
    src = rows[1]["source_data"]
    originals = copy.deepcopy(src["events"])
    rows[1]["source_data"] = event_summary({
        "events": source_events + originals[1:]})
    result = verified_temporal_lead(rows, ["7103"])
    assert result["later_on_commands"] == 11
    assert result["sample_complete"] is False
