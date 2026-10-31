"""Stage 4K: source/draft binding, post-hoc label isolation, safety parity."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))

from stage4k_frozen_answer_audit import (
    freeze_stage4k_answer,
    audit_stage4k_frozen_answer,
)
from stage4_narrative_contract import build_stage4_evidence_packet
from test_canonical_investigation_foundation import native_command


def _sample(*, sentence_count=2):
    rows = [native_command("701", issuer="501", label="Heating Coordinator",
                           attribute="command-setHeatingSetpoint")]
    packet = build_stage4_evidence_packet(rows)
    fact = packet["facts"][0]
    assert fact["kind"] == "issued_command"
    claim = {key: fact[key] for key in (
        "fact_id", "kind", "entity_id", "attribute", "value",
        "clock_basis", "time_utc", "issuer_app_id", "physical_ack_verified")}
    sentences = [
        "The heat setpoint command was recorded, and the boiler fired.",
        "The complete record proves nothing else happened.",
    ]
    while len(sentences) < sentence_count:
        sentences.append("The controller command was recorded.")
    draft = {
        "schema": "homebrain-stage4-draft.v1",
        "sections": [{"name": "evidence", "sentences": [
            {"text": text, "citations": [fact["fact_id"]],
             "claims": [deepcopy(claim)]} for text in sentences
        ]}],
    }
    frozen = freeze_stage4k_answer(rows, draft)
    atoms = [
        [
            {"proposition": "recorded_event",
             "fact_ids": [fact["fact_id"]], "limit": None},
            {"proposition": "physical_effect",
             "fact_ids": [fact["fact_id"]], "limit": None},
        ],
        [
            {"proposition": "complete_history",
             "fact_ids": [fact["fact_id"]], "limit": None},
        ],
    ]
    while len(atoms) < sentence_count:
        atoms.append([{
            "proposition": "recorded_event",
            "fact_ids": [fact["fact_id"]], "limit": None,
        }])
    labels = {
        "schema": "homebrain-stage4k-adjudication.v1",
        "draft_sha256": frozen["draft_sha256"],
        "packet_sha256": frozen["packet_sha256"],
        "sentences": [
            {"sentence_sha256": sh, "reference_atoms": atom}
            for sh, atom in zip(frozen["sentence_sha256"], atoms)
        ],
    }
    return rows, draft, frozen, labels


class ReferenceExtractor:
    def __init__(self, draft, labels):
        texts = [s["text"] for sec in draft["sections"]
                 for s in sec["sentences"]]
        self.lookup = {text: deepcopy(label["reference_atoms"])
                       for text, label in zip(texts, labels["sentences"])}
        self.requests = []

    def __call__(self, model, request):
        assert model == "qwen2.5:3b"
        assert "reference_atoms" not in json.dumps(request)
        assert "adjudication" not in request
        self.requests.append(deepcopy(request))
        return {"schema": "homebrain-stage4j-atom-extraction.v1",
                "atoms": deepcopy(self.lookup[request["sentence"]])}


def _audit(rows, draft, frozen, labels, invoke):
    return audit_stage4k_frozen_answer(
        rows, draft, frozen, labels, model="qwen2.5:3b", invoke=invoke)


def test_source_bound_complete_answer_exposes_unverified_prose_not_approved():
    rows, draft, frozen, labels = _sample()
    before = deepcopy((rows, draft, frozen, labels))
    model = ReferenceExtractor(draft, labels)
    report = _audit(rows, draft, frozen, labels, model)
    assert (rows, draft, frozen, labels) == before
    assert report["sentence_count"] == report["valid_responses"] == 2
    assert report["typed_claims_valid"] is True
    assert report["exact_extraction_cases"] == 2
    assert report["reference_atoms"] == 3
    assert report["missed_high_risk_atoms"] == 0
    assert report["host_unproven_high_risk_atoms"] == 2
    assert report["host_proven_extracted_atoms"] == 1
    assert report["exact_draft_and_reconstructed_packet_bound"] is True
    assert not report["publisher_approval"]
    assert not report["unseen_prose_semantics_certified"]
    assert not report["reference_labels_post_generation_independence_authenticated"]
    assert len(model.requests) == 2


def test_partial_atom_extraction_cannot_mask_boiler_or_history_implications():
    rows, draft, frozen, labels = _sample()
    def partial(_model, request):
        if "boiler fired" in request["sentence"]:
            return {"schema": "homebrain-stage4j-atom-extraction.v1",
                    "atoms": [labels["sentences"][0]["reference_atoms"][0]]}
        return {"schema": "homebrain-stage4j-atom-extraction.v1",
                "atoms": []}
    report = _audit(rows, draft, frozen, labels, partial)
    assert report["missed_high_risk_atoms"] == 2
    assert report["missed_atoms"] == 2
    assert report["host_proven_extracted_atoms"] == 1
    assert not report["unsafe_claim_free_publication_certified"]


def test_draft_tampering_after_freeze_is_rejected():
    rows, draft, frozen, labels = _sample()
    edited = deepcopy(draft)
    edited["sections"][0]["sentences"][0]["text"] += " Definitely!"
    with pytest.raises(ValueError, match="frozen"):
        _audit(rows, edited, frozen, labels, lambda *_: None)


def test_host_receipt_tampering_after_freeze_is_rejected():
    rows, draft, frozen, labels = _sample()
    changed = [native_command("702", issuer="501", label="Heating Coordinator",
                              attribute="command-setHeatingSetpoint")]
    with pytest.raises(ValueError, match="frozen"):
        _audit(changed, draft, frozen, labels, lambda *_: None)


def test_duplicate_or_unbound_labels_cannot_bypass_scope_check():
    rows, draft, frozen, labels = _sample()
    for edit in ("remove", "swap", "extra"):
        candidate = deepcopy(labels)
        if edit == "remove":
            candidate["sentences"].pop()
        elif edit == "swap":
            candidate["sentences"].reverse()
        else:
            candidate["sentences"][0]["extra_text"] = "invented"
        with pytest.raises(ValueError):
            _audit(rows, draft, frozen, candidate, lambda *_: None)
    candidate = deepcopy(labels)
    candidate["sentences"][0]["reference_atoms"][0]["fact_ids"] = ["f999"]
    with pytest.raises(ValueError):
        _audit(rows, draft, frozen, candidate, lambda *_: None)


def test_no_false_safe_result_on_model_failure_or_empty_atoms():
    rows, draft, frozen, labels = _sample()
    def fail(*_):
        raise RuntimeError("PRIVATE-SECRET-DO-NOT-LOG")
    report = _audit(rows, draft, frozen, labels, fail)
    assert report["invocation_errors"] == 2
    assert report["missed_high_risk_atoms"] == 2
    assert report["valid_responses"] == 0
    assert "PRIVATE-SECRET" not in json.dumps(report)


def test_full_16_sentences_aggregate_without_stage4j_batch_limit():
    rows, draft, frozen, labels = _sample(sentence_count=16)
    def extract(_model, req):
        atoms = [
            {"proposition": "recorded_event",
             "fact_ids": ["f001"], "limit": None}
        ]
        if "boiler fired" in req["sentence"]:
            atoms.append({"proposition": "physical_effect",
                          "fact_ids": ["f001"], "limit": None})
        elif "complete record" in req["sentence"]:
            atoms = [{"proposition": "complete_history",
                      "fact_ids": ["f001"], "limit": None}]
        return {"schema": "homebrain-stage4j-atom-extraction.v1", "atoms": atoms}
    report = _audit(rows, draft, frozen, labels, extract)
    assert report["sentence_count"] == 16
    assert report["valid_responses"] == 16
    assert report["exact_extraction_cases"] == 16
    assert report["reference_atoms"] == 17
    assert report["missed_atoms"] == 0


def test_privacy_aggregate_only_and_active_paths_unchanged():
    rows, draft, frozen, labels = _sample()
    result = _audit(rows, draft, frozen, labels, ReferenceExtractor(draft, labels))
    out = json.dumps(result)
    for secret in ("Heating Coordinator", "boiler fired", "701", "501",
                   "f001", "192.168", "2026-"):
        assert secret not in out
    for name in ("app.py", "mcp_agent_orchestrator.py",
                 "final_answer_coordinator.py", "causal_claim_publication.py"):
        assert "stage4k_frozen_answer_audit" not in (
            ROOT / "rootfs" / "app" / name).read_text(encoding="utf-8")
