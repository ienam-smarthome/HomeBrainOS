"""Stage 4A: domain-general, source-typed model-authored narrative contract.

This is an OFFLINE SHADOW protocol. It does not run a model, publish prose,
add MCP tools or replace the existing causal publisher. In particular,
valid source citations do NOT imply the surrounding model-written sentence
is semantically correct. Publishable prose requires a separately reviewed
semantic-evidence validator in a later milestone.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from canonical_investigation_evidence import build_canonical_evidence_view

_MAX_RECEIPTS = 160
_MAX_FACTS = 80
_MAX_SENTENCES = 16
_MAX_CITATIONS_PER_SENTENCE = 4
_MAX_SECTIONS = 5
_SECTION_NAMES = frozenset(("summary", "timeline", "evidence",
                            "limitations", "next_checks"))
_EVENT_KINDS = {
    "reported-state": "reported_state",
    "input-report": "input_report",
    "issued-command": "issued_command",
}
_REASON_CODES = frozenset((
    "invalid_packet", "invalid_draft", "missing_citation",
    "unknown_fact", "claim_kind_mismatch", "subject_mismatch",
    "attribute_mismatch", "value_mismatch", "clock_mismatch",
    "issuer_mismatch", "unverified_physical_ack", "unsupported_factual_kind",
    "invalid_sentence", "too_many_sentences", "duplicate_fact",
))


def build_stage4_evidence_packet(
    receipts: Sequence[Mapping[str, Any]], *,
    max_facts: int = _MAX_FACTS,
) -> dict[str, Any]:
    """Project *only* canonical observations/coverage to a bounded model brief.

    Each fact's ID is assigned by the trusted host from scoped receipts,
    never invented by the model. Identity labels are included only when
    independently qualified by the canonical identity view; conflict fails
    closed. Event source-clock and collector-clock retain their distinction.
    """
    if not isinstance(receipts, (tuple, list)):
        raise ValueError("receipts must be an in-memory sequence")
    max_facts = max(1, min(int(max_facts), _MAX_FACTS))
    view = build_canonical_evidence_view(receipts[:_MAX_RECEIPTS])
    facts: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def put(fact: dict[str, Any]) -> None:
        key = tuple((k, fact.get(k)) for k in sorted(fact) if k != "fact_id")
        if key in seen:
            return
        seen.add(key)
        if len(facts) < max_facts:
            facts.append({"fact_id": f"f{len(facts) + 1:03}", **fact})

    for event in view.events:
        if event.role not in _EVENT_KINDS:
            continue
        put({
            "kind": _EVENT_KINDS[event.role],
            "entity_id": event.entity_id,
            "attribute": event.attribute,
            "value": event.value,
            "clock_basis": event.clock_basis,
            "time_utc": event.time_utc,
            "source": event.source,
            "issuer_app_id": event.issuer_app_id,
            # This always stays false until independent physical proof exists.
            "physical_ack_verified": False,
        })
    for coverage in view.coverage:
        put({
            "kind": "coverage_limit",
            "entity_id": coverage.entity_id,
            "source": coverage.source,
            "gap_count": coverage.gap_count,
            "truncated": coverage.truncated,
            "complete": False,
        })
    labels: list[dict[str, str]] = []
    for identity in view.identities:
        verified = view.verified_label(identity.kind, identity.entity_id)
        if not verified:
            continue
        row = {"kind": identity.kind, "entity_id": identity.entity_id,
               "label": verified}
        if row not in labels and len(labels) < 32:
            labels.append(row)
    source_items = len({tuple((k, item.get(k)) for k in sorted(item))
                        for item in (
                            [{
                                "kind": _EVENT_KIN[e.role],
                                "entity_id": e.entity_id,
                                "attribute": e.attribute,
                                "value": e.value,
                                "clock_basis": e.clock_basis,
                                "time_utc": e.time_utc,
                                "source": e.source,
                                "issuer_app_id": e.issuer_app_id,
                                "physical_ack_verified": False,
                            } for e in view.events if e.role in _EVENT_KINDS]
                            + [{
                                "kind": "coverage_limit",
                                "entity_id": c.entity_id,
                                "source": c.source,
                                "gap_count": c.gap_count,
                                "truncated": c.truncated,
                                "complete": False,
                            } for c in view.coverage]
                        )})
    return {
        "schema": "homebrain-stage4-evidence-packet.v1",
        "shadow_only": True,
        "facts": facts,
        "verified_labels": labels,
        "facts_total": source_items,
        "facts_omitted": max(0, source_items - len(facts)),
        "receipts_omitted": max(0, len(receipts) - _MAX_RECEIPTS),
        "physical_acknowledgement_proven": False,
        "upstream_root_cause_proven": False,
        "source_history_complete": False,
        "claims_about_absence_authorised": False,
        "is_publisher_input_not_publication": True,
    }


def stage4_model_authoring_instructions(packet: Mapping[str, Any]) -> str:
    """A general, non-room-specific *proposal* prompt, never active routing."""
    if (not isinstance(packet, Mapping)
            or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"):
        raise ValueError("invalid source packet")
    return (
        "Draft a clear, concise, natural-language investigation answer in JSON "
        "schema homebrain-stage4-draft.v1. Use only the attached host evidence "
        "packet for factual claims. The model chooses relevant facts, paragraph "
        "order and sentence wording; do not invent events, commands, names, "
        "times or root causes. Each factual sentence needs a 'citations' array "
        "of exact host fact IDs and a 'claims' array with typed, exact "
        "fact assertions (kind, entity_id, attribute, value, clock_basis, "
        "issuer_app_id where applicable); the citation and assertion must "
        "refer to the same evidence record. Sections may be summary, timeline, "
        "evidence, limitations or next_checks. Clearly separate source-reported "
        "from collector-received timestamps; a reported state is not a "
        "physical ACK, a notification is not a command issuer, and missing "
        "history is not evidence of absence. This draft is a proposal, not "
        "automatically published. The host will validate the structured "
        "assertions independently, and a later semantic review is required "
        "before any authored prose can replace the existing answer."
    )


def validate_stage4_model_draft(
    draft: Any,
    packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Check all typed assertions against packet facts. NEVER attest prose.

    A sentence with no factual claims is not accepted as a verified factual
    answer. Citation IDs and claim attributes must match exactly. Content
    semantics are NOT judged by this validator, even for a perfect envelope.
    The result has no draft prose, device names, event values or timestamps.
    """
    reasons: list[str] = []
    supported = 0
    total = 0
    factual_sentences = 0

    def reject(reason: str) -> None:
        if reason in _REASON_CODES and reason not in reasons:
            reasons.append(reason)

    if (not isinstance(packet, Mapping)
            or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"
            or packet.get("shadow_only") is not True
            or not isinstance(packet.get("facts"), list)):
        reject("invalid_packet")
    if (not isinstance(draft, Mapping)
            or draft.get("schema") != "homebrain-stage4-draft.v1"
            or set(draft) != {"schema", "sections"}
            or not isinstance(draft.get("sections"), list)
            or not 1 <= len(draft["sections"]) <= _MAX_SECTIONS):
        reject("invalid_draft")
    if reasons:
        return _result(reasons, total, supported, factual_sentences)
    witness = {
        item["fact_id"]: item for item in packet["facts"][:_MAX_FACTS]
        if isinstance(item, Mapping)
        and isinstance(item.get("fact_id"), str)
        and item.get("kind") in (*_EVENT_KINDS.values(), "coverage_limit")
    }
    count = 0
    for section in draft["sections"]:
        if (not isinstance(section, Mapping)
                or set(section) != {"name", "sentences"}
                or section.get("name") not in _SECTION_NAMES
                or not isinstance(section.get("sentences"), list)):
            reject("invalid_sentence")
            continue
        for row in section["sentences"]:
            count += 1
            if count > _MAX_SENTENCES:
                reject("too_many_sentences")
                break
            if (not isinstance(row, Mapping)
                    or set(row) != {"text", "citations", "claims"}
                    or not isinstance(row.get("text"), str)
                    or not 1 <= len(row["text"]) <= 600
                    or "\x00" in row["text"]
                    or not isinstance(row.get("citations"), list)
                    or not isinstance(row.get("claims"), list)):
                reject("invalid_sentence")
                continue
            cites = row["citations"]
            assertions = row["claims"]
            if (not cites or len(cites) > _MAX_CITATIONS_PER_SENTENCE
                    or len(cites) != len(set(str(i) for i in cites))
                    or any(not isinstance(c, str) for c in cites)):
                reject("missing_citation")
                continue
            if not assertions or len(assertions) != len(cites):
                reject("invalid_sentence")
                continue
            if not all(isinstance(a, Mapping) for a in assertions):
                reject("invalid_sentence")
                continue
            factual_sentences += 1
            claimed_ids: set[str] = set()
            for claim in assertions:
                total += 1
                ref = claim.get("fact_id")
                if not isinstance(ref, str) or ref not in cites:
                    reject("missing_citation")
                    continue
                if ref in claimed_ids:
                    reject("duplicate_fact")
                    continue
                claimed_ids.add(ref)
                actual = witness.get(ref)
                if actual is None:
                    reject("unknown_fact")
                    continue
                kind = claim.get("kind")
                if kind != actual.get("kind"):
                    reject("claim_kind_mismatch")
                    continue
                if kind in _EVENT_KINDS.values():
                    fields = {"fact_id", "kind", "entity_id", "attribute", "value",
                              "clock_basis", "time_utc", "issuer_app_id",
                              "physical_ack_verified"}
                elif kind == "coverage_limit":
                    fields = {"fact_id", "kind", "entity_id", "source",
                              "gap_count", "truncated", "complete"}
                else:
                    reject("unsupported_factual_kind")
                    continue
                if set(claim) != fields:
                    reject("invalid_sentence")
                    continue
                mismatched = False
                for field, reason in (
                    ("entity_id", "subject_mismatch"),
                    ("attribute", "attribute_mismatch"),
                    ("value", "value_mismatch"),
                    ("clock_basis", "clock_mismatch"),
                    ("time_utc", "clock_mismatch"),
                    ("issuer_app_id", "issuer_mismatch"),
                    ("source", "invalid_sentence"),
                    ("gap_count", "value_mismatch"),
                    ("truncated", "value_mismatch"),
                    ("complete", "value_mismatch"),
                ):
                    if field in fields and claim.get(field) != actual.get(field):
                        reject(reason)
                        mismatched = True
                if kind in _EVENT_KINDS.values() and claim.get("physical_ack_verified") is not False:
                    reject("unverified_physical_ack")
                    mismatched = True
                if not mismatched:
                    supported += 1
            if set(cites) != claimed_ids:
                reject("missing_citation")
        if count > _MAX_SENTENCES:
            break
    if not factual_sentences:
        reject("missing_citation")
    return _result(reasons, total, supported, factual_sentences)


def _result(
    reasons: list[str], total: int, supported: int, factual_sentences: int,
) -> dict[str, Any]:
    return {
        "schema": "homebrain-stage4-typed-draft-verdict.v1",
        "structured_claims_valid": bool(total and total == supported and not reasons),
        "claims_total": total, "claims_supported": supported,
        "claims_rejected": max(0, total - supported),
        "factual_sentences_with_citations": factual_sentences,
        "reason_codes": sorted(reasons)[:12],
        "prose_semantically_verified": False,
        "published": False,
        "safe_to_replace_existing_answer": False,
        "upstream_cause_or_physical_ack_proven": False,
        "offline_shadow_only": True,
    }


__all__ = [
    "build_stage4_evidence_packet",
    "stage4_model_authoring_instructions",
    "validate_stage4_model_draft",
]
