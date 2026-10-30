"""V3 final-synthesis claim handoff stays source-qualified and shadow-only.

Optional discovery checkpoint offers are not a reliable proxy for the final
model instruction. The final synthesis should receive one explicit claim
format instruction after the normal answer-quality prompts, only when the
legacy source-journal digest boundary already applies.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from test_evidence_driven_discovery_cycle_018255 import (
    receipts as fixture_receipts, QUESTION, journal,
)
from causal_claim_pilot import render_shadow_claim_pilot
from unified_investigation_bridge import collect_unified_evidence
from request_metrics import RequestMetrics


def _facts(rows):
    data = collect_unified_evidence(rows, QUESTION)
    assert data is not None
    return data


def test_final_handoff_requests_envelope_after_natural_language():
    facts = _facts(fixture_receipts(with_journal=True))
    early = render_shadow_claim_pilot(facts)
    final = render_shadow_claim_pilot(facts, final_synthesis=True)
    assert "HOST OPTIONAL SHADOW CLAIM ATTESTATION" in early
    assert "you MAY append one" in early
    assert "HOST FINAL-SYNTHESIS SHADOW CLAIM ATTESTATION" in final
    assert "append exactly one fenced code block" in final
    assert "you MAY append one" not in final
    assert "Natural-language reasoning comes first" in final
    assert "legacy safety digest will still control publication" in final
    assert '"device_id":"101"' in final
    assert '"device_id":"102"' in final
    assert '"schema":"homebrain-claims.v1"' in final
    assert len(final) < 4000


def test_final_handoff_requires_two_source_timed_target_histories():
    assert render_shadow_claim_pilot(
        _facts(fixture_receipts(with_journal=False)),
        final_synthesis=True,
    ) == ""
    collector_only = fixture_receipts(with_journal=False) + [
        journal(101, with_source=False), journal(102, with_source=False),
    ]
    assert render_shadow_claim_pilot(
        _facts(collector_only), final_synthesis=True,
    ) == ""
    one_target = fixture_receipts(with_journal=False) + [journal(101)]
    assert render_shadow_claim_pilot(
        _facts(one_target), final_synthesis=True,
    ) == ""


def test_final_offer_counter_is_allowlisted_and_private():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("v3_claim_pilot_final_offered")
        snapshot = metrics.snapshot()["counters"]
        assert snapshot["v3_claim_pilot_final_offered"] == 1
        assert "device_id" not in str(snapshot)
        assert "w_" not in str(snapshot)
    finally:
        metrics.reset(token)
