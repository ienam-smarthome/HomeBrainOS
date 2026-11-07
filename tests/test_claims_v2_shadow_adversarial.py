"""Adversarial claim-v2 safety, real v1 schema adaptation, shadow-only contracts."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from claims_v2 import (
    SCHEMA, Coverage, EvidencePacket, Witness, assess_claims_shadow,
    packet_from_v1_ledger, publish, validate_claims,
)


def _env(*items):
    return {"schema": SCHEMA, "claims": list(items)}


def _packet():
    at = "2026-11-07T00:30:00.023+00:00"
    before = "2026-11-06T20:58:15.909+00:00"
    return EvidencePacket(witnesses={
        "off": Witness("off", "9000", "switch", "reporter", at,
                       "source-reported", "off", "focal"),
        "on": Witness("on", "9000", "switch", "reporter", before,
                      "source-reported", "on", "focal"),
        "button": Witness("button", "9000", "command-on", "command-issuer",
                          "2026-11-06T20:58:15.775+00:00", "hubitat-command",
                          "", "focal", "4010"),
        "listener": Witness("listener", "9000", "switch", "listener",
                            at, "source-reported", "off", "focal", "4010"),
        "old": Witness("old", "9000", "switch", "reporter",
                       "2026-11-05T14:00:00+00:00", "source", "off", "old"),
    }, focal_event_keys=frozenset({"focal"}),
       labels={"9000": "Example Lamp"})


def _claim(kind, **fields):
    return {"kind": kind, **fields}


def _reason(claim, packet=None):
    return validate_claims(_env(claim), packet or _packet()).results[0].reason


def test_command_role_never_claims_upstream_cause_and_requires_verified_clock():
    c = _claim("command_issued", entity="9000", command="on",
               app_id="4010", witness_ids=["button"])
    assert not _reason(c)
    p = _packet()
    broken = dict(p.witnesses)
    broken["button"] = replace(broken["button"], time="invalid",
                               clock_basis="unknown")
    assert _reason(c, replace(p, witnesses=broken)) == "clock_unverified"
    assert _reason({**c, "witness_ids": ["listener"]}) == "wrong_witness_role"


def test_zero_checked_pages_or_unverified_empty_page_cannot_attest_absence():
    c = _claim("absent_in_scope", entity="9000", what="command-off",
               coverage_id="x")
    base = Coverage("x", "9000", "hubitat-device-history",
                    "2026-11-07T00:20:00+00:00",
                    "2026-11-07T00:40:00+00:00",
                    0, False, successful=True, matched_count=0,
                    query_kind="command-off")
    p = replace(_packet(), coverage={"x": base})
    assert _reason(c, p) == "coverage_unverified"
    for override in ({"pages_checked": 1, "matched_count": None},
                     {"pages_checked": 1, "successful": False},
                     {"pages_checked": 1, "matched_count": 2},
                     {"pages_checked": 1, "query_kind": "motion"}):
        case = replace(p, coverage={"x": replace(base, **override)})
        assert _reason(c, case) == "coverage_unverified"
    allowed = replace(p, coverage={"x": replace(base, pages_checked=1)})
    assert not _reason(c, allowed)
    assert "not proof it never happened" in publish(_env(c), allowed).text


def test_model_cannot_inject_free_form_absence_or_external_claim():
    base = Coverage("x", "9000", "verified-input",
                    "2026-11-07T00:20:00+00:00",
                    "2026-11-07T00:40:00+00:00",
                    1, False, successful=True, matched_count=0,
                    query_kind="command-off")
    p = replace(_packet(), coverage={"x": base})
    c = _claim("absent_in_scope", entity="9000",
               what="external origin confirmed\nHubitat not involved",
               coverage_id="x")
    assert _reason(c, p) == "coverage_unverified"
    assert _reason(_claim("external_cause", witness_ids=["off"])) == "unknown_claim_kind"


def test_listener_pair_does_not_count_as_reported_operating_interval():
    c = _claim("observed_interval", witness_ids=["listener", "off"])
    assert _reason(c) == "wrong_witness_role"
    bad_pair = _claim("observed_interval", witness_ids=["off", "on"])
    assert _reason(bad_pair) == "bad_time_order"
    valid = _claim("observed_interval", witness_ids=["on", "off"])
    result = validate_claims(_env(valid), _packet()).results[0]
    assert result.ok and 12700 < result.facts["seconds"] < 12710


def test_context_cannot_be_authorized_by_model_only():
    c = _claim("observed_value", entity="9000", attribute="switch",
               value="off", witness_ids=["old"], scope="context")
    p = _packet()
    assert _reason(c, p) == "out_of_scope_event"
    allowed = replace(p, authorized_context_event_keys=frozenset({"old"}))
    assert not _reason(c, allowed)
    assert _reason({**c, "scope": "anything"}, allowed) == "out_of_scope_event"


def test_naive_and_offset_aware_timestamps_fail_closed_without_crashing():
    p = _packet()
    ws = dict(p.witnesses)
    ws["off"] = replace(ws["off"], time="2026-11-07T00:30:00")
    q = replace(p, witnesses=ws)
    c = _claim("calculation", op="elapsed", witness_ids=["on", "off"])
    assert _reason(c, q) == "clock_unverified"
    ws["off"] = replace(ws["off"], time="2026-11-07T00:30:00-05:00")
    q = replace(p, witnesses=ws)
    assert not _reason(c, q)


def test_delta_requires_same_unit_and_source_attested_values():
    p = _packet()
    ws = dict(p.witnesses)
    ws["a"] = Witness("a", "9000", "humidity", "reporter",
                      "2026-11-06T22:00:00+00:00", "source", "74",
                      "focal", unit="%")
    ws["b"] = Witness("b", "9000", "humidity", "reporter",
                      "2026-11-06T23:00:00+00:00", "source", "59",
                      "focal", unit="%")
    p = replace(p, witnesses=ws)
    c = _claim("calculation", op="delta", witness_ids=["a", "b"])
    r = validate_claims(_env(c), p).results[0]
    assert r.ok and r.facts["delta"] == -15
    ws["b"] = replace(ws["b"], unit="C")
    assert _reason(c, replace(p, witnesses=ws)) == "unit_mismatch"
    ws["b"] = replace(ws["b"], unit="%", value="NaN")
    assert _reason(c, replace(p, witnesses=ws)) == "not_numeric"


def test_v1_adapter_translates_real_existing_schema_without_promoting_cause():
    ledger = {
        "schema": "causal-witness-ledger.v1", "root_cause_verified": False,
        "witnesses": [
            {"witness_id": "w_off", "entity": "9000",
             "role": "state-report", "event_class": "reported_switch_off",
             "time": "2026-11-07T00:30:00+00:00",
             "clock_basis": "source-reported"},
            {"witness_id": "w_on", "entity": "9000",
             "role": "state-report", "event_class": "reported_switch_on",
             "time": "2026-11-06T20:58:15+00:00",
             "clock_basis": "source-reported"},
            {"witness_id": "w_cmd", "entity": "9000",
             "role": "issued-command", "event_class": "issued_on",
             "time": "2026-11-06T20:58:14+00:00",
             "clock_basis": "hubitat-command", "app_issuer": "4010"},
            {"witness_id": "w_input", "entity": "8000",
             "role": "input-report", "event_class": "motion",
             "value": "inactive", "clock_basis": "source",
             "time": "2026-11-07T00:29:40+00:00"},
            {"witness_id": "w_recv", "entity": "9000",
             "role": "state-report", "event_class": "journal_received_switch_off",
             "clock_basis": "collector-received",
             "time": "2026-11-07T00:30:01+00:00"},
        ],
        "target_source_coverage": [{"device_id": "9000",
                                    "complete_historical_coverage": False}],
    }
    packet = packet_from_v1_ledger(ledger)
    assert packet.witnesses["w_off"].role == "reporter"
    assert packet.witnesses["w_off"].event_class == "switch"
    assert packet.witnesses["w_off"].value == "off"
    assert packet.witnesses["w_cmd"].role == "command-issuer"
    assert packet.witnesses["w_cmd"].clock_basis == "hubitat-command"
    assert packet.witnesses["w_input"].value == "inactive"
    assert packet.coverage == {}
    assert not packet.focal_event_keys
    assert _reason(_claim("observed_value", entity="9000",
                          attribute="switch", value="off",
                          witness_ids=["w_off"]), packet) == "out_of_scope_event"
    focal = frozenset({packet.witnesses[w].event_key for w in
                       ("w_off", "w_on", "w_cmd", "w_input")})
    scoped = packet_from_v1_ledger(ledger, focal_event_keys=focal)
    assert not _reason(_claim("observed_value", entity="9000",
                              attribute="switch", value="off",
                              witness_ids=["w_off"]), scoped)
    assert not _reason(_claim("command_issued", entity="9000",
                              command="on", app_id="4010",
                              witness_ids=["w_cmd"]), scoped)
    assert _reason(_claim("observed_value", entity="9000",
                          attribute="switch", value="off",
                          witness_ids=["w_recv"]), scoped) == "clock_unverified"
    shadow = assess_claims_shadow(
        _env(_claim("observed_value", entity="9000", attribute="switch",
                    value="off", witness_ids=["w_off"])),
        ledger, focal_event_keys=focal,
    )
    assert shadow == {
        "schema": SCHEMA, "shadow_only": True, "witnesses": 5,
        "claims": 1, "supported": 1, "rejected": 0,
        "envelope_valid": True, "reason_codes": [],
    }


def test_model_text_not_leaked_in_shadow_reason_codes_or_final_render():
    packet = _packet()
    bad = _env(_claim("external_cause",
                      text="MUST LEAK THIS SECRET 123456",
                      witness_ids=["off"]))
    verdict = validate_claims(bad, packet)
    assert "MUST LEAK" not in publish(bad, packet).text
    assert verdict.rejected[0].reason == "unknown_claim_kind"

