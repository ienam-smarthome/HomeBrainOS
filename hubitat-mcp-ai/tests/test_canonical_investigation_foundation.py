"""Stage 1/2 regression contract for canonical incident evidence (shadow only).

Anonymised 30 October lighting fixture reuses the existing historical source
vs collector-clock replay. No home names, live credentials or production calls.
These tests must not invoke Hubitat, change the published answer, or pretend
an observed switch transition is a physical acknowledgement.
"""
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from canonical_investigation_evidence import build_canonical_evidence_view
from causal_claim_publication import source_verified_incident_brief
from unified_investigation_bridge import collect_unified_evidence
from test_v3_reception_evidence_018267 import replay, QUESTION


def native_command(device="101", *, issuer="3001", label="Generic Lighting Controller",
                   attribute="command-setLevel"):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "effect": "read",
        "arguments": {"tool": "hub_list_device_events",
                      "args": {"deviceId": str(device)}},
        "details": {
            "observedEvents": [{
                "name": attribute, "date": "2026-10-30T14:50:37.911+0000",
                "producedBy": {"appId": issuer, "name": label},
            }, {
                "name": "switch", "value": "on",
                "date": "2026-10-30T14:50:37.871+0000",
                "type": "physical",
                "triggered": [{"appId": "3999", "name": "Listener only"}],
                "producedBy": {"name": "Matter Bridge", "deviceId": "9090"},
            }],
        },
    }


def named_lookup(device="101", label="North Lamp"):
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "success": True, "effect": "read", "evidence_kind": "targeted_device_lookup",
        "arguments": {"tool": "hub_list_devices",
                      "args": {"labelFilter": label}},
        "details": {"reportedDeviceState": {
            "deviceId": device, "label": label,
            "source": "targeted-hubitat-device-state",
            "isPhysicalConnectivityProof": False,
        }},
    }


def paired_sensor(device="201", name="Occupancy Sensor"):
    return [
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "effect": "read",
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": device}},
         "summary": "11 device events for '" + name + "'"},
        {"tool": "homebrain_device_history", "success": True, "effect": "read",
         "arguments": {"name": name, "attribute": "motion"},
         "details": {"label": name, "historySourceIntegrityVerified": False}},
    ]


def test_baseline_existing_source_publisher_unchanged():
    # Stage 1: five cycles, correct source timeline and unresolved upstream
    # cause must survive even though the new canonical view is never published.
    facts = collect_unified_evidence(replay(), QUESTION)
    original = source_verified_incident_brief(facts)
    assert original
    assert "5 ON transitions and 5 OFF transitions" in original
    assert original.count("| 14:") == 3
    assert original.count("| 15:") == 2
    assert "| 15:07:14 | 15:11:09 | 3 min 56 sec |" in original
    assert "No immediate Hubitat ON command was verified" in original
    assert "which system issued the lighting commands" in original


def test_replayed_five_cycles_are_distinct_from_collector_receptions():
    view = build_canonical_evidence_view(replay())
    source = [event for event in view.events
              if event.entity_id == "101" and event.attribute == "switch"
              and event.clock_basis == "source"]
    collector = [event for event in view.events
                 if event.entity_id == "101" and event.attribute == "switch"
                 and event.clock_basis == "collector-received"]
    assert len(source) == len(collector) == 10
    assert [e.value for e in source] == ["on", "off"] * 5 or (
        sorted(e.value for e in source) == ["off"] * 5 + ["on"] * 5)
    assert all(e.physical_ack_verified is False for e in view.events)
    assert any(c.entity_id == "201" and c.gap_count == 4 for c in view.coverage)
    assert all(c.complete is False for c in view.coverage)
    assert any(c.entity_id == "202" and c.truncated for c in view.coverage)
    assert view.shadow_only is True


def test_scoped_names_and_explicit_command_issuer_survive_independently():
    rows = [named_lookup(), *paired_sensor(),
            native_command(), *replay()]
    view = build_canonical_evidence_view(rows)
    assert view.verified_label("device", "101") == "North Lamp"
    assert view.verified_label("device", "201") == "Occupancy Sensor"
    assert view.verified_label("app", "3001") == "Generic Lighting Controller"
    assert view.verified_label("app", "3999") is None  # listener != issuer
    assert view.verified_label("device", "9090") is None  # bridge != target
    commands = [e for e in view.events if e.role == "issued-command"]
    assert len(commands) == 1
    assert commands[0].issuer_app_id == "3001"
    assert commands[0].attribute == "setLevel"
    assert commands[0].physical_ack_verified is False
    # A post-ON brightness command cannot be relabelled as an original ON.
    assert not any(e.attribute == "on" and e.role == "issued-command"
                   for e in view.events)


