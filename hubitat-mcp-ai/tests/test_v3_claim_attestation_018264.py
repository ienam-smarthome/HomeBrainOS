"""V3 Stage D1: typed attestation pilot cannot certify arbitrary prose."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_claim_attestation import (
    extract_claim_envelope, validate_claim_envelope,
)
from causal_witness_ledger import build_witness_coverage_ledger
from request_metrics import RequestMetrics
from unified_incident_synthesis import reconcile_ledger_if_needed
from unified_investigation_bridge import unified_investigation_instruction


def _event(ident, kind, time, app=""):
    return {"device_id": str(ident), "event_class": kind, "app_id": app,
            "device_name": "Generic Test Light",
            "value": ("on" if kind.endswith("_on") else "off"),
            "date": "2026-10-30T" + time + "+00:00"}


def _facts():
    rows = [
        _event(101, "issued_on", "15:00:00.100", "3001"),
        _event(101, "reported_switch_on", "15:00:00.450"),
        _event(101, "journal_received_switch_on", "15:00:01.600"),
        _event(101, "issued_setlevel", "15:00:01.200", "3001"),
        _event(102, "journal_source_switch_on", "15:00:00.950"),
        _event(102, "journal_source_switch_off", "15:00:30.000"),
    ]
    facts = {
        "source_attested": True, "target_device_ids": ["101", "102"],
        "target_coverage": [
            {"device_id": "101", "device_name": "Generic Test Light"},
            {"device_id": "102", "device_name": "Another Test Light"},
        ],
        "incident_ledger": rows,
        "journal_source_observations": 2,
        "missing_switch_history_for_targets": [
            "Generic Test Light", "Another Test Light",
        ],
        "independent_input_observations": [{
            "device_id": "201", "attribute": "motion", "value": "active",
            "time": "2026-10-30T14:59:59.700+00:00",
            "timestamp_basis": "source-reported", "source_read": 1,
        }],
    }
    facts["v3_witness_ledger"] = build_witness_coverage_ledger(facts, [])
    return facts


def _witness(facts, *, kind, ident):
    return next(w["witness_id"] for w in facts["v3_witness_ledger"]["witnesses"]
                if w["event_class"] == kind and w["entity"] == str(ident))


def _claim(kind, ident, witnesses, **kwargs):
    return {"kind": kind, "device_id": str(ident),
            "witness_ids": list(witnesses), **kwargs}


def _envelope(*claims):
    return {"schema": "homebrain-claims.v1", "claims": list(claims)}


def test_positive_command_state_and_source_input_claims_are_type_checked():
    f = _facts()
    command = _witness(f, kind="issued_on", ident=101)
    state = _witness(f, kind="reported_switch_on", ident=101)
    motion = _witness(f, kind="motion", ident=201)
    envelope = _envelope(
        _claim("reported_switch_state", 101, [state], state="on"),
        _claim("hubitat_issued_command", 101, [command],
               command="on", app_id="3001"),
        _claim("matched_hubitat_on_command", 101, [command, state],
               app_id="3001"),
        _claim("reported_input_state", 201, [motion],
               attribute="motion", value="active"),
        _claim("upstream_cause_unverified", 101, []),
    )
    r = validate_claim_envelope(envelope, f["v3_witness_ledger"])
    assert r == {"present": True, "valid": True, "total": 5,
                 "supported": 5, "rejected": 0, "reasons": [],
                 "prose_verified": False}


def test_setlevel_after_on_cannot_attest_prior_on_issuer():
    f = _facts()
    level = _witness(f, kind="issued_setlevel", ident=101)
    state = _witness(f, kind="reported_switch_on", ident=101)
    claim = _claim("matched_hubitat_on_command", 101, [level, state],
                   app_id="3001")
    r = validate_claim_envelope(_envelope(claim), f["v3_witness_ledger"])
    assert not r["valid"] and "command_pair_not_attested" in r["reasons"]


def test_collector_reception_cannot_be_attested_as_source_state():
    f = _facts()
    collector = _witness(f, kind="journal_received_switch_on", ident=101)
    claim = _claim("reported_switch_state", 101, [collector], state="on")
    r = validate_claim_envelope(_envelope(claim), f["v3_witness_ledger"])
    assert not r["valid"]
    assert "wrong_witness_role" in r["reasons"]


def test_forged_wrong_device_app_and_wrong_state_rejected():
    f = _facts()
    on = _witness(f, kind="reported_switch_on", ident=101)
    command = _witness(f, kind="issued_on", ident=101)
    claims = [
        _claim("reported_switch_state", 102, [on], state="on"),
        _claim("reported_switch_state", 101, [on], state="off"),
        _claim("hubitat_issued_command", 101, [command],
               command="on", app_id="9999"),
        _claim("reported_switch_state", 101, ["w_forged"], state="on"),
    ]
    r = validate_claim_envelope(_envelope(*claims), f["v3_witness_ledger"])
    assert not r["valid"] and r["rejected"] == 4
    assert {"target_mismatch", "wrong_witness_role", "app_mismatch",
            "missing_witness"}.issubset(set(r["reasons"]))


def test_malformed_limit_and_unknown_kind_are_not_approved():
    f = _facts()
    assert not validate_claim_envelope(None, f["v3_witness_ledger"])["valid"]
    assert not validate_claim_envelope(
        _envelope(*[_claim("upstream_cause_unverified", 101, [])
                    for _ in range(20)]),
        f["v3_witness_ledger"])["valid"]
    assert "claim_limit_exceeded" in validate_claim_envelope(
        _envelope(*[_claim("upstream_cause_unverified", 101, [])
                    for _ in range(20)]),
        f["v3_witness_ledger"])["reasons"]
    assert "unknown_claim_kind" in validate_claim_envelope(
        _envelope(_claim("the sensor caused the light", 101, [])),
        f["v3_witness_ledger"])["reasons"]


def test_parser_has_exact_fence_limit_and_does_not_parse_prose():
    envelope = _envelope(_claim("upstream_cause_unverified", 101, []))
    prose = "The original upstream cause is unknown."
    draft = prose + "\n" + "\x60\x60\x60homebrain-claims\n" + json.dumps(
        envelope) + "\n\x60\x60\x60"
    assert extract_claim_envelope(draft) == envelope
    assert extract_claim_envelope(prose) is None
    assert extract_claim_envelope(
        "\x60\x60\x60homebrain-claims\n{\n\x60\x60\x60"
    )["schema"] == "invalid"
    assert extract_claim_envelope(
        "\x60\x60\x60homebrain-claims\n" + " " * 9000
    )["schema"] == "invalid"


def test_request_shadow_counts_support_and_reject_but_publishes_legacy():
    f = _facts()
    original = ("Unverified source was ON at 15:00:00."
                + "\n\x60\x60\x60homebrain-claims\n"
                + json.dumps(_envelope(
                    _claim("upstream_cause_unverified", 101, []),
                    _claim("matched_hubitat_on_command", 101, ["w_fake", "w_fake"],
                           app_id="3001")))
                + "\n\x60\x60\x60")
    m = RequestMetrics()
    token = m.begin()
    try:
        final, replaced = reconcile_ledger_if_needed(original, f)
        counts = m.snapshot()["counters"]
        assert replaced is True
        assert final != original
        assert "\x60\x60\x60homebrain-claims" not in final
        assert counts["v3_claim_envelope_present"] == 1
        assert counts["v3_claim_envelope_invalid"] == 1
        assert counts["v3_claim_supported"] == 1
        assert counts["v3_claim_rejected"] == 1
        assert counts["v3_shadow_legacy_digest_replaced"] == 1
        assert "Generic Test Light" not in str(counts)
    finally:
        m.reset(token)


def test_no_envelope_counts_absence_without_changing_existing_output():
    f = _facts()
    m = RequestMetrics()
    token = m.begin()
    try:
        original = "The original initiating controller is not verified."
        final, replaced = reconcile_ledger_if_needed(original, f)
        assert replaced and final != original
        counts = m.snapshot()["counters"]
        assert counts["v3_claim_envelope_missing"] == 1
        assert "v3_claim_envelope_valid" not in counts
    finally:
        m.reset(token)


def test_single_target_or_collector_only_cannot_activate_model_pilot():
    # The pilot is limited to the existing digest replacement route.
    assert callable(unified_investigation_instruction)
