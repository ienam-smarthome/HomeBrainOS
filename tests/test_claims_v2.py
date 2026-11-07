import pytest
import sys
from pathlib import Path
APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from claim_evidence_contract import (Coverage, EvidencePacket, Witness, publish,
                       validate_claims, SCHEMA)

F = frozenset({"off-0030", "on-2058", "fp400-0029"})
W = {w.witness_id: w for w in [
    Witness("w_off", "L2", "switch", "reporter", "2026-11-07T00:30:00.023+00:00", "source", "off", "off-0030"),
    Witness("w_on", "L2", "switch", "reporter", "2026-11-06T20:58:15.909+00:00", "source", "on", "on-2058"),
    Witness("w_cmd_on", "L2", "command-on", "command-issuer", "2026-11-06T20:58:15.775+00:00", "source", "", "on-2058", "4020"),
    Witness("w_fp", "FP400", "motion", "input-report", "2026-11-07T00:29:40.936+00:00", "source", "inactive", "fp400-0029"),
    Witness("w_lis", "L2", "switch", "listener", "2026-11-07T00:30:00.100+00:00", "source", "off", "off-0030", "4020"),
    Witness("w_old", "L2", "switch", "reporter", "2026-11-06T15:13:00+00:00", "source", "off", "old-1513"),
    Witness("w_nocl", "L2", "switch", "reporter", "2026-11-07T00:30:00+00:00", "unknown", "off", "off-0030"),
]}
COV = {"c1": Coverage("c1", "L2", "device command history",
                      "2026-11-06T20:00:00+00:00", "2026-11-07T08:40:00+00:00", 2, False, successful=True, matched_count=0, query_kind="command-off")}
P = EvidencePacket(W, COV, F,
                   labels={"L2": "Livingroom Light 2", "FP400": "FP400"},
                   authorized_context_event_keys=frozenset({"old-1513"}))


def env(*claims):
    return {"schema": SCHEMA, "claims": list(claims)}


def one(claim):
    return validate_claims(env(claim), P).results[0]


def test_reported_off_ok():
    r = one({"kind": "observed_value", "entity": "L2", "attribute": "switch",
             "value": "off", "witness_ids": ["w_off"]})
    assert r.ok


def test_wrong_value_rejected():
    assert one({"kind": "observed_value", "entity": "L2", "attribute": "switch",
                "value": "on", "witness_ids": ["w_off"]}).reason == "value_mismatch"


def test_listener_cannot_support_value_or_command():
    assert one({"kind": "command_issued", "entity": "L2", "command": "off",
                "app_id": "4020", "witness_ids": ["w_lis"]}).reason == "wrong_witness_role"


def test_unverified_clock_rejected():
    assert one({"kind": "observed_value", "entity": "L2", "attribute": "switch",
                "value": "off", "witness_ids": ["w_nocl"]}).reason == "clock_unverified"


def test_no_kind_can_express_external_cause():
    assert one({"kind": "external_cause", "witness_ids": ["w_off"]}).reason == "unknown_claim_kind"


def test_absent_requires_known_coverage():
    assert one({"kind": "absent_in_scope", "entity": "L2", "what": "command-off",
                "coverage_id": "nope"}).reason == "missing_coverage"


def test_absent_renders_scope_and_incomplete_warning():
    pub = publish(env({"kind": "absent_in_scope", "entity": "L2",
                       "what": "command-off", "coverage_id": "c1"}), P)
    assert "in the records checked" in pub.text
    assert "not proof it never happened" in pub.text


def test_event_scope_blocks_old_interval_in_focal_section():
    c = {"kind": "observed_value", "entity": "L2", "attribute": "switch",
         "value": "off", "witness_ids": ["w_old"]}
    assert one(c).reason == "out_of_scope_event"
    ok = one({**c, "scope": "context"})
    assert ok.ok
    assert "Other recorded events" in publish(env({**c, "scope": "context"}), P).text


def test_elapsed_computed_by_code_ignores_model_number():
    r = one({"kind": "calculation", "op": "elapsed", "seconds": 5,
             "witness_ids": ["w_on", "w_off"]})
    assert r.ok and 12700 < r.facts["seconds"] < 12710


def test_correlation_labelled_and_windowed():
    r = one({"kind": "correlation", "witness_ids": ["w_fp", "w_off"]})
    assert r.ok and abs(r.facts["lag_s"] - 19.087) < 0.01
    t = publish(env({"kind": "correlation", "witness_ids": ["w_fp", "w_off"]}), P).text
    assert "inactive" in t and "not shown to be the cause" in t


def test_cause_disclosure_cannot_be_omitted():
    t = publish(env({"kind": "observed_value", "entity": "L2", "attribute": "switch",
                     "value": "off", "witness_ids": ["w_off"]}), P).text
    assert "What initiated the change is not established" in t


def test_repair_uses_codes_only_then_floor():
    bad = env({"kind": "observed_value", "entity": "L2", "attribute": "switch",
               "value": "on", "witness_ids": ["w_off"]})
    seen = []
    pub = publish(bad, P, repair=lambda codes: seen.append(codes) or bad)
    assert seen == [[("observed_value", "value_mismatch")]]
    assert pub.downgraded and pub.attempts == 2
    assert "could not be verified" in pub.text


def test_malformed_envelope_floor():
    pub = publish("garbage", P)
    assert pub.downgraded and "No claims could be verified" in pub.text or "not established" in pub.text.lower()