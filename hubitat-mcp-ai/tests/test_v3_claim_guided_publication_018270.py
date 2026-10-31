"""Fail closed: validated typed witnesses never certify arbitrary model prose."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_claim_attestation import validate_claim_envelope
from causal_claim_pilot import render_shadow_claim_pilot
from causal_claim_publication import (
    claim_guided_incident_answer, source_verified_incident_brief,
)
from unified_incident_synthesis import reconcile_ledger_if_needed
from unified_investigation_bridge import collect_unified_evidence
from test_v3_reception_evidence_018267 import replay, QUESTION


def facts(ids=(101, 102, 201, 202, 203)):
    f = collect_unified_evidence(replay(ids), QUESTION)
    assert f
    return f


def complete_envelope(f):
    ledger = f["v3_witness_ledger"]
    claims = []
    for target in f["target_device_ids"]:
        for state in ("on", "off"):
            witness = next(w for w in ledger["witnesses"]
                           if str(w["entity"]) == str(target)
                           and w["event_class"] == "journal_source_switch_" + state
                           and w["clock_basis"] == "source")
            claims.append({"kind": "reported_switch_state",
                           "device_id": str(target), "state": state,
                           "witness_ids": [witness["witness_id"]]})
    claims.append({"kind": "upstream_cause_unverified",
                   "device_id": str(f["target_device_ids"][0]), "witness_ids": []})
    return {"schema": "homebrain-claims.v1", "claims": claims}


def draft(envelope, prefix="The lights were DEFINITELY switched on by app 4013."):
    fence = "\x60" * 3
    return prefix + "\n\n" + fence + "homebrain-claims\n" + json.dumps(envelope) + "\n" + fence


def test_complete_attestation_yields_natural_facts_but_never_raw_model_prose():
    f = facts()
    raw = draft(complete_envelope(f))
    answer, state = claim_guided_incident_answer(raw, f)
    assert state == "published"
    assert answer and "**Most likely mechanism:**" in answer
    assert "Input device 201" in answer
    assert "5/5 active-to-ON and 5/5 inactive-to-OFF" in answer
    assert "North Lamp had 5 reported ON and 5 reported OFF" in answer
    assert "South Lamp had 5 ON and 5 OFF" in answer
    assert "source-timestamped state reports" in answer
    assert "DEFINITELY" not in answer
    assert "\x60\x60\x60" not in answer
    assert "### Reconstructed source-timed sequence" not in answer
    published, changed = reconcile_ledger_if_needed(raw, f)
    assert changed is True and published == answer


def test_bad_issuer_is_rejected_and_original_digest_survives():
    f = facts()
    e = complete_envelope(f)
    e["claims"].append({"kind": "matched_hubitat_on_command",
                        "device_id": f["target_device_ids"][0],
                        "app_id": "4013", "witness_ids": e["claims"][0]["witness_ids"]})
    result = validate_claim_envelope(e, f["v3_witness_ledger"])
    assert result["valid"] is False and result["rejected"] == 1
    assert result["reasons"] == ["command_pair_not_attested"]
    raw = draft(e)
    assert claim_guided_incident_answer(raw, f) == (None, "invalid_envelope")
    published, changed = reconcile_ledger_if_needed(raw, f)
    assert changed is True and published.startswith("**Most likely mechanism:**")
    assert "Input device 201" in published
    assert "### Reconstructed source-timed sequence" not in published
    assert "DEFINITELY" not in published


def test_invalid_model_claims_still_allow_safe_source_only_short_brief():
    f = facts()
    brief = source_verified_incident_brief(f)
    assert brief and brief.startswith("**Most likely mechanism:**")
    raw = "Invented physical confirmation without any claim envelope."
    published, changed = reconcile_ledger_if_needed(raw, f)
    assert changed is True and published == brief
    assert "Invented physical confirmation" not in published
    no_source = copy.deepcopy(f)
    no_source["same_receiver_evidence"]["candidates"] = []
    assert source_verified_incident_brief(no_source) is None
    published, changed = reconcile_ledger_if_needed(raw, no_source)
    assert changed is True
    assert published.startswith("**What happened:**")


def test_missing_envelope_and_partial_coverage_fail_closed():
    f = facts()
    assert claim_guided_incident_answer("Unsupported prose", f) == (
        None, "missing_envelope")
    e = complete_envelope(f)
    e["claims"] = e["claims"][:2] + e["claims"][-1:]
    assert validate_claim_envelope(e, f["v3_witness_ledger"])["valid"] is True
    assert claim_guided_incident_answer(draft(e), f) == (
        None, "incomplete_claim_coverage")
    e = complete_envelope(f)
    e["claims"] = e["claims"][:-1]
    assert claim_guided_incident_answer(draft(e), f) == (
        None, "missing_causal_boundary")


def test_collector_timestamp_cannot_attest_source_state():
    f = facts()
    e = complete_envelope(f)
    reception = next(w for w in f["v3_witness_ledger"]["witnesses"]
                     if w["event_class"] == "journal_received_switch_on"
                     and w["entity"] == f["target_device_ids"][0])
    e["claims"][0]["witness_ids"] = [reception["witness_id"]]
    verdict = validate_claim_envelope(e, f["v3_witness_ledger"])
    assert not verdict["valid"] and verdict["rejected"] == 1
    assert claim_guided_incident_answer(draft(e), f)[1] == "invalid_envelope"


def test_renamed_ids_have_same_result_and_no_phantom_controller():
    f = facts((701, 702, 803, 804, 805))
    text, state = claim_guided_incident_answer(draft(complete_envelope(f)), f)
    assert state == "published" and text
    assert "Input device 803" in text
    assert "7895" not in text and "4013" not in text
    assert "No immediate Hubitat ON command was verified for either target" in text


def test_partial_immediate_on_witness_does_not_create_all_target_denial():
    f = facts()
    f["v3_witness_ledger"]["immediate_hubitat_on_command_matches"] = [
        {"device_id": f["target_device_ids"][0], "hubitat_app_id": "5000"}
    ]
    text, state = claim_guided_incident_answer(
        draft(complete_envelope(f)), f)
    assert state == "published"
    assert "for one target but not both" in text
    assert "No immediate Hubitat ON command" not in text


def test_prompt_offers_both_targets_on_off_and_uncertainty():
    prompt = render_shadow_claim_pilot(facts(), final_synthesis=True)
    assert "Include at least one source-timed ON and OFF" in prompt
    assert "upstream_cause_unverified" in prompt
    assert prompt.count("journal_source_switch_on") >= 2
    assert prompt.count("journal_source_switch_off") >= 2
    assert "legacy safety digest" in prompt


def test_nonqualifying_coverage_preserves_existing_publication():
    f = facts()
    reduced = copy.deepcopy(f)
    reduced["missing_switch_history_for_targets"] = []
    assert claim_guided_incident_answer(draft(complete_envelope(f)), reduced) == (
        None, "not_eligible")
    reduced = copy.deepcopy(f)
    reduced["target_device_ids"] = [f["target_device_ids"][0]]
    assert claim_guided_incident_answer(draft(complete_envelope(f)), reduced) == (
        None, "not_eligible")
