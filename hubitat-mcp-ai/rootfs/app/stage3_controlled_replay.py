"""Stage 3D: controlled OFFLINE replay of model tool proposals vs Stage 3A.

No MCP client, hosted model, device/network access, storage, timers or active
agent integration. Inputs must already be redacted, independently collected
and bounded. 'Original model' refers to supplied model-call-shaped input;
constructed test cases are NEVER represented as observed production calls.

The independent expected-read oracle is consulted only AFTER both original
model and advisory frontier choices have been computed.
"""
from __future__ import annotations

import re
from statistics import mean
from typing import Any, Mapping, Sequence

from stage3_loop_shadow import (
    _MAX_CALLS, _MAX_SCHEMAS, _call_arguments, _declared_operations,
    observe_stage3_model_round,
)
from stage3_evidence_frontier import (
    _discovered_ids, _scope, _signature, build_stage3_read_frontier,
)

_SAFE_LABEL = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_ORIGINS = frozenset(("constructed-fixture", "anonymised-reconstruction",
                     "user-labelled-redacted-trace"))
_MAX_CASES = 24
_MAX_ROUNDS = 12
_MAX_RECEIPTS = 160
_MAX_ORACLE = 12


def _validated_key(row: Any, allowed: frozenset[str]) -> str | None:
    if not isinstance(row, Mapping):
        return None
    leaf = row.get("leaf")
    if not isinstance(leaf, str) or leaf not in allowed:
        return None
    args = _scope(leaf, row.get("args"))
    return _signature(leaf, args) if args is not None else None


def _model_read_proposals(
    calls: Sequence[Any], schemas: Sequence[Any],
) -> tuple[list[dict[str, Any]], frozenset[str]]:
    """Only positively declared read suboperations, never gateway guessing."""
    permitted = _declared_operations(schemas)
    allowed = frozenset(x for operations in permitted.values() for x in operations)
    proposals: list[dict[str, Any]] = []
    for call in calls[:_MAX_CALLS]:
        if not isinstance(call, Mapping):
            continue
        function = call.get("function")
        if not isinstance(function, Mapping):
            continue
        gateway = function.get("name")
        if not isinstance(gateway, str) or gateway not in permitted:
            continue
        value = _call_arguments(function.get("arguments"))
        if not isinstance(value, Mapping):
            continue
        operation, arguments = value.get("tool"), value.get("args")
        if (isinstance(operation, str) and operation in permitted[gateway]
                and isinstance(arguments, Mapping)):
            proposals.append({"leaf": operation, "args": arguments})
    return proposals, allowed


def _score(keys: Sequence[str | None], oracle: set[str], k: int) -> dict[str, Any]:
    top = list(keys[:k])
    matched = {key for key in top if key is not None and key in oracle}
    return {
        "offered_at_k": len(top),
        "useful_at_k": len(matched),
        "precision_at_k": round(len(matched) / len(top), 4) if top else 0.0,
        "oracle_recall_at_k": round(len(matched) / len(oracle), 4) if oracle else None,
        "first_useful_rank": next((i for i, key in enumerate(top, 1)
                                   if key in oracle), None),
        "invalid_scope_at_k": sum(key is None for key in top),
        "exact_duplicate_keys_at_k": len(top) - len(set(top)),
    }


