"""Stage 3C passive observation of *actual* model-chosen read proposals.

Only invoked when an explicitly constructed agent has stage3_shadow_mode='observe'.
No tool execution, model guidance, runtime outcome, permissions, or device
state changes. Uses the EXACT tool schemas advertised to that model round;
does not turn prior successful tools, prose descriptions or model guesses
into catalog authorization. Never emits argument values or credentials.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from stage3_evidence_frontier import (
    _READ_SCOPES, build_stage3_read_frontier,
)

_MAX_CALLS = 16
_MAX_SCHEMAS = 60


def _call_arguments(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str) or len(value) > 12000:
        return None
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, Mapping) else None
    except (ValueError, TypeError):
        return None


def _declared_operations(
    schemas: Sequence[Mapping[str, Any]],
) -> dict[str, set[str]]:
    """Only explicit live tool enum entries; never guess a gateway mapping."""
    declared: dict[str, set[str]] = {}
    for schema in schemas[:_MAX_SCHEMAS]:
        if not isinstance(schema, Mapping):
            continue
        function = schema.get("function")
        if not isinstance(function, Mapping):
            continue
        gateway = function.get("name")
        if not isinstance(gateway, str) or not gateway.startswith("hub_read_"):
            continue
        parameters = function.get("parameters")
        props = parameters.get("properties") if isinstance(parameters, Mapping) else None
        tool_prop = props.get("tool") if isinstance(props, Mapping) else None
        enum = tool_prop.get("enum") if isinstance(tool_prop, Mapping) else None
        if not isinstance(enum, list):
            continue
        admitted = {x for x in enum[:100] if type(x) is str and x in _READ_SCOPES}
        if admitted:
            declared[gateway] = admitted
    return declared


def observe_stage3_model_round(
    receipts: Sequence[Mapping[str, Any]],
    model_tool_calls: Sequence[Mapping[str, Any]],
    declared_tool_schemas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Pure metrics-only observation; all source/model/tool text is discarded.

    An unrecognised/unknown gateway is NOT judged disallowed by the live
    executor; it is simply outside the currently verified shadow adapter.
    No model call is added, removed, reordered, blocked or edited here.
    """
    permitted = _declared_operations(declared_tool_schemas)
    seen_calls = 0
    scoped_proposals: list[dict[str, Any]] = []
    rejected_envelopes = 0
    skipped_unsupported = 0
    for call in model_tool_calls[:_MAX_CALLS]:
        if not isinstance(call, Mapping):
            rejected_envelopes += 1
            continue
        function = call.get("function")
        if not isinstance(function, Mapping):
            rejected_envelopes += 1
            continue
        gateway = function.get("name")
        if not isinstance(gateway, str) or gateway not in permitted:
            skipped_unsupported += 1
            continue
        raw = _call_arguments(function.get("arguments"))
        if raw is None:
            rejected_envelopes += 1
            continue
        operation = raw.get("tool")
        args = raw.get("args")
        if operation not in permitted[gateway] or not isinstance(args, Mapping):
            skipped_unsupported += 1
            continue
        seen_calls += 1
        # Stage 3A will validate bounded args, attested identities, and
        # exact previous attempts. Do not persist raw call arguments.
        scoped_proposals.append({"leaf": operation, "args": args})
    frontier = build_stage3_read_frontier(
        receipts,
        model_proposals=scoped_proposals,
        available_read_tools=tuple(sorted({leaf for leaves in permitted.values()
                                           for leaf in leaves})),
        max_choices=12,
    )
    rejected = frontier.get("rejected_candidate_counts") or {}
    return {
        "schema": "homebrain-stage3c-passive-round.v1",
        "shadow_only": True,
        "executes_tools": False,
        "affects_model_prompts": False,
        "affects_tool_choices": False,
        "affects_final_answer": False,
        "model_calls_examined": min(len(model_tool_calls), _MAX_CALLS),
        "model_calls_omitted": max(0, len(model_tool_calls) - _MAX_CALLS),
        "declared_schema_count_examined": min(len(declared_tool_schemas), _MAX_SCHEMAS),
        "read_calls_with_positive_catalog_mapping": seen_calls,
        "unsupported_gateway_or_operation_calls_skipped": skipped_unsupported,
        "invalid_envelopes_skipped": rejected_envelopes,
        "verified_new_candidate_count": frontier["candidate_count"],
        "previous_exact_attempts": rejected.get("exact-read-already-attempted", 0),
        "unattested_id_suppressed": rejected.get("identifier-not-source-attested", 0),
        "invalid_scope_suppressed": rejected.get("invalid-or-unbounded-scope", 0),
        "frontier_scope": "only explicitly enumerated read gateway suboperations",
        "no_source_absence_or_causal_proof": True,
    }


__all__ = ["observe_stage3_model_round"]
