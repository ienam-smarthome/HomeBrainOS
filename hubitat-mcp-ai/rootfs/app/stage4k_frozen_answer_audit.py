"""Stage 4K: freeze and evaluate whole authored answers against post-hoc labels.

Offline only. Rebuild the source packet from supplied canonical READ receipts;
do not accept a model-supplied packet. Freeze the exact answer before adding
per-sentence reference annotations. Then reuse the Stage 4J atom extractor and
Stage 4I host proof obligations. Reference labels are withheld from the model,
but this code CANNOT verify who annotated them or authenticate the receipts.

Neither semantic completeness nor publication is certified, even with a
perfect result. No active imports, MCP/LLM adapter implementation, or IO.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

from stage4_atomic_proof_obligations import _host_packet
from stage4_narrative_contract import (
    build_stage4_evidence_packet,
    validate_stage4_model_draft,
)
from stage4_prose_atom_coverage import evaluate_stage4j_prose_claim_coverage

_MAX_SENTENCES = 16
_MAX_TEXT = 500
_MAX_ATOMS = 5
_SHA_LEN = 64


def _digest(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("unserialisable frozen input") from exc
    return sha256(encoded).hexdigest()


def _sentences(draft: Any) -> list[str]:
    if (not isinstance(draft, Mapping)
            or set(draft) != {"schema", "sections"}
            or draft["schema"] != "homebrain-stage4-draft.v1"
            or not isinstance(draft["sections"], list)
            or not 1 <= len(draft["sections"]) <= 5):
        raise ValueError("invalid Stage 4A authored draft")
    result: list[str] = []
    for section in draft["sections"]:
        if (not isinstance(section, Mapping)
                or set(section) != {"name", "sentences"}
                or section["name"] not in {
                    "summary", "timeline", "evidence", "limitations", "next_checks"}
                or not isinstance(section["sentences"], list)):
            raise ValueError("invalid authored section")
        for item in section["sentences"]:
            if (not isinstance(item, Mapping)
                    or set(item) != {"text", "citations", "claims"}
                    or not isinstance(item["text"], str)
                    or not 1 <= len(item["text"]) <= _MAX_TEXT
                    or not item["text"].strip()
                    or "\x00" in item["text"]
                    or not isinstance(item["citations"], list)
                    or not isinstance(item["claims"], list)):
                raise ValueError("invalid authored sentence")
            result.append(item["text"])
            if len(result) > _MAX_SENTENCES:
                raise ValueError("too many authored sentences")
    if not result:
        raise ValueError("empty authored answer")
    return result


def freeze_stage4k_answer(receipts: Sequence[Mapping[str, Any]],
                          draft: Mapping[str, Any]) -> dict[str, Any]:
    """Bind a complete draft and host-recomputed source facts by digest.

    This captures a reproducible snapshot, NOT a signed attestation that the
    receipts or draft came from a trusted live service. No prose is returned.
    """
    sentences = _sentences(draft)
    packet = build_stage4_evidence_packet(receipts)
    _host_packet(packet)
    return {
        "schema": "homebrain-stage4k-frozen-answer.v1",
        "draft_sha256": _digest(draft),
        "packet_sha256": _digest(packet),
        "sentence_sha256": [
            _digest({"index": i, "sentence": sentence})
            for i, sentence in enumerate(sentences)
        ],
        "sentence_count": len(sentences),
    }


def audit_stage4k_frozen_answer(
    receipts: Sequence[Mapping[str, Any]],
    draft: Mapping[str, Any],
    frozen: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    *, model: str, invoke: Callable[[str, Mapping[str, Any]], Any],
) -> dict[str, Any]:
    """Score post-generation labels without giving them to the extractor.

    This is an evaluation of the *provided* labels and text, not proof the
    labels were authored after the model answer or independently reviewed.
    Inference failures count as missed propositions, not safe results.
    """
    expected = freeze_stage4k_answer(receipts, draft)
    if not isinstance(frozen, Mapping) or dict(frozen) != expected:
        raise ValueError("frozen answer or source packet does not match")
    if (not isinstance(adjudication, Mapping)
            or set(adjudication) != {
                "schema", "draft_sha256", "packet_sha256", "sentences"}
            or adjudication["schema"] != "homebrain-stage4k-adjudication.v1"
            or adjudication["draft_sha256"] != expected["draft_sha256"]
            or adjudication["packet_sha256"] != expected["packet_sha256"]
            or not isinstance(adjudication["sentences"], list)
            or len(adjudication["sentences"]) != expected["sentence_count"]):
        raise ValueError("adjudication does not match frozen source and answer")
    texts = _sentences(draft)
    packet = build_stage4_evidence_packet(receipts)
    cases = []
    for i, (sentence, annotation) in enumerate(zip(texts, adjudication["sentences"])):
        if (not isinstance(annotation, Mapping)
                or set(annotation) != {"sentence_sha256", "reference_atoms"}
                or annotation["sentence_sha256"] != expected["sentence_sha256"][i]
                or not isinstance(annotation["reference_atoms"], list)
                or not 1 <= len(annotation["reference_atoms"]) <= _MAX_ATOMS):
            raise ValueError("sentence reference missing or unbound")
        cases.append({
            "sentence": sentence,
            "packet": packet,
            "reference_atoms": annotation["reference_atoms"],
        })
    # The established Stage 4J evaluator caps batches at 12. Chunking
    # preserves weighted totals across up to 16 complete draft sentences.
    counts: Counter[str] = Counter()
    metrics = (
        "invocation_attempts", "responses_received", "invocation_errors",
        "valid_responses", "invalid_responses", "reference_atoms",
        "reference_high_risk_atoms", "extracted_atoms",
        "correctly_extracted_atoms", "missed_atoms", "extra_atoms",
        "missed_high_risk_atoms", "exact_extraction_cases",
        "host_proven_extracted_atoms", "host_unproven_extracted_atoms",
        "host_unproven_high_risk_atoms", "proof_errors",
    )
    for start in range(0, len(cases), 12):
        result = evaluate_stage4j_prose_claim_coverage(
            cases[start:start + 12], model=model, invoke=invoke)
        for key in metrics:
            counts[key] += result[key]
    typed = validate_stage4_model_draft(draft, packet)
    return {
        "schema": "homebrain-stage4k-post-generation-audit.v1",
        "offline_only": True,
        "sentence_count": len(texts),
        "typed_claims_valid": typed["structured_claims_valid"],
        "typed_claims_total": typed["claims_total"],
        "typed_claims_supported": typed["claims_supported"],
        "typed_reason_codes": typed["reason_codes"],
        **{key: counts[key] for key in metrics},
        "extraction_recall": (
            round(counts["correctly_extracted_atoms"] / counts["reference_atoms"], 4)
            if counts["reference_atoms"] else None),
        "extraction_precision": (
            round(counts["correctly_extracted_atoms"] / counts["extracted_atoms"], 4)
            if counts["extracted_atoms"] else None),
        "reference_labels_post_generation_independence_authenticated": False,
        "reference_labels_live_truth_authenticated": False,
        "supplied_receipts_external_provenance_authenticated": False,
        "exact_draft_and_reconstructed_packet_bound": True,
        "unseen_prose_semantics_certified": False,
        "unsafe_claim_free_publication_certified": False,
        "publisher_approval": False,
        "active_agent_changed": False,
        "device_actions_executed": False,
    }


__all__ = ["freeze_stage4k_answer", "audit_stage4k_frozen_answer"]