def evaluate_stage3d_replay(
    cases: Sequence[Mapping[str, Any]], *,
    top_k: int = 3,
) -> dict[str, Any]:
    """Score actual-shaped model choices *as supplied* versus safe frontier.

    The existing executor/model responses are never invoked. A "model"
    baseline is an input trace, NOT independently verified live activity.
    Cases with no independently supplied oracle are excluded from utility
    averages rather than treated as 0 or 100 percent useful.
    """
    if not isinstance(cases, (tuple, list)):
        raise ValueError("cases must be an in-memory sequence")
    k = max(1, min(int(top_k), 12))
    out: list[dict[str, Any]] = []
    for case in cases[:_MAX_CASES]:
        if not isinstance(case, Mapping):
            raise ValueError("case must be a mapping")
        case_id = case.get("case_id")
        domain = case.get("domain")
        origin = case.get("trace_origin")
        if (not isinstance(case_id, str) or not _SAFE_LABEL.fullmatch(case_id)
                or not isinstance(domain, str) or not _SAFE_LABEL.fullmatch(domain)):
            raise ValueError("case id and domain must be safe identifiers")
        if not isinstance(origin, str) or origin not in _ORIGINS:
            raise ValueError("trace_origin must state the input's evidence provenance")
        rounds = case.get("rounds")
        if not isinstance(rounds, (list, tuple)) or not rounds:
            raise ValueError("case requires nonempty rounds")
        case_result: list[dict[str, Any]] = []
        for index, row in enumerate(rounds[:_MAX_ROUNDS], start=1):
            if not isinstance(row, Mapping):
                raise ValueError("round must be a mapping")
            receipts = row.get("receipts_before")
            calls = row.get("model_tool_calls")
            schemas = row.get("declared_tool_schemas")
            facts = row.get("facts")
            if not isinstance(receipts, (list, tuple)) or len(receipts) > _MAX_RECEIPTS:
                raise ValueError("receipts_before must be bounded and pre-round")
            if not isinstance(calls, (list, tuple)):
                raise ValueError("model_tool_calls must be an in-memory sequence")
            if not isinstance(schemas, (list, tuple)):
                raise ValueError("declared_tool_schemas must be an in-memory sequence")
            if facts is not None and not isinstance(facts, Mapping):
                raise ValueError("facts must be an optional mapping")
            model_reads, allowed = _model_read_proposals(calls, schemas)
            # No oracle argument reaches the planner or the passive observer.
            shadow = build_stage3_read_frontier(
                receipts, facts=facts, model_proposals=model_reads,
                available_read_tools=tuple(sorted(allowed)), max_choices=k)
            passive = observe_stage3_model_round(receipts, calls, schemas)
            # Input is an optional independently authored expectation. A
            # missing oracle is UNASSESSED, never an implicit zero score.
            oracle_input = row.get("expected_reads", None)
            model_score = frontier_score = None
            if oracle_input is not None:
                if (not isinstance(oracle_input, (list, tuple))
                        or len(oracle_input) > _MAX_ORACLE):
                    raise ValueError("expected_reads must be a bounded sequence")
                devices, apps, _command_apps = _discovered_ids(receipts)
                oracle = set()
                for expected in oracle_input:
                    key = _validated_key(expected, allowed)
                    if key is None or key in oracle:
                        raise ValueError("expected reads must be unique, declared and scoped")
                    args = _scope(expected["leaf"], expected["args"])
                    ident = args.get("deviceId", args.get("appId"))
                    if ident not in (devices if "deviceId" in args else apps):
                        raise ValueError("expected read ID lacks independent receipt evidence")
                    oracle.add(key)
                model_score = _score(
                    [_validated_key(x, allowed) for x in model_reads], oracle, k)
                frontier_score = _score(
                    [_validated_key(x, allowed)
                     for x in shadow["candidate_reads"]], oracle, k)
            case_result.append({
                "round": index,
                "input_model_calls": min(len(calls), _MAX_CALLS),
                "model_calls_omitted": max(0, len(calls) - _MAX_CALLS),
                "model_reads_with_declared_mapping": len(model_reads),
                "shadow_read_candidates": shadow["candidate_count"],
                "shadow_choices_omitted": shadow["candidate_count_omitted"],
                "duplicate_exact_attempts_suppressed":
                    shadow["rejected_candidate_counts"].get(
                        "exact-read-already-attempted", 0),
                "unattested_ids_suppressed":
                    shadow["rejected_candidate_counts"].get(
                        "identifier-not-source-attested", 0),
                "invalid_scopes_suppressed":
                    shadow["rejected_candidate_counts"].get(
                        "invalid-or-unbounded-scope", 0),
                "unsupported_operations_skipped":
                    passive["unsupported_gateway_or_operation_calls_skipped"],
                "unparseable_envelopes_skipped":
                    passive["invalid_envelopes_skipped"],
                "model_oracle": model_score,
                "shadow_oracle": frontier_score,
                "oracle_available": oracle_input is not None,
                "effect_on_live_tool_calls": False,
                "effect_on_live_answer": False,
            })
        out.append({
            "case_id": case_id,
            "domain": domain,
            "trace_origin": origin,
            "provenance_independently_authenticated": False,
            "rounds": case_result,
            "rounds_omitted": max(0, len(rounds) - _MAX_ROUNDS),
        })
    scored = [row for case in out for row in case["rounds"]
              if row["oracle_available"]]
    def avg(kind: str, field: str) -> float | None:
        vals = [item[kind][field] for item in scored
                if item[kind] is not None and item[kind][field] is not None]
        return round(mean(vals), 4) if vals else None
    return {
        "schema": "homebrain-stage3d-controlled-replay.v1",
        "offline_only": True,
        "model_calls_replayed_not_executed": True,
        "shadow_only": True,
        "case_count": len(out),
        "cases_omitted": max(0, len(cases) - _MAX_CASES),
        "round_count": sum(len(case["rounds"]) for case in out),
        "oracle_scored_rounds": len(scored),
        "oracle_unscored_rounds": sum(len(case["rounds"]) for case in out) - len(scored),
        "top_k": k,
        "model_macro_oracle_recall_at_k": avg("model_oracle", "oracle_recall_at_k"),
        "shadow_macro_oracle_recall_at_k": avg("shadow_oracle", "oracle_recall_at_k"),
        "model_macro_precision_at_k": avg("model_oracle", "precision_at_k"),
        "shadow_macro_precision_at_k": avg("shadow_oracle", "precision_at_k"),
        "total_duplicate_attempts_suppressed": sum(
            row["duplicate_exact_attempts_suppressed"] for c in out for row in c["rounds"]),
        "total_unattested_ids_suppressed": sum(
            row["unattested_ids_suppressed"] for c in out for row in c["rounds"]),
        "total_invalid_scopes_suppressed": sum(
            row["invalid_scopes_suppressed"] for c in out for row in c["rounds"]),
        "cases": out,
        "input_trace_provenance_not_verified": True,
        "no_live_speed_or_quality_claim": True,
        "historical_completeness_proven": False,
        "causal_initiator_verified": False,
        "physical_ack_verified": False,
        "no_agent_tool_or_publisher_change": True,
    }


__all__ = ["evaluate_stage3d_replay"]
