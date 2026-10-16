import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from investigation_evidence_ledger import command_facts, reconcile_command_denials
from lockout_claim_consistency import annotate_lockout_disagreement

EVIDENCE = [{"success": True, "details": {"label": "Bedroom 1 Light", "events": [
    {"name": "command-on", "date": "2026-10-12T07:25:37.504+0100",
     "producedBy": {"label": "05. Maker API - HD+", "id": "2355"}},
]}}]

def test_command_ledger_reconciles_false_absence():
    sentence = "No commands issued to the Bedroom 1 Light were identified for the date of 12 October 2026."
    revised, claims = reconcile_command_denials(sentence, EVIDENCE)
    assert len(claims) == 1
    assert "2026-10-12T07:25:37" in revised
    assert "Maker API" in revised
    assert "does not establish" in revised
    assert "No commands issued" not in revised

def test_nonfocal_command_does_not_prove_activation():
    text = "No state change at 08:16 on 12 October was observed."
    revised, claims = reconcile_command_denials(text, EVIDENCE)
    assert revised == text and claims == []

def test_duplicate_receipts_deduplicated():
    assert len(command_facts(EVIDENCE + EVIDENCE)) == 1

def test_failed_receipts_do_not_count():
    assert command_facts([{"success": False, "details": EVIDENCE[0]["details"]}]) == []

def test_lockout_conflict_is_exposed_not_resolved():
    text = "Manual-Off Lockout: Configured for 30 minutes (though the app summary paragraph mentions 300 min)."
    out, conflict = annotate_lockout_disagreement(text)
    assert conflict is not None
    assert conflict["persisted_claim_minutes"] == 30
    assert conflict["summary_claim_minutes"] == 300
    assert "have not been reconciled" in out
