"""Stage 3B offline scorecard for the already existing Stage 3A read frontier.

Strictly an evaluator, never a planner or answer publisher. Reference
discriminators are provided by independently authored regression fixtures,
and are never passed into the frontier being tested.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from statistics import mean
from typing import Any, Mapping, Sequence

from causal_source_feasibility import build_source_feasibility_choices
from stage3_evidence_frontier import (
    _scope, _signature, build_stage3_read_frontier,
)

_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,59}$")
_MAX_CASES = 40
_MAX_ORACLE_READS = 24


def _key(row: Any, catalog: frozenset[str]) -> str | None:
    if not isinstance(row, Mapping):
        return None
    leaf = row.get("leaf")
    if not isinstance(leaf, str) or leaf not in catalog:
        return None
    args = _scope(leaf, row.get("args"))
    return _signature(leaf, args) if args is not None else None


def _evaluate_ranked(
    candidates: Sequence[Mapping[str, Any]],
    oracle: set[str],
    catalog: frozenset[str],
    k: int,
) -> dict[str, Any]:
    selected = [_key(row, catalog) for row in candidates[:k]]
    # An invalid candidate is counted in the denominator, never hidden as a
    # good result. Duplicates cannot increase evidence coverage.
    selected_valid = {key for key in selected if key is not None}
    useful = len(selected_valid & oracle)
    offered = len(selected)
    first_useful = next((index for index, key in enumerate(selected, 1)
                         if key in oracle), None)
    return {
        "offered": offered,
        "useful": useful,
        "precision_at_k": round(useful / offered, 4) if offered else 0.0,
        "oracle_recall_at_k": round(useful / len(oracle), 4) if oracle else None,
        "first_useful_rank": first_useful,
        "invalid_or_unauthorized_offered": sum(x is None for x in selected),
        "duplicate_offered": offered - len(selected_valid) - sum(x is None for x in selected),
    }


def evaluate_stage3_fixture_suite(
    cases: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    """Measure independent expected-read recovery versus existing V3 frontier.

    Each case supplies receipt evidence, optional grouped legacy facts,
    candidate model reads and an independently specified oracle. Unlike
    execution-time plan selection, this function can *see* the oracle, but
    only AFTER it calls the tested frontier. Output is aggregate and
    privacy-bounded; raw device names, receipts and model text never appear.
    """
    k = max(1, min(int(top_k), 12))
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases[:_MAX_CASES]):
        if not isinstance(case, Mapping):
            raise ValueError("case must be a mapping")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or _CASE_ID.fullmatch(case_id) is None:
            raise ValueError("case_id must be a short, safe fixture identifier")
        receipts = case.get("receipts")
        if not isinstance(receipts, (tuple, list)):
            raise ValueError("receipts must be a bounded sequence")
        facts = case.get("facts")
        if facts is not None and not isinstance(facts, Mapping):
            raise ValueError("facts must be a mapping or None")
        model_proposals = case.get("model_proposals") or []
        if not isinstance(model_proposals, (tuple, list)):
            raise ValueError("model_proposals must be a sequence")
        catalog = frozenset(
            t for t in (case.get("available_read_tools") or ())
            if isinstance(t, str)
        )
        expected = case.get("expected_reads")
        if not isinstance(expected, (tuple, list)) or len(expected) > _MAX_ORACLE_READS:
            raise ValueError("expected_reads must be a bounded sequence")
        oracle = {_key(x, catalog) for x in expected}
        if None in oracle or len(oracle) != len(expected):
            raise ValueError("oracle reads must have unique, valid catalog-scoped keys")

        # IMPORTANT: expected/oracle reads are NOT passed to the planner.
        plan = build_stage3_read_frontier(
            receipts, facts=facts,
            model_proposals=model_proposals,
            available_read_tools=tuple(sorted(catalog)),
            max_choices=k,
        )
        result = _evaluate_ranked(plan["candidate_reads"], oracle, catalog, k)
        legacy = build_source_feasibility_choices(facts, receipts, max_options=6)
        baseline = None
        if isinstance(legacy, Mapping):
            baseline = _evaluate_ranked(
                legacy.get("candidate_reads") or [], oracle, catalog, k)
        rows.append({
            "case_id": case_id,
            "domain": str(case.get("domain") or "unspecified")[:32]
                      if str(case.get("domain") or "unspecified").isascii()
                      and str(case.get("domain") or "unspecified").replace("-", "").isalpha()
                      else "unspecified",
            "expected_new_reads": len(oracle),
            "new_frontier": result,
            "existing_frontier": baseline,
            "exact_repeats_suppressed": plan["rejected_candidate_counts"].get(
                "exact-read-already-attempted", 0),
            "unverified_ids_suppressed": plan["rejected_candidate_counts"].get(
                "identifier-not-source-attested", 0),
            "invalid_scopes_suppressed": plan["rejected_candidate_counts"].get(
                "invalid-or-unbounded-scope", 0),
            "unsupported_leaves_suppressed": plan["rejected_candidate_counts"].get(
                "not-in-current-validated-read-catalog", 0),
            "source_absence_proven": False,
            "root_cause_proven": False,
        })

    def averages(key: str, root: str) -> float | None:
        values = [v[root][key] for v in rows
                  if isinstance(v.get(root), Mapping)
                  and v[root].get(key) is not None]
        return round(mean(values), 4) if values else None

    comparison_cases = sum(row["existing_frontier"] is not None for row in rows)
    return {
        "schema": "homebrain-stage3b-offline-scorecard.v1",
        "shadow_only": True,
        "executes_tools": False,
        "independent_oracle_not_passed_to_planner": True,
        "suite_count": len(rows),
        "suite_cases_omitted": max(0, len(cases) - _MAX_CASES),
        "legacy_comparable_cases": comparison_cases,
        "top_k": k,
        "stage3_macro_precision_at_k": averages("precision_at_k", "new_frontier"),
        "stage3_macro_oracle_recall_at_k": averages("oracle_recall_at_k", "new_frontier"),
        "existing_macro_precision_at_k": averages("precision_at_k", "existing_frontier"),
        "existing_macro_oracle_recall_at_k": averages("oracle_recall_at_k", "existing_frontier"),
        "total_expected_reads": sum(row["expected_new_reads"] for row in rows),
        "total_stage3_useful_reads_at_k": sum(row["new_frontier"]["useful"] for row in rows),
        "total_legacy_useful_reads_at_k": sum(
            row["existing_frontier"]["useful"] for row in rows if row["existing_frontier"]),
        "total_suppressed_exact_repeats": sum(row["exact_repeats_suppressed"] for row in rows),
        "total_suppressed_unverified_ids": sum(row["unverified_ids_suppressed"] for row in rows),
        "total_suppressed_invalid_scopes": sum(row["invalid_scopes_suppressed"] for row in rows),
        "total_suppressed_unsupported_leaves": sum(row["unsupported_leaves_suppressed"] for row in rows),
        "total_invalid_or_unauthorized_stage3_offers": sum(
            row["new_frontier"]["invalid_or_unauthorized_offered"] for row in rows),
        "cases": rows,
        "zero_unsupported_causal_claims_asserted": True,
        "no_runtime_quality_or_latency_claim": True,
    }


__all__ = ["evaluate_stage3_fixture_suite"]
