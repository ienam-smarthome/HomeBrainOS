"""V3: short source-only witness aliases and evidence-grounded alternatives.

No model-provided alias becomes a source witness unless the *current* ledger
independently resolves it. Long natural-language drafts never gain approval.
"""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_claim_attestation import (
    source_witness_aliases, resolve_source_witness_aliases,
    validate_claim_envelope,
)
from causal_claim_pilot import render_shadow_claim_pilot
from causal_claim_publication import claim_guided_incident_answer
from causal_source_alternatives import source_based_competing_explanations
from shared_investigation_completion import apply_shared_investigation_completion
from test_v3_claim_guided_publication_018270 import facts, complete_envelope, draft
from test_v3_reception_evidence_018267 import replay, QUESTION


def aliased(f):
    envelope = complete_envelope(f)
    reverse = {v: k for k, v in source_witness_aliases(f["v3_witness_ledger"]).items()}
    for claim in envelope["claims"]:
        claim["witness_ids"] = [
            reverse.get(w, w) for w in claim.get("witness_ids") or []
        ]
    return envelope


def test_aliases_are_exact_source_ledger_ids_with_both_targets():
    f = facts()
    aliases = source_witness_aliases(f["v3_witness_ledger"])
    assert set(aliases) == {"w_t1_on", "w_t1_off", "w_t2_on", "w_t2_off"}
    assert all(w.startswith("w_") and len(w) == 16 for w in aliases.values())
    e = aliased(f)
    assert validate_claim_envelope(e, f["v3_witness_ledger"])["valid"]
    normalized = resolve_source_witness_aliases(e, f["v3_witness_ledger"])
    assert normalized["claims"][0]["witness_ids"] == [aliases["w_t1_on"]]
    result, status = claim_guided_incident_answer(draft(e), f)
    assert status == "published"
    assert "No immediate Hubitat ON command" in result
    assert "DEFINITELY" not in result


def test_alias_target_swaps_and_unknown_names_remain_rejected():
    f = facts()
    original = aliased(f)
    bad = copy.deepcopy(original)
    bad["claims"][0]["witness_ids"] = ["w_t2_on"]
    result = validate_claim_envelope(bad, f["v3_witness_ledger"])
    assert not result["valid"] and "target_mismatch" in result["reasons"]
    bad = copy.deepcopy(original)
    bad["claims"][0]["witness_ids"] = ["w_t99_on"]
    result = validate_claim_envelope(bad, f["v3_witness_ledger"])
    assert not result["valid"] and "missing_witness" in result["reasons"]
    assert claim_guided_incident_answer(draft(bad), f)[1] == "invalid_envelope"


def test_aliases_are_rederived_after_renaming_and_never_cached_by_identity():
    f = facts((701, 702, 803, 804, 805))
    e = aliased(f)
    assert validate_claim_envelope(e, f["v3_witness_ledger"])["valid"]
    text, status = claim_guided_incident_answer(draft(e), f)
    assert status == "published" and "Motion sensor (device 803)" in text
    assert "7895" not in text


def test_pilot_shows_short_aliases_not_unnecessarily_long_hashes():
    f = facts()
    prompt = render_shadow_claim_pilot(f, final_synthesis=True)
    assert "w_t1_on" in prompt and "w_t1_off" in prompt
    assert "w_t2_on" in prompt and "w_t2_off" in prompt
    assert "Do not invent" in prompt
    assert "Example envelope" in prompt
    assert len(prompt) < 4000


def test_verified_sensor_contrast_replaces_generic_hypothesis_checklist():
    f = facts()
    rendered = source_based_competing_explanations(f)
    assert rendered
    assert rendered.startswith("**Other explanations considered:**")
    assert "Motion sensor (device 202)" in rendered
    assert "5 of 5 for Motion sensor (device 201)" in rendered
    assert "20 of 160 archived observations" in rendered
    assert "another automation or a bridge" in rendered
    assert "Competing explanations (provisional" not in rendered


def test_shared_completion_respects_explicit_comparison_with_verified_brief():
    sample = replay()
    outcome = SimpleNamespace(
        route="unified-mcp-agent",
        request_class="live-read",
        evidence=sample,
        message="**Most likely mechanism:** Source-verified example.",
        metrics={"outcome": "unresolved", "counters": {
            "v3_source_brief_publications": 1,
        }},
        investigation_coverage={
            "status": "partial-evidence",
            "evidenceComplete": False,
            "questionResolved": False,
            "hypothesisComparisons": [{
                "candidate": "Generic unverified reset theory",
                "discriminating_question": "Was a reset recorded?",
                "source_state": "source-class-not-checked",
                "source_kind": "device_logs",
                "required_origin": "physical",
                "hypothesis_verdict": "unverified",
            }],
        },
    )
    updated = apply_shared_investigation_completion(
        outcome, QUESTION + " Compare competing explanations.")
    assert "**Other explanations considered:**" in updated.message
    assert "Generic unverified reset theory" not in updated.message
    assert "**Competing explanations (provisional" not in updated.message
    assert updated.investigation_coverage["questionResolved"] is False