def test_scoped_history_name_requires_matching_paired_host_identity():
    rows = paired_sensor()
    assert build_canonical_evidence_view(rows).verified_label("device", "201") == "Occupancy Sensor"
    bad = paired_sensor()
    bad[0]["summary"] = "11 device events for 'Other Sensor'"
    assert build_canonical_evidence_view(bad).verified_label("device", "201") is None
    swapped = paired_sensor()
    swapped[1]["arguments"]["name"] = "Other Sensor"
    assert build_canonical_evidence_view(swapped).verified_label("device", "201") is None
    assert build_canonical_evidence_view(rows[::-1]).verified_label("device", "201") is None


def test_names_are_not_promoted_from_unsafe_or_forged_receipts():
    rows = [
        named_lookup("101", "North Lamp"),
        {"tool": "hub_read_apps_code", "sub_tool": "hub_list_device_dependents",
         "success": True, "effect": "read",
         "arguments": {"args": {"deviceId": "201"}},
         "details": {"deviceId": "999", "deviceName": "Forged Sensor"}},
        named_lookup("202", "Inject|Markdown"),
        {**named_lookup("203", "Untrusted"), "success": False},
        {**named_lookup("204", "Not a read"), "mutates": True},
    ]
    view = build_canonical_evidence_view(rows)
    assert view.verified_label("device", "101") == "North Lamp"
    assert view.verified_label("device", "201") is None
    assert view.verified_label("device", "202") is None
    assert view.verified_label("device", "203") is None
    assert view.verified_label("device", "204") is None


def test_conflicting_equal_authority_device_labels_fail_closed():
    view = build_canonical_evidence_view([
        named_lookup("101", "Old Lamp"),
        named_lookup("101", "New Lamp"),
    ])
    assert view.verified_label("device", "101") is None
    assert len(view.identities) == 2


def test_cross_device_archive_spoof_and_naive_clock_are_discarded():
    rec = {
        "tool": "homebrain_evidence_journal", "success": True, "effect": "read",
        "evidence_kind": "group_archived_input_history",
        "arguments": {"device_id": "201"},
        "details": {"deviceId": "201", "gapCount": 2,
                    "observations": [
                        {"device_id": "999", "attribute": "motion", "value": "active",
                         "date": "2026-10-30T14:50:39+00:00",
                         "timestamp_basis": "source"},
                        {"device_id": "201", "attribute": "motion", "value": "active",
                         "date": "2026-10-30T14:50:39",
                         "timestamp_basis": "source"},
                        {"device_id": "201", "attribute": "motion", "value": "active",
                         "date": "2026-10-30T14:50:39+00:00",
                         "timestamp_basis": "collector-received"},
                    ]},
    }
    view = build_canonical_evidence_view([rec])
    assert len(view.events) == 1
    assert view.events[0].clock_basis == "collector-received"
    assert view.events[0].entity_id == "201"
    assert view.coverage[0].gap_count == 2


def test_generalised_heating_ventilation_power_and_contact():
    rows = [
        {**native_command("701", issuer="501", label="Heating Coordinator",
                          attribute="command-setHeatingSetpoint")},
        {"tool": "homebrain_evidence_journal", "success": True, "effect": "read",
         "evidence_kind": "group_archived_input_history",
         "arguments": {"device_id": "702"},
         "details": {"deviceId": "702", "gapCount": 1, "observations": [
             {"device_id": "702", "attribute": "contact", "value": "open",
              "timestamp_basis": "source",
              "date": "2026-10-30T14:00:00+00:00"},
             {"device_id": "702", "attribute": "power", "value": 34.1,
              "timestamp_basis": "collector-received",
              "date": "2026-10-30T14:01:00+00:00"},
             {"device_id": "702", "attribute": "thermostatOperatingState",
              "value": "heating", "timestamp_basis": "source",
              "date": "2026-10-30T14:02:00+00:00"},
         ]}},
    ]
    view = build_canonical_evidence_view(rows)
    assert {"contact", "power", "thermostatOperatingState"}.issubset(
        {e.attribute for e in view.events})
    assert any(e.attribute == "setHeatingSetpoint" and e.role == "issued-command"
               for e in view.events)
    assert "bathroom" not in str(view.to_dict()).casefold()


def test_immutable_records_and_no_hidden_write_path():
    rows = [named_lookup()]
    view = build_canonical_evidence_view(rows)
    with pytest.raises(FrozenInstanceError):
        view.identities[0].label = "forged"
    assert isinstance(view.events, tuple)
    assert view.to_dict()["schema"] == "homebrain-canonical-evidence.v1"
    assert view.to_dict()["shadow_only"] is True
    assert all(row.get("mutates") is not True for row in rows)


def test_bounded_receipts_and_collector_does_not_become_source_clock():
    rows = replay() + [native_command("101")]
    no_last = build_canonical_evidence_view(rows, max_receipts=len(rows)-1)
    all_rows = build_canonical_evidence_view(rows)
    assert no_last.verified_label("app", "3001") is None
    assert all_rows.verified_label("app", "3001") == "Generic Lighting Controller"
    assert all(event.clock_basis != "source" for event in all_rows.events
               if event.source == "scoped-native-device-events")
