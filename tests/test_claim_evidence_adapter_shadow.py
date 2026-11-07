"""Claim-v2 adapter adversarial and cross-domain frozen synthetic evaluations.

All entities are fictitious. This suite is not a measured live-answer score.
Tests use source-style receipts and deliberately distrust newest-N/log queries.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from claim_evidence_contract import (
    SCHEMA, Witness, EvidencePacket, Coverage, validate_claims, render_claims,
)
from claim_evidence_adapter import (
    packet_from_evidence, assess_evidence_shadow, witness_menu,
)

FOCAL = "2026-11-07T00:30:00.023+00:00"
FIRST = "2026-11-05T02:41:58+00:00"


def _switch(t, val):
    return {"name": "switch", "value": val, "isStateChange": True,
            "date": t, "producedBy": {"type": "device",
                                     "label": "Example Bridge"}}


def _command(t, issuer):
    return {"name": "command-off", "type": "command", "date": t,
            "producedBy": {"type": "app", "id": issuer,
                           "label": "Example Button"}}


def packet_receipts():
    events = [
        _switch(FOCAL, "off"),
        _switch("2026-11-06T20:58:15.909+00:00", "on"),
        _switch("2026-11-06T20:53:25.948+00:00", "off"),
        _switch("2026-11-06T18:11:51+00:00", "on"),
        _switch("2026-11-06T15:29:53.708+00:00", "off"),
        _switch("2026-11-06T15:13:18+00:00", "on"),
        _switch("2026-11-06T01:49:39+00:00", "off"),
        _switch("2026-11-06T00:23:56+00:00", "on"),
        _switch("2026-11-05T23:11:48+00:00", "off"),
        _switch("2026-11-05T19:30:44+00:00", "on"),
        _switch(FIRST, "off"),
    ]
    commands = [
        _command("2026-11-06T20:53:25.307+00:00", "1252"),
        _command("2026-11-06T15:29:52.776+00:00", "1252"),
        _command("2026-11-04T10:50:45+00:00", "1252"),
        _command("2026-11-03T19:23:27+00:00", "1252"),
        _command("2026-11-03T18:55:28+00:00", "1252"),
        _command("2026-11-01T22:05:49+00:00", "4209"),
        _command("2026-10-31T15:57:46+00:00", "1252"),
    ]
    report = [
        {"tool": "hub_read_devices", "sub_tool": "hub_list_devices",
         "success": True, "mutates": False, "effect": "read",
         "evidence_kind": "targeted_device_lookup",
         "details": {"reportedDeviceState": {
             "deviceId": "7828", "label": "Example Lamp",
             "reportedAttributes": {"switch": "off"},
         }}},
        {"tool": "homebrain_device_history", "success": True,
         "mutates": False, "effect": "read",
         "evidence_kind": "authoritative_device_event_history",
         "details": {"label": "Example Lamp", "attribute": "switch",
                     "boundaryEvents": events}},
        {"tool": "homebrain_device_history", "success": True,
         "mutates": False, "effect": "read",
         "evidence_kind": "deterministic_device_event_history",
         "details": {"label": "Example Lamp", "attribute": "switch",
                     "boundaryEvents": events[:4]}},
        {"tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
         "success": True, "mutates": False, "effect": "read",
         "timestamp": "2026-11-07T10:05:15.625956+00:00",
         "evidence_kind": "authoritative_command_event_history",
         "arguments": {"tool": "hub_list_device_events",
                       "args": {"deviceId": "7828", "attribute": "command-off",
                                "hoursBack": 168, "limit": 20}},
         "details": {"label": "Example Lamp", "eventName": "command-off",
                     "events": commands, "eventCount": len(commands)}},
        {"tool": "homebrain_causal_secondary_correlation",
         "success": True, "mutates": False, "effect": "read",
         "evidence_kind": "deterministic_causal_secondary_correlation",
         "details": {
             "subject": "Example Lamp", "transition": "off",
             "requestedBoundary": FOCAL,
             "sensorSelection": {"candidateDisposition": [
                 {"id": str(8000 + i),
                  "reason": "probed" if i < 4 else "not-in-probe"}
                 for i in range(10)
             ]},
             "historicalJournal": {"sensors": [{
                 "deviceId": "8001", "label": "Example Desk",
                 "attribute": "motion", "events": [{
                     "value": "inactive",
                     "observedAt": "2026-11-07T00:29:41.617787+00:00",
                     "timestampBasis": "collector-received",
                 }],
             }]},
         }},
    ]
    for ident, kind in (("8001", "motion"), ("8002", "presence")):
        report.append({
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False, "effect": "read",
            "evidence_kind": "authoritative_device_event_history",
            "arguments": {"tool": "hub_list_device_events", "args": {
                "deviceId": ident, "attribute": kind,
                "since": "2026-11-07T00:25:00+00:00",
                "until": "2026-11-07T00:32:00+00:00"}},
            "details": {"deviceId": ident, "attribute": kind, "label": kind,
                        "windowVerified": True, "events": [], "eventCount": 0,
                        "sourceHistoryComplete": False},
        })
    for i, (entity, frm, to) in enumerate([
        ("7828", "2026-11-06T20:58:05+00:00", "2026-11-06T20:58:25+00:00"),
        ("*", "2026-11-06T15:13:08+00:00", "2026-11-06T15:13:28+00:00"),
        ("4020", "2026-11-06T15:13:08+00:00", "2026-11-06T15:13:28+00:00"),
        ("4209", "2026-11-06T15:13:08+00:00", "2026-11-06T15:13:28+00:00"),
    ]):
        args = {"mode": "past", "since": frm, "until": to}
        args.update({"appId": entity} if entity in ("4020", "4209")
                    else {"deviceId": entity} if entity != "*" else {})
        report.append({
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "mutates": False, "effect": "read",
            "evidence_kind": "tool_result",
            "arguments": {"tool": "hub_get_logs", "args": args},
            "details": {"nativePastLog": {"returnedPageCount": 0,
                                          "matchedRowsReported": 0}},
        })
    report.append({
        "tool": "hub_read_rules", "sub_tool": "hub_list_rules",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "tool_result",
        "arguments": {"tool": "hub_list_rules"}, "details": {},
    })
    return report


def _one(claim, packet):
    return validate_claims({"schema": SCHEMA, "claims": [claim]}, packet).results[0]


def test_focal_receipts_drive_all_sample_indices_and_probed_vs_history_read():
    p = packet_from_evidence(packet_receipts())
    assert p.focal_time.startswith("2026-11-07T00:30:00")
    assert p.witnesses["w_off1"].value == "off"
    assert p.witnesses["w_on1"].value == "on"
    assert len(p.eligible_transition_keys) == 6
    assert p.candidate_sensor_count == 10
    assert p.candidate_sensor_probed_count == 4
    assert p.direct_sensor_windows_checked == 2
    assert p.log_reads_total == 4 and p.log_reads_containing_focal == 0
    assert p.internal_configuration_inspected is False
    assert len(p.journal_reception_event_keys) == 1
    assert "Example Lamp" in witness_menu(p)


def test_shadow_counts_verified_sample_not_model_quality_score():
    s = assess_evidence_shadow(packet_receipts())
    assert s["shadow_only"] and s["focal_attested"]
    assert s["model_claims_assessed"] is False
    assert s["returned_command_pairing"] == {
        "off_transitions": 6,
        "matching_recorded_commands": 2,
        "unmatched_in_returned_records": 4,
        "matching_tolerance_seconds": 2,
        "historical_completeness_verified": False,
    }
    assert s["source_sensor_windows_checked"] == 2
    assert s["candidate_sensors_marked_probed"] == 4
    assert s["candidate_sensors"] == 10
    assert s["app_log_requests"] == 4
    assert s["app_log_requests_covering_focal"] == 0


def test_focal_absence_query_requires_checked_window_and_real_zero_matches():
    p = packet_from_evidence(packet_receipts())
    c = Coverage("logs", "app:4020", "past-app-logs",
                 "2026-11-06T15:13:08+00:00",
                 "2026-11-06T15:13:28+00:00",
                 1, False, successful=True, matched_count=0,
                 query_kind="app-log")
    bad = _one({"kind": "absent_in_scope", "entity": "app:4020",
                "what": "app-log", "coverage_id": "logs"},
               replace(p, coverage={**p.coverage, "logs": c}))
    assert bad.reason == "coverage_window_mismatch"
    same = replace(c, window_start="2026-11-07T00:20:00+00:00",
                   window_end="2026-11-07T00:40:00+00:00", pages_checked=0)
    assert _one({"kind": "absent_in_scope", "entity": "app:4020",
                 "what": "app-log", "coverage_id": "logs"},
                replace(p, coverage={**p.coverage, "logs": same})).reason == (
                    "coverage_unverified"
                )
    assert all(cov.query_kind != "app-log" for cov in p.coverage.values())


def test_journal_reception_is_not_source_motion_event_or_caused_lag():
    p = packet_from_evidence(packet_receipts())
    w = next(w for w in p.witnesses.values() if w.role == "journal-reception")
    wrong = {"kind": "observed_value", "entity": w.entity,
             "attribute": w.event_class, "value": w.value,
             "witness_ids": [w.witness_id]}
    assert _one(wrong, p).reason == "wrong_witness_role"
    assert _one({"kind": "correlation",
                 "witness_ids": [w.witness_id, "w_off1"]}, p).reason == (
                     "wrong_witness_role"
                 )
    good = _one({"kind": "journal_observation", "entity": w.entity,
                 "attribute": w.event_class, "value": w.value,
                 "witness_ids": [w.witness_id]}, p)
    assert good.ok and good.facts["event_clock_verified"] is False
    rendered = render_claims(validate_claims(
        {"schema": SCHEMA, "claims": [good.claim]}, p), p)
    assert "collector-received" in rendered
    assert "original sensor-event time" in rendered


def test_transition_claim_model_cannot_repeat_or_choose_subset():
    p = packet_from_evidence(packet_receipts())
    id_ = next(k for k, v in p.coverage.items() if v.query_kind == "command-off")
    c = {"kind": "transition_pairing", "entity": "7828", "coverage_id": id_}
    accepted = _one(c, p)
    assert accepted.ok and accepted.facts["unmatched"] == 4
    for attack in (
        {**c, "transition_ids": ["w_off1", "w_off1", "w_off1"]},
        {**c, "witness_ids": ["w_off1", "w_off2"]},
    ):
        assert _one(attack, p).reason == "model_selected_sample"
    output = render_claims(validate_claims({"schema": SCHEMA, "claims": [c]}, p), p)
    assert "in the returned records" in output
    assert "does not prove an external cause" in output


def test_failed_receipts_never_supply_states_commands_or_sensor_coverage():
    original = packet_receipts()
    for index in (0, 1, 4):
        data = deepcopy(original)
        data[index]["success"] = False
        p = packet_from_evidence(data)
        if index in (0, 1):
            assert not p.focal_time
        else:
            assert not p.journal_reception_event_keys
    data = deepcopy(original)
    data[3]["success"] = False
    p = packet_from_evidence(data)
    assert not any(c.query_kind == "command-off" for c in p.coverage.values())
    assert assess_evidence_shadow(data)["returned_command_pairing"] is None


def test_historical_coverage_and_model_control_cannot_invent_focal_event():
    data = packet_receipts()
    for mutate in (
        lambda x: x.pop(0),
        lambda x: x[4]["details"].update(requestedBoundary="2026-11-06T15:29:53+00:00"),
        lambda x: x[1]["details"]["boundaryEvents"].pop(0),
    ):
        altered = deepcopy(data)
        mutate(altered)
        assert not packet_from_evidence(altered).focal_time
    noncausal = [{"tool": "hub_read_devices", "success": True, "mutates": False,
                  "evidence_kind": "authoritative_device_event_history",
                  "details": {"label": "Example Temperature", "attribute": "temperature",
                              "observedEvents": [{"value": 21.5}]}}]
    assert assess_evidence_shadow(noncausal)["focal_attested"] is False


def test_cross_domain_typed_values_and_derived_math():
    """Held-out synthetic humidity, heating and power receipts use same schema."""
    cases = [
        ("humidity", "74", "59", "%", -15.0),
        ("heatingSetpoint", "22", "18", "°C", -4.0),
        ("power", "90", "13", "W", -77.0),
    ]
    for attr, first, last, unit, expected in cases:
        p = EvidencePacket(
            witnesses={
                "a": Witness("a", "900", attr, "reporter",
                             "2026-11-07T08:00:00+00:00", "source",
                             first, "first", unit=unit),
                "b": Witness("b", "900", attr, "reporter",
                             "2026-11-07T08:30:00+00:00", "source",
                             last, "last", unit=unit),
            },
            focal_event_keys=frozenset({"first", "last"}),
        )
        c = {"kind": "calculation", "op": "delta",
             "witness_ids": ["a", "b"]}
        assert _one(c, p).facts["delta"] == expected
        # A collector receipt cannot be used to invent a heating delta.
        different = replace(p, witnesses={
            **p.witnesses,
            "a": replace(p.witnesses["a"], clock_basis="collector-received"),
        })
        assert _one(c, different).reason == "clock_unverified"


def test_hub_health_warning_is_not_root_cause_of_reboot():
    p = EvidencePacket(witnesses={
        "warn": Witness("warn", "hub", "memory_warning", "reporter",
                        "2026-11-07T08:10:00+00:00", "source",
                        "low", "f"),
    }, focal_event_keys=frozenset({"f"}))
    assert _one({"kind": "external_cause", "witness_ids": ["warn"]}, p).reason == (
        "unknown_claim_kind"
    )
    assert not _one({"kind": "observed_value", "entity": "hub",
                     "attribute": "memory_warning", "value": "low",
                     "witness_ids": ["warn"]}, p).reason
