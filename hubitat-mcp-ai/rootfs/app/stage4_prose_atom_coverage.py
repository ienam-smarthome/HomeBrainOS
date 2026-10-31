"""Stage 4J: offline coverage audit for claims EXTRACTED from authored prose.

A reviewer/model suggests *which* atomic propositions a sentence asserts.
The host independently projects those proposals onto Stage 4I's source
proof obligations, then a separate, withheld reference annotation measures
whether the extractor MISSED implications (especially causal ones).

No regex on the model's wording, no domain/room keywords, and no semantic
certification: a model may omit, misread, or suppress factual implications.
Even a perfect source-proof score CANNOT approve prose for publication.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Mapping, Sequence

from stage4_atomic_proof_obligations import (
    _host_packet,
    evaluate_stage4i_proof_obligations,
)

_TYPES = frozenset((
    "recorded_event", "recorded_issuer", "recorded_clock", "recorded_gap",
    "packet_limit", "upstream_cause", "physical_effect", "absence_of_event",
    "complete_history",
))
_UNSUPPORTED = frozenset((
    "upstream_cause", "physical_effect", "absence_of_event", "complete_history",
))
_LIMITS = frozenset((
    "physical_ack_unverified", "root_cause_unverified",
    "history_incomplete", "absence_not_authorised",
))
_MAX_CASES = 12
_MAX_ATOMS = 5
_MAX_SENTENCE = 500


def _atom(value: Any, facts: Mapping[str, Any]) -> tuple[str, tuple[str, ...], str | None]:
    """Validate a bounded semantic proposition; source ID and role only."""
    if (not isinstance(value, Mapping) or set(value) != {
            "proposition", "fact_ids", "limit"}):
        raise ValueError("unknown atomic extraction shape")
    prop = value["proposition"]
    ids = value["fact_ids"]
    limit = value["limit"]
    if prop not in _TYPES or not isinstance(ids, list):
        raise ValueError("unknown proposition or IDs")
    if (len(ids) > 2 or len(ids) != len(set(str(x) for x in ids))
            or any(not isinstance(fid, str) or fid not in facts for fid in ids)):
        raise ValueError("unknown or duplicated source references")
    if prop == "packet_limit":
        if ids or limit not in _LIMITS:
            raise ValueError("unknown limitation")
    elif (limit is not None or len(ids) != (
            2 if prop == "upstream_cause" else 1)):
        raise ValueError("source scope not suitable for proposition type")
    return prop, tuple(ids), limit


def _proof_claim(atom: tuple[str, tuple[str, ...], str | None],
                 facts: Mapping[str, Any]) -> dict[str, Any]:
    """All witness fields derived from host facts, NEVER model-supplied."""
    prop, ids, limit = atom
    f = facts[ids[0]] if ids else None
    if prop == "recorded_event":
        witness = {k: f[k] for k in ("kind", "entity_id", "attribute", "value")}
    elif prop == "recorded_issuer":
        witness = {"entity_id": f["entity_id"],
                   "issuer_app_id": f.get("issuer_app_id")}
    elif prop == "recorded_clock":
        witness = {k: f[k] for k in ("entity_id", "clock_basis", "time_utc")}
    elif prop == "recorded_gap":
        witness = {k: f[k] for k in ("entity_id", "gap_count", "truncated")}
    elif prop == "packet_limit":
        witness = {"limit": limit}
    elif prop == "upstream_cause":
        witness = {"cause_fact_id": ids[0], "result_fact_id": ids[1]}
    else:
        witness = {"entity_id": f["entity_id"]}
    return {
        "claim_id": "c001", "proposition": prop,
        "fact_ids": list(ids), "witness": witness,
    }


def _validate_cases(cases: Any) -> list[tuple[dict[str, Any],
                                             list[tuple[str, tuple[str, ...], str | None]]]]:
    if not isinstance(cases, (list, tuple)) or not 1 <= len(cases) <= _MAX_CASES:
        raise ValueError("bounded nonempty offline case list required")
    checked = []
    for row in cases:
        if (not isinstance(row, Mapping)
                or set(row) != {"sentence", "packet", "reference_atoms"}
                or not isinstance(row["sentence"], str)
                or not 1 <= len(row["sentence"]) <= _MAX_SENTENCE
                or not isinstance(row["reference_atoms"], list)
                or not 1 <= len(row["reference_atoms"]) <= _MAX_ATOMS):
            raise ValueError("invalid prose reference case")
        facts = _host_packet(row["packet"])
        refs = [_atom(a, facts) for a in row["reference_atoms"]]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate reference propositions")
        checked.append((dict(row), refs))
    return checked


def evaluate_stage4j_prose_claim_coverage(
    cases: Sequence[Mapping[str, Any]],
    *, model: str, invoke: Callable[[str, Mapping[str, Any]], Any],
) -> dict[str, Any]:
    """Model-extracted implications versus withheld host-curated oracles.

    This metric assesses extraction quality only ON PROVIDED CASES.
    The independent labels never enter the model prompt. Even an
    exact match does not validate arbitrary newly written answers.
    """
    checked = _validate_cases(cases)
    if model != "qwen2.5:3b" or not callable(invoke):
        raise ValueError("only bounded offline 3B extractor experiment allowed")
    totals: Counter[str] = Counter()
    for case, oracle in checked:
        facts = _host_packet(case["packet"])
        reference_set = set(oracle)
        risk_set = {a for a in oracle if a[0] in _UNSUPPORTED}
        totals["reference_atoms"] += len(reference_set)
        totals["reference_high_risk_atoms"] += len(risk_set)
        totals["invocation_attempts"] += 1
        try:
            raw = invoke(model, {
                "task": "extract",
                "schema": "homebrain-stage4j-extract-request.v1",
                "sentence": case["sentence"],
                "packet": case["packet"],
            })
        except Exception:
            totals["invocation_errors"] += 1
            totals["missed_atoms"] += len(reference_set)
            totals["missed_high_risk_atoms"] += len(risk_set)
            continue
        totals["responses_received"] += 1
        if (not isinstance(raw, Mapping)
                or set(raw) != {"schema", "atoms"}
                or raw["schema"] != "homebrain-stage4j-atom-extraction.v1"
                or not isinstance(raw["atoms"], list)
                or len(raw["atoms"]) > _MAX_ATOMS):
            totals["invalid_responses"] += 1
            totals["missed_atoms"] += len(reference_set)
            totals["missed_high_risk_atoms"] += len(risk_set)
            continue
        try:
            predicted = [_atom(a, facts) for a in raw["atoms"]]
            if len(predicted) != len(set(predicted)):
                raise ValueError("repeated proposition")
        except (ValueError, TypeError):
            totals["invalid_responses"] += 1
            totals["missed_atoms"] += len(reference_set)
            totals["missed_high_risk_atoms"] += len(risk_set)
            continue
        totals["valid_responses"] += 1
        observed = set(predicted)
        missed = reference_set - observed
        extra = observed - reference_set
        totals["extracted_atoms"] += len(observed)
        totals["correctly_extracted_atoms"] += len(reference_set & observed)
        totals["missed_atoms"] += len(missed)
        totals["extra_atoms"] += len(extra)
        totals["missed_high_risk_atoms"] += len(risk_set - observed)
        totals["cases_exact_extraction"] += int(observed == reference_set)
        for atom in observed:
            try:
                result = evaluate_stage4i_proof_obligations(
                    case["packet"],
                    {"schema": "homebrain-stage4i-proof-bundle.v1",
                     "claims": [_proof_claim(atom, facts)]},
                )
            except (ValueError, TypeError, KeyError):
                totals["proof_errors"] += 1
                continue
            totals["host_proven_extracted_atoms"] += result["host_proven_atomic_claims"]
            totals["host_unproven_extracted_atoms"] += result["unproven_atomic_claims"]
            totals["host_unproven_high_risk_atoms"] += (
                result["unproven_atomic_claims"] if atom[0] in _UNSUPPORTED else 0)
    return {
        "schema": "homebrain-stage4j-prose-atom-coverage.v1",
        "case_count": len(checked),
        "extractor_model": model,
        "invocation_attempts": totals["invocation_attempts"],
        "responses_received": totals["responses_received"],
        "invocation_errors": totals["invocation_errors"],
        "valid_responses": totals["valid_responses"],
        "invalid_responses": totals["invalid_responses"],
        "reference_atoms": totals["reference_atoms"],
        "reference_high_risk_atoms": totals["reference_high_risk_atoms"],
        "extracted_atoms": totals["extracted_atoms"],
        "correctly_extracted_atoms": totals["correctly_extracted_atoms"],
        "missed_atoms": totals["missed_atoms"],
        "extra_atoms": totals["extra_atoms"],
        "missed_high_risk_atoms": totals["missed_high_risk_atoms"],
        "exact_extraction_cases": totals["cases_exact_extraction"],
        "extraction_recall": (
            round(totals["correctly_extracted_atoms"] / totals["reference_atoms"], 4)
            if totals["reference_atoms"] else None),
        "extraction_precision": (
            round(totals["correctly_extracted_atoms"] / totals["extracted_atoms"], 4)
            if totals["extracted_atoms"] else None),
        "host_proven_extracted_atoms": totals["host_proven_extracted_atoms"],
        "host_unproven_extracted_atoms": totals["host_unproven_extracted_atoms"],
        "host_unproven_high_risk_atoms": totals["host_unproven_high_risk_atoms"],
        "proof_errors": totals["proof_errors"],
        "reference_annotations_externally_authenticated": False,
        "reference_cases_pre_authored_not_new_generation": True,
        "extraction_completeness_on_unseen_prose_proven": False,
        "model_is_not_trusted_to_self_certify_completeness": True,
        "source_proof_does_not_attest_free_text": True,
        "production_publisher_approval": False,
        "live_homebrain_evaluated": False,
        "devices_touched": False,
    }


__all__ = ["evaluate_stage4j_prose_claim_coverage"]
