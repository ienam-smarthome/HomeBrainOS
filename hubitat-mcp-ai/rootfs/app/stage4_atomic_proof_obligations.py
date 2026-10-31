"""Stage 4I: host-source proof obligations for bounded ATOMIC propositions.

The primary safety lesson from actual Stage 4H model reviews: even two
concordant model judges may accept a fabricated physical action or upstream
cause. For a precisely typed proposition the host can instead require the
right type of positive source witness, not just a citation or model vote.

No natural-language parser: it cannot prove that an authored sentence means
the atomic claims attached to it. No production imports, publisher changes,
model calls, device/MCP/network use or history reconstruction. The caller
must provide a trusted host-produced Stage 4A packet; source authenticity
cannot be established from a self-declared packet.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping, Sequence

_MAX_CLAIMS = 16
_MAX_FACTS = 80
_ID = re.compile(r"^c[0-9]{3}$")
_FACT_ID = re.compile(r"^f[0-9]{3}$")
_FACT_KINDS = frozenset(("issued_command", "reported_state", "input_report",
                         "coverage_limit"))
_PROPS = frozenset((
    "recorded_event", "recorded_issuer", "recorded_clock", "recorded_gap",
    "packet_limit", "upstream_cause", "physical_effect", "absence_of_event",
    "complete_history",
))
_UNPROVABLE = frozenset((
    "upstream_cause", "physical_effect", "absence_of_event", "complete_history",
))
_LIMITS = {
    "physical_ack_unverified": ("physical_acknowledgement_proven", False),
    "root_cause_unverified": ("upstream_root_cause_proven", False),
    "history_incomplete": ("source_history_complete", False),
    "absence_not_authorised": ("claims_about_absence_authorised", False),
}


def _host_packet(packet: Any) -> dict[str, Mapping[str, Any]]:
    if (not isinstance(packet, Mapping)
            or packet.get("schema") != "homebrain-stage4-evidence-packet.v1"
            or packet.get("shadow_only") is not True
            or packet.get("is_publisher_input_not_publication") is not True
            or not isinstance(packet.get("facts"), list)
            or not 1 <= len(packet["facts"]) <= _MAX_FACTS
            or any(packet.get(field) is not False for field in (
                "physical_acknowledgement_proven", "upstream_root_cause_proven",
                "source_history_complete", "claims_about_absence_authorised"
            ))):
        raise ValueError("invalid or unsafe host evidence packet")
    witness: dict[str, Mapping[str, Any]] = {}
    for fact in packet["facts"]:
        if (not isinstance(fact, Mapping)
                or not isinstance(fact.get("fact_id"), str)
                or not _FACT_ID.fullmatch(fact["fact_id"])
                or fact["fact_id"] in witness
                or fact.get("kind") not in _FACT_KINDS
                or not isinstance(fact.get("entity_id"), str)):
            raise ValueError("ambiguous or unsupported host fact")
        if fact["kind"] == "coverage_limit":
            if (fact.get("complete") is not False
                    or not isinstance(fact.get("gap_count"), int)
                    or isinstance(fact.get("gap_count"), bool)
                    or fact["gap_count"] < 0
                    or not isinstance(fact.get("truncated"), bool)):
                raise ValueError("invalid host gap evidence")
        elif (fact.get("physical_ack_verified") is not False
              or "attribute" not in fact or "value" not in fact
              or "clock_basis" not in fact
              or "time_utc" not in fact):
            raise ValueError("invalid host event evidence")
        witness[fact["fact_id"]] = fact
    return witness


def _required_claim(claim: Any) -> None:
    if (not isinstance(claim, Mapping)
            or set(claim) != {"claim_id", "proposition", "fact_ids", "witness"}
            or not isinstance(claim.get("claim_id"), str)
            or not _ID.fullmatch(claim["claim_id"])
            or claim.get("proposition") not in _PROPS
            or not isinstance(claim.get("witness"), Mapping)
            or not isinstance(claim.get("fact_ids"), list)):
        raise ValueError("invalid or unknown proof obligation")
    ids = claim["fact_ids"]
    if (len(ids) > 2 or len(ids) != len(set(str(x) for x in ids))
            or any(not isinstance(x, str) or not _FACT_ID.fullmatch(x)
                   for x in ids)):
        raise ValueError("unbounded or duplicate source references")
    if claim["proposition"] == "packet_limit":
        if ids or set(claim["witness"]) != {"limit"}:
            raise ValueError("packet-level limitations cannot cite fabricated facts")
    else:
        if len(ids) != (2 if claim["proposition"] == "upstream_cause" else 1):
            raise ValueError("invalid source witness cardinality")
    witness = claim["witness"]
    expected_keys = {
        "recorded_event": {"kind", "entity_id", "attribute", "value"},
        "recorded_issuer": {"entity_id", "issuer_app_id"},
        "recorded_clock": {"entity_id", "clock_basis", "time_utc"},
        "recorded_gap": {"entity_id", "gap_count", "truncated"},
        "packet_limit": {"limit"},
        "upstream_cause": {"cause_fact_id", "result_fact_id"},
        "physical_effect": {"entity_id"},
        "absence_of_event": {"entity_id"},
        "complete_history": {"entity_id"},
    }[claim["proposition"]]
    if set(witness) != expected_keys:
        raise ValueError("invalid proposition-specific witness fields")


def _prove(claim: Mapping[str, Any], facts: Mapping[str, Mapping[str, Any]],
           packet: Mapping[str, Any]) -> str:
    prop = claim["proposition"]
    refs = claim["fact_ids"]
    w = claim["witness"]
    if prop == "packet_limit":
        limit = w["limit"]
        pair = _LIMITS.get(limit) if isinstance(limit, str) else None
        return "proven" if pair and packet.get(pair[0]) is pair[1] else "unproven"
    if any(fid not in facts for fid in refs):
        return "unproven"
    if prop in _UNPROVABLE:
        # The Stage 4A packet has NO verified source-causal edge, device
        # physical-effect acknowledgment, or complete absence proof.
        # Even two genuine events cannot prove their causal relationship.
        return "unproven"
    fact = facts[refs[0]]
    if prop == "recorded_gap":
        return ("proven" if (fact["kind"] == "coverage_limit"
                and (fact["gap_count"] > 0 or fact["truncated"])
                and all(fact.get(k) == v for k, v in w.items()))
                else "unproven")
    if fact["kind"] == "coverage_limit":
        return "unproven"
    if prop == "recorded_event":
        return ("proven" if all(fact.get(k) == v for k, v in w.items())
                else "unproven")
    if prop == "recorded_issuer":
        # This establishes ONLY a recorded immediate issuer, not an
        # upstream sensor, initiating person or eventual physical actuation.
        return ("proven" if isinstance(fact.get("issuer_app_id"), str)
                and bool(fact["issuer_app_id"])
                and all(fact.get(k) == v for k, v in w.items())
                else "unproven")
    if prop == "recorded_clock":
        return ("proven" if (fact.get("clock_basis") is not None
                and fact.get("time_utc") is not None
                and all(fact.get(k) == v for k, v in w.items()))
                else "unproven")
    return "unproven"


def evaluate_stage4i_proof_obligations(packet: Any, bundle: Any) -> dict[str, Any]:
    """Host-source proof of *typed* claims, not semantic approval of text.

    A "proven" obligation means the specified atomic role/field follows
    from the supplied canonical fact, NOT that model-written wording is
    equivalent to the obligation or that the source is authenticated.
    """
    facts = _host_packet(packet)
    if (not isinstance(bundle, Mapping)
            or set(bundle) != {"schema", "claims"}
            or bundle.get("schema") != "homebrain-stage4i-proof-bundle.v1"
            or not isinstance(bundle.get("claims"), list)
            or not 1 <= len(bundle["claims"]) <= _MAX_CLAIMS):
        raise ValueError("invalid bounded atomic proof bundle")
    seen: set[str] = set()
    outcome: Counter[str] = Counter()
    breakdown: dict[str, Counter[str]] = {}
    for claim in bundle["claims"]:
        _required_claim(claim)
        if claim["claim_id"] in seen:
            raise ValueError("duplicate atomic claim ID")
        seen.add(claim["claim_id"])
        status = _prove(claim, facts, packet)
        outcome[status] += 1
        breakdown.setdefault(claim["proposition"], Counter())[status] += 1
    return {
        "schema": "homebrain-stage4i-atomic-proof-audit.v1",
        "atomic_claim_count": len(seen),
        "host_proven_atomic_claims": outcome["proven"],
        "unproven_atomic_claims": outcome["unproven"],
        "by_proposition": {
            prop: {"proven": breakdown[prop]["proven"],
                   "unproven": breakdown[prop]["unproven"]}
            for prop in sorted(breakdown)
        },
        "provenance_of_host_packet_independently_authenticated": False,
        "source_event_is_not_physical_confirmation": True,
        "issuer_is_not_upstream_cause": True,
        "history_incompleteness_does_not_establish_absence": True,
        "claim_text_meaning_verified": False,
        "atomic_claim_extraction_from_prose_verified": False,
        "model_witness_attestation_is_not_truth": True,
        "reviewer_agreement_not_used_as_proof": True,
        "publisher_approval": False,
        "active_answer_changed": False,
        "device_actions_executed": False,
    }


def benchmark_stage4i_reference_claims(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Static separately curated labels of atomic claims: a test oracle only.

    The labels are NOT copied into the evaluator and have not been
    authenticated against live household traces.
    """
    if not isinstance(cases, (list, tuple)) or not 1 <= len(cases) <= 24:
        raise ValueError("invalid reference corpus")
    counts: Counter[str] = Counter()
    for case in cases:
        if not isinstance(case, Mapping) or set(case) != {
            "packet", "claim", "expected"
        } or case["expected"] not in ("proven", "unproven"):
            raise ValueError("invalid curated reference label")
        proof = evaluate_stage4i_proof_obligations(
            case["packet"],
            {"schema": "homebrain-stage4i-proof-bundle.v1",
             "claims": [case["claim"]]},
        )
        accepted = proof["host_proven_atomic_claims"] == 1
        counts["cases"] += 1
        counts["supported"] += int(case["expected"] == "proven")
        counts["unproven"] += int(case["expected"] == "unproven")
        counts["false_accepts"] += int(accepted and case["expected"] == "unproven")
        counts["false_rejects"] += int(not accepted and case["expected"] == "proven")
    return {
        "schema": "homebrain-stage4i-constructed-atomic-benchmark.v1",
        "case_count": counts["cases"],
        "reference_proven_count": counts["supported"],
        "reference_unproven_count": counts["unproven"],
        "false_accept_count": counts["false_accepts"],
        "false_reject_count": counts["false_rejects"],
        "false_accept_rate": (
            round(counts["false_accepts"] / counts["unproven"], 4)
            if counts["unproven"] else None),
        "false_reject_rate": (
            round(counts["false_rejects"] / counts["supported"], 4)
            if counts["supported"] else None),
        "independent_live_oracle_authenticated": False,
        "full_answer_prose_semantically_scored": False,
        "publisher_unchanged": True,
    }


__all__ = [
    "evaluate_stage4i_proof_obligations",
    "benchmark_stage4i_reference_claims",
]
