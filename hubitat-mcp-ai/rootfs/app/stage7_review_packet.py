"""Stage 7 independent, human-reviewable synthetic provenance packet.

This is NOT a second model, a semantic truth oracle or a production publisher.
It freezes the exact fictional source universe *after* a successful Stage 6
run so a separate reviewer can examine each natural-language sentence against
both read and skipped records. Host-held benchmark gold/source relevance
labels stay outside the packet. Never accepts arbitrary live MCP evidence.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from stage71_evidence_scope import build_evidence_scope_review
from stage72_answer_coverage import build_answer_coverage_review
from stage75_evidence_answer_review import build_stage75_review
from stage77_relationship_review import build_stage77_review
from stage78_followup_sufficiency import build_stage78_review
from stage79_proof_target_review import build_stage79_review


def _bounded_record(record: dict[str, Any]) -> dict[str, Any]:
    # The scenario catalog is static. Use an explicit allowlist rather than
    # serializing arbitrary future device fields, credentials or metadata.
    allowed = {
        "id", "kind", "synthetic", "device", "state", "received_at",
        "source_time", "at", "clock_basis", "reported_at", "issuer",
        "command", "level", "physical_acknowledgement",
        "driver_connected_to_broker", "proves_plug_online",
        "independent_device_packet", "actual_plug_packet",
        "temperature_c", "timezone", "reviewed_at", "timeout_seconds",
        "gap", "device_confirmation",
    }
    return {k: v for k, v in record.items()
            if k in allowed and isinstance(v, (str, bool, int, float))
            and (not isinstance(v, str) or len(v) <= 180)}


def build_review_packet(
    case_id: str, case: dict[str, Any],
    selected: list[str], draft: dict[str, Any],
) -> dict[str, Any]:
    """Available only for static Stage 6 test cases post-result.

    The model has *already* made all its source choices. Supplying unread
    sources here to the user cannot influence that finished investigation.
    No gold labels/expected conclusions are disclosed by this packet.
    """
    if not (isinstance(case_id, str) and len(case_id) <= 64
            and type(case) is dict
            and type(draft) is dict
            and type(selected) is list
            and len(selected) <= 3):
        raise ValueError("invalid synthetic review inputs")
    sources = case["catalog"]
    ids = {source["id"] for source in sources}
    if len(selected) != len(set(selected)) or any(sid not in ids for sid in selected):
        raise ValueError("unknown synthetic selection")
    records = [{
        "source_id": "INITIAL",
        "title": "Initial focal observation",
        "was_selected_by_model": True,
        "records": [_bounded_record(case["initial"])],
    }]
    for source in sources:
        records.append({
            "source_id": source["id"],
            "title": source["title"],
            "was_selected_by_model": source["id"] in selected,
            "records": [_bounded_record(r) for r in source["records"]],
        })
    sentences = []
    for index, sent in enumerate(draft["sentences"], 1):
        sentences.append({
            "number": index,
            "text": sent["text"],
            "model_supplied_claim_type": sent["kind"],
            "model_supplied_epistemic": (
                dict(sent["epistemic"]) if "epistemic" in sent else None
            ),
            "epistemic_meaning_agrees_with_prose": "not_reviewed",
            "model_cited_evidence_ids": list(sent["evidence_ids"]),
            "model_supplied_atoms": [
                {k: a[k] for k in ("record_id", "field", "value")}
                for a in sent.get("atoms", [])
            ],
            "human_factual_verdict": "not_reviewed",
        })
    # The reference rubric and evidence structure are generated only after
    # the model finishes, not injected into its source or answer prompts.
    scope_review = build_evidence_scope_review(case, selected)
    answer_review = build_answer_coverage_review(case_id, case, selected, draft)
    # Checker is the existing host source-type test, not a prose evaluator.
    from stage6_adaptive_benchmark import _host_proof
    stage75_review = build_stage75_review(
        case, selected, draft, answer_review, _host_proof)
    stage78_review = build_stage78_review(case, selected, draft)
    packet = {
        "schema": "homebrain-stage7-review.v1",
        "case_id": case_id,
        "question": case["question"],
        "source_records": records,
        "author_sentences": sentences,
        "author_uncertainties": list(draft["uncertainties"]),
        "author_suggested_next_evidence": draft["next_evidence"],
        "evidence_scope_review": scope_review,
        "answer_coverage_review": answer_review,
        "stage75_evidence_answer_review": stage75_review,
        "stage77_relationship_review": build_stage77_review(case, selected, answer_review),
        "stage78_followup_sufficiency_review": stage78_review,
        "stage79_proof_target_review": build_stage79_review(draft, stage78_review),
        "suggested_next_evidence_review": {
            "suggestion": draft["next_evidence"],
            "human_review_verdict": "not_reviewed",
            "guidance": (
                "Judge whether this proposed source could establish the "
                "claimed fact, not merely whether it is relevant. A device "
                "packet alone may not identify a command initiator."
            ),
            "automatically_verified": False,
        },
        "reviewer_rubric": {
            "next_evidence_quality": [
                "adequately_scoped", "overstates_what_evidence_proves",
                "insufficient_detail", "unclear",
            ],
            "per_sentence": ["supported", "partially_supported",
                             "unsupported", "uncertain"],
            "overall_completeness": ["adequate", "important_omissions",
                                     "insufficient_information"],
            "causal_calibration": ["appropriate", "overclaims",
                                   "uncertain"],
            "epistemic_prose_alignment": [
                "aligned", "contradicts_declaration", "unclear",
            ],
            "negative_claim_scope": [
                "not_a_negative_claim", "scoped_to_examined_records",
                "overstates_global_absence", "unclear_scope",
            ],
            "question_coverage": [
                "addressed", "omitted", "unverifiable", "unclear",
            ],
        },
        "gold_reference_labels_included": False,
        "all_records_are_fictional": True,
        "unread_sources_only_disclosed_after_model_finished": True,
        "prose_fully_verified": False,
        "independent_human_review_required": True,
        "publisher_approval": False,
    }
    # Reproducible content ID, not a security token, does not imply signing.
    blob = json.dumps(packet, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))
    if len(blob) > 32000:
        raise ValueError("synthetic review packet exceeded bounds")
    packet["review_packet_id"] = hashlib.sha256(
        blob.encode("utf-8")).hexdigest()[:16]
    return packet


__all__ = ["build_review_packet"]
