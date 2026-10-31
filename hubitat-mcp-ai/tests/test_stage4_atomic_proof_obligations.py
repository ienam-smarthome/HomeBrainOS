"""Stage 4I: host-source atomic proof, not invented cause from reviewer votes.

Constructed reference tests only; no real model calls, device control,
source recording or semantic authentication of free text.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from stage4_atomic_proof_obligations import (
    benchmark_stage4i_reference_claims,
    evaluate_stage4i_proof_obligations,
)
from stage4g_github_authored_answers import _synthetic_author_cases


def _case(domain):
    return next(c for c in _synthetic_author_cases() if c["domain"] == domain)


def _claim(prop, fact, witness, *, claim_id="c001", other=None):
    return {
        "claim_id": claim_id,
        "proposition": prop,
        "fact_ids": (
            [] if prop == "packet_limit" else
            [fact["fact_id"], other["fact_id"]] if other else
            [fact["fact_id"]]),
        "witness": witness,
    }


def _bundle(*claims):
    return {"schema": "homebrain-stage4i-proof-bundle.v1", "claims": list(claims)}


def _event_witness(f):
    return {key: f[key] for key in ("kind", "entity_id", "attribute", "value")}


def _clock_witness(f):
    return {key: f[key] for key in ("entity_id", "clock_basis", "time_utc")}


def _event(domain):
    return _case(domain)["packet"]["facts"][0]


def test_genuine_source_command_is_provable_but_physical_effect_is_not():
    packet = _case("heating")["packet"]
    f = packet["facts"][0]
    claims = [
        _claim("recorded_event", f, _event_witness(f)),
        _claim("physical_effect", f, {"entity_id": f["entity_id"]}, claim_id="c002"),
        _claim("absence_of_event", f, {"entity_id": f["entity_id"]}, claim_id="c003"),
        _claim("complete_history", f, {"entity_id": f["entity_id"]}, claim_id="c004"),
    ]
    original = deepcopy(packet)
    result = evaluate_stage4i_proof_obligations(packet, _bundle(*claims))
    assert result["atomic_claim_count"] == 4
    assert result["host_proven_atomic_claims"] == 1
    assert result["unproven_atomic_claims"] == 3
    assert result["by_proposition"]["physical_effect"]["unproven"] == 1
    assert result["publisher_approval"] is False
    assert result["claim_text_meaning_verified"] is False
    assert packet == original


def test_source_record_issuer_is_not_upstream_sensor_or_root_cause():
    packet = _case("lighting")["packet"]
    f = packet["facts"][0]
    assert isinstance(f["issuer_app_id"], str) and f["issuer_app_id"]
    proven = _claim("recorded_issuer", f, {
        "entity_id": f["entity_id"], "issuer_app_id": f["issuer_app_id"]})
    result = evaluate_stage4i_proof_obligations(packet, _bundle(proven))
    assert result["host_proven_atomic_claims"] == 1
    falsified = deepcopy(proven)
    falsified["witness"]["issuer_app_id"] = "another-app"
    result = evaluate_stage4i_proof_obligations(packet, _bundle(falsified))
    assert result["host_proven_atomic_claims"] == 0
    assert result["unproven_atomic_claims"] == 1
    assert result["issuer_is_not_upstream_cause"] is True


def test_fan_off_command_does_not_establish_humidity_trigger_or_motor_shutdown():
    packet = _case("ventilation")["packet"]
    f = packet["facts"][0]
    report = evaluate_stage4i_proof_obligations(packet, _bundle(
        _claim("recorded_event", f, _event_witness(f)),
        _claim("physical_effect", f, {"entity_id": f["entity_id"]}, claim_id="c002"),
    ))
    assert report["host_proven_atomic_claims"] == 1
    assert report["unproven_atomic_claims"] == 1
    assert report["source_event_is_not_physical_confirmation"]


def test_source_clock_and_collector_clock_are_independently_exact():
    packet = _case("history")["packet"]
    f = next(x for x in packet["facts"] if x["kind"] == "reported_state")
    observed = _claim("recorded_clock", f, _clock_witness(f))
    correct = evaluate_stage4i_proof_obligations(packet, _bundle(observed))
    assert correct["host_proven_atomic_claims"] == 1
    shifted = deepcopy(observed)
    shifted["witness"]["clock_basis"] = "independently-source-timestamped"
    assert evaluate_stage4i_proof_obligations(packet, _bundle(
        shifted))["unproven_atomic_claims"] == 1
    shifted = deepcopy(observed)
    shifted["witness"]["time_utc"] = "2030-02-01T00:00:00Z"
    assert evaluate_stage4i_proof_obligations(packet, _bundle(
        shifted))["unproven_atomic_claims"] == 1


def test_genuine_archive_gap_proves_incompleteness_not_no_commands():
    packet = _case("history")["packet"]
    gap = next(x for x in packet["facts"] if x["kind"] == "coverage_limit")
    claim = _claim("recorded_gap", gap, {key: gap[key] for key in (
        "entity_id", "gap_count", "truncated")})
    report = evaluate_stage4i_proof_obligations(packet, _bundle(claim))
    assert report["host_proven_atomic_claims"] == 1
    absence = _claim("absence_of_event", gap, {"entity_id": gap["entity_id"]})
    assert evaluate_stage4i_proof_obligations(
        packet, _bundle(absence))["unproven_atomic_claims"] == 1


def test_two_cited_events_cannot_satisfy_unverified_causal_edge():
    packet = _case("history")["packet"]
    first, second = packet["facts"]
    candidate = _claim("upstream_cause", first, {
        "cause_fact_id": first["fact_id"], "result_fact_id": second["fact_id"],
    }, other=second)
    r = evaluate_stage4i_proof_obligations(packet, _bundle(candidate))
    assert r["unproven_atomic_claims"] == 1
    assert r["model_witness_attestation_is_not_truth"]
    assert not r["publisher_approval"]


@pytest.mark.parametrize("limit", [
    "physical_ack_unverified",
    "root_cause_unverified",
    "history_incomplete",
    "absence_not_authorised",
])
def test_host_policy_limit_is_safely_reportable_but_not_an_absence_fact(limit):
    packet = _case("heating")["packet"]
    claim = _claim("packet_limit", None, {"limit": limit})
    result = evaluate_stage4i_proof_obligations(packet, _bundle(claim))
    assert result["host_proven_atomic_claims"] == 1
    assert result["history_incompleteness_does_not_establish_absence"]


def test_unknown_fake_packet_limit_does_not_prove_anything():
    p = _case("lighting")["packet"]
    claim = _claim("packet_limit", None, {"limit": "full-history-certified"})
    result = evaluate_stage4i_proof_obligations(p, _bundle(claim))
    assert result["unproven_atomic_claims"] == 1


def test_reference_corpus_separately_labelled_from_claim_evaluator():
    cases = []
    for domain in ("lighting", "heating", "ventilation", "history"):
        packet = _case(domain)["packet"]
        f = packet["facts"][0]
        cases.append({"packet": packet,
                      "claim": _claim("recorded_event", f, _event_witness(f))
                      if f["kind"] != "coverage_limit" else
                      _claim("recorded_gap", f, {key: f[key] for key in (
                          "entity_id", "gap_count", "truncated")}),
                      "expected": "proven"})
        cases.append({"packet": packet,
                      "claim": _claim("physical_effect", f, {
                          "entity_id": f["entity_id"]}),
                      "expected": "unproven"})
        cases.append({"packet": packet,
                      "claim": _claim("complete_history", f, {
                          "entity_id": f["entity_id"]}),
                      "expected": "unproven"})
    result = benchmark_stage4i_reference_claims(cases)
    assert result["case_count"] == 12
    assert result["reference_proven_count"] == 4
    assert result["reference_unproven_count"] == 8
    assert result["false_accept_count"] == 0
    assert result["false_reject_count"] == 0
    assert result["independent_live_oracle_authenticated"] is False
    assert result["full_answer_prose_semantically_scored"] is False


@pytest.mark.parametrize("tamper", [
    lambda c: c.update({"proposition": "magic_source_cause"}),
    lambda c: c.update({"claim_id": "Bedroom User 101"}),
    lambda c: c.update({"fact_ids": ["f999", "f999"]}),
    lambda c: c.update({"fact_ids": []}),
    lambda c: c.update({"fact_ids": ["f001"] * 3}),
    lambda c: c.update({"witness": {"value": "off"}}),
    lambda c: c.update({"additional_proof": True}),
])
def test_untrusted_atomic_claim_structures_fail_closed(tamper):
    p = _case("lighting")["packet"]
    f = p["facts"][0]
    claim = _claim("recorded_event", f, _event_witness(f))
    tamper(claim)
    with pytest.raises(ValueError):
        evaluate_stage4i_proof_obligations(p, _bundle(claim))


def test_claim_scope_unknown_fact_is_unproven_not_a_new_fact():
    p = _case("lighting")["packet"]
    f = p["facts"][0]
    claim = _claim("recorded_event", f, _event_witness(f))
    claim["fact_ids"] = ["f888"]
    result = evaluate_stage4i_proof_obligations(p, _bundle(claim))
    assert result["unproven_atomic_claims"] == 1


@pytest.mark.parametrize("tamper", [
    lambda p: p.update({"shadow_only": False}),
    lambda p: p.update({"is_publisher_input_not_publication": False}),
    lambda p: p.update({"physical_acknowledgement_proven": True}),
    lambda p: p.update({"upstream_root_cause_proven": True}),
    lambda p: p.update({"source_history_complete": True}),
    lambda p: p.update({"claims_about_absence_authorised": True}),
    lambda p: p["facts"][0].update({"physical_ack_verified": True}),
    lambda p: p["facts"][0].update({"fact_id": "fXYZ"}),
    lambda p: p["facts"].append(deepcopy(p["facts"][0])),
])
def test_host_source_packet_contract_rejects_forged_certainty(tamper):
    p = deepcopy(_case("lighting")["packet"])
    tamper(p)
    with pytest.raises(ValueError):
        evaluate_stage4i_proof_obligations(p, _bundle(
            _claim("packet_limit", None, {"limit": "root_cause_unverified"})))


def test_reject_mismatched_record_kind_and_attribute_without_prose_regex():
    packet = _case("heating")["packet"]
    fact = packet["facts"][0]
    c = _claim("recorded_event", fact, _event_witness(fact))
    c["witness"]["attribute"] = "switch"
    c["witness"]["kind"] = "reported_state"
    result = evaluate_stage4i_proof_obligations(packet, _bundle(c))
    assert result["unproven_atomic_claims"] == 1


def test_complete_answer_but_unverified_physical_claim_cannot_be_proven():
    p = _case("heating")["packet"]
    f = p["facts"][0]
    claims = [
        _claim("recorded_event", f, _event_witness(f)),
        _claim("physical_effect", f, {"entity_id": f["entity_id"]}, claim_id="c002"),
    ]
    result = evaluate_stage4i_proof_obligations(p, _bundle(*claims))
    assert result["host_proven_atomic_claims"] == 1
    assert result["unproven_atomic_claims"] == 1
    assert result["atomic_claim_extraction_from_prose_verified"] is False


def test_all_reports_aggregate_only_without_ids_raw_text_or_home_secrets():
    p = deepcopy(_case("lighting")["packet"])
    p["facts"][0]["value"] = "PRIVATE-HOUSEHOLD-SOURCE-SECRET"
    c = _claim("recorded_event", p["facts"][0], _event_witness(p["facts"][0]))
    out = json.dumps(evaluate_stage4i_proof_obligations(p, _bundle(c)))
    for sensitive in ("PRIVATE-HOUSEHOLD", "2026-01-01", "Synthetic Controller",
                      '"101"', "f001", "c001", "source_clock", "issuer_app_id"):
        assert sensitive not in out
    assert '"publisher_approval": false' in out


def test_active_agent_and_publisher_do_not_import_stage4i():
    for name in ("app.py", "mcp_agent_orchestrator.py",
                 "final_answer_coordinator.py", "causal_claim_publication.py"):
        assert "stage4_atomic_proof_obligations" not in (
            ROOT / "rootfs" / "app" / name).read_text()
