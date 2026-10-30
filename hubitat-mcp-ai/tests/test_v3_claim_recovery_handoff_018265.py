"""V3 D1 claim pilot survives the source-recovery evidence handoff.

In real historic requests the initial unified evidence instruction can be
composed before archived switch rows are present. This regression tests the
SAME pilot in the recovered-journal checkpoint without altering publication.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from test_evidence_driven_discovery_cycle_018255 import (
    receipts as fixtures, QUESTION, journal,
)
from causal_claim_pilot import render_shadow_claim_pilot
from unified_investigation_bridge import (
    collect_unified_evidence, unified_investigation_instruction,
)
from investigation_evidence_cycle import cross_source_discovery_checkpoint
from causal_claim_attestation import validate_claim_envelope


def _facts(rows):
    result = collect_unified_evidence(rows, QUESTION)
    assert result is not None
    return result


def test_pilot_offered_by_recovery_checkpoint_when_initial_history_was_empty():
    initial = fixtures(with_journal=False)
    assert render_shadow_claim_pilot(_facts(initial)) == ""
    assert cross_source_discovery_checkpoint(initial, QUESTION) is None
    recovered = fixtures(with_journal=True)
    packet = cross_source_discovery_checkpoint(recovered, QUESTION)
    assert packet is not None
    assert "HOST OPTIONAL SHADOW CLAIM ATTESTATION" in packet
    assert '"schema":"homebrain-claims.v1"' in packet
    assert "w_" in packet
    assert "Choose only available, authorized READ tools" in packet
    assert "Do not invent sensor IDs" in packet
    assert "root cause" not in packet.lower() or "unverified" in packet.lower()
    assert len(packet) < 14000


def test_same_witness_contract_at_initial_and_recovery_stages():
    rows = fixtures(with_journal=True)
    original = unified_investigation_instruction(rows, QUESTION)
    recovered = cross_source_discovery_checkpoint(rows, QUESTION)
    assert original and recovered
    for string in (
        "HOST OPTIONAL SHADOW CLAIM ATTESTATION",
        "homebrain-claims.v1",
        "matched_hubitat_on_command",
        "upstream_cause_unverified",
    ):
        assert string in original
        assert string in recovered
    a = render_shadow_claim_pilot(_facts(rows))
    assert original.endswith(a) and recovered.endswith(a)


def test_recovery_claim_catalog_contains_both_verified_target_ids():
    rows = fixtures(with_journal=True)
    pilot = render_shadow_claim_pilot(_facts(rows))
    assert '"device_id":"101"' in pilot
    assert '"device_id":"102"' in pilot
    assert "journal_source_switch_on" in pilot
    assert "setLevel can establish" not in pilot


def test_collector_only_cannot_activate_claim_pilot():
    rows = fixtures(with_journal=False) + [
        journal(101, with_source=False), journal(102, with_source=False),
    ]
    assert render_shadow_claim_pilot(_facts(rows)) == ""
    assert cross_source_discovery_checkpoint(rows, QUESTION) is None


def test_single_source_target_cannot_trigger_multi_target_pilot():
    rows = fixtures(with_journal=False) + [journal(101)]
    facts = _facts(rows)
    assert render_shadow_claim_pilot(facts) == ""
    # A checkpoint for a single history may exist as general evidence;
    # its prompt must not assert a two-target attestation pilot.
    checkpoint = cross_source_discovery_checkpoint(rows, QUESTION) or ""
    assert "HOST OPTIONAL SHADOW CLAIM ATTESTATION" not in checkpoint


def test_optional_shadow_only_does_not_certify_free_form_cause():
    ledger = _facts(fixtures(with_journal=True))["v3_witness_ledger"]
    sample = {
        "schema": "homebrain-claims.v1",
        "claims": [{
            "kind": "upstream_cause_unverified", "device_id": "101",
            "witness_ids": [],
        }],
    }
    result = validate_claim_envelope(sample, ledger)
    assert result["valid"] is True
    assert result["prose_verified"] is False
