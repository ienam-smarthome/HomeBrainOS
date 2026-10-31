"""Stage 3E: strictly aggregate, offline-only export of Stage 3D trace results.

Source traces may contain private identifiers and model arguments. This
module never emits a copied source value, individual case ID, raw receipt,
prompt, tool call, evidence timestamp, model text or credential. It computes
locally with Stage 3D and returns only allowlisted categories and counts.

This is NOT a trace capture service or a provenance authenticator. The
production agent does not import it and no network, filesystem, or MCP
operation occurs here.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from stage3_controlled_replay import evaluate_stage3d_replay

_MAX_CASES = 24
_MAX_ROUNDS_PER_CASE = 12
_MAX_CALLS = 16
_MAX_SCHEMAS = 60
_MAX_RECEIPTS = 160
_DOMAINS = frozenset((
    "lighting", "heating", "ventilation", "power", "history",
    "security", "connectivity", "sensors", "media", "other",
))
_ORIGINS = frozenset((
    "constructed-fixture", "anonymised-reconstruction",
    "user-labelled-redacted-trace",
))
_MIN_DOMAIN_CELL = 3


def _ready_input(cases: Any) -> Sequence[Mapping[str, Any]]:
    """Reject truncation and invalid provenance instead of hiding omissions."""
    if not isinstance(cases, (list, tuple)) or not 1 <= len(cases) <= _MAX_CASES:
        raise ValueError("invalid or over-limit trace case count")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("invalid trace case")
        if case.get("trace_origin") not in _ORIGINS:
            raise ValueError("missing recognised trace provenance label")
        if case.get("domain") not in _DOMAINS:
            raise ValueError("unrecognised domain category")
        rounds = case.get("rounds")
        if not isinstance(rounds, (list, tuple)) or not 1 <= len(rounds) <= _MAX_ROUNDS_PER_CASE:
            raise ValueError("invalid or over-limit round count")
        for round_row in rounds:
            if not isinstance(round_row, Mapping):
                raise ValueError("invalid trace round")
            for key, maximum in (
                ("receipts_before", _MAX_RECEIPTS),
                ("model_tool_calls", _MAX_CALLS),
                ("declared_tool_schemas", _MAX_SCHEMAS),
            ):
                value = round_row.get(key)
                if not isinstance(value, (list, tuple)) or len(value) > maximum:
                    raise ValueError("invalid or over-limit trace field")
    return cases


def _int(value: Any) -> int:
    return max(0, int(value)) if type(value) is int else 0


def _quality(result: Mapping[str, Any], side: str) -> dict[str, Any]:
    # No per-case values, raw input strings or untrusted keys.
    return {
        "macro_recall_at_k": result[f"{side}_macro_oracle_recall_at_k"],
        "macro_precision_at_k": result[f"{side}_macro_precision_at_k"],
    }


def build_stage3e_private_trace_report(
    cases: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    """Evaluate locally, return a shareable, strictly allowlisted aggregate.

    User-labelled input is *not* independently authenticated. A passing
    fixture score cannot unlock production or establish a live quality gain.
    No raw identifiers survive into the returned object.
    """
    safe_cases = _ready_input(cases)
    replay = evaluate_stage3d_replay(safe_cases, top_k=top_k)
    sources = Counter(c["trace_origin"] for c in safe_cases)
    domains = Counter(c["domain"] for c in safe_cases)
    # Per-domain counts are suppressed for small cells. Domain titles come
    # from this source-code allowlist, never from trace labels.
    visible_domains = {
        domain: count for domain, count in sorted(domains.items())
        if domain in _DOMAINS and count >= _MIN_DOMAIN_CELL
    }
    hidden_domains = sum(count for domain, count in domains.items()
                         if domain not in visible_domains)

    rounds = (round_row for case in replay["cases"]
              for round_row in case["rounds"])
    round_rows = list(rounds)
    captured_or_user_labelled = sources.get("user-labelled-redacted-trace", 0)
    return {
        "schema": "homebrain-stage3e-private-aggregate.v1",
        "origin": "local-in-memory-computation",
        "offline_only": True,
        "source_case_count": len(safe_cases),
        "round_count": _int(replay["round_count"]),
        "independently_scored_rounds": _int(replay["oracle_scored_rounds"]),
        "unscored_rounds": _int(replay["oracle_unscored_rounds"]),
        "top_k": _int(replay["top_k"]),
        "origins": {
            "constructed_fixture": _int(sources.get("constructed-fixture", 0)),
            "anonymised_reconstruction": _int(sources.get("anonymised-reconstruction", 0)),
            "user_labelled_redacted_trace": _int(captured_or_user_labelled),
        },
        "domains_with_at_least_three_cases": visible_domains,
        "small_domain_case_counts_suppressed": _int(hidden_domains),
        "model_original": _quality(replay, "model"),
        "stage3_frontier": _quality(replay, "shadow"),
        "total_duplicate_attempts_suppressed": _int(
            replay["total_duplicate_attempts_suppressed"]),
        "total_unattested_ids_suppressed": _int(
            replay["total_unattested_ids_suppressed"]),
        "total_invalid_scopes_suppressed": _int(
            replay["total_invalid_scopes_suppressed"]),
        "total_unsupported_operations_skipped": sum(
            _int(row["unsupported_operations_skipped"]) for row in round_rows),
        "total_malformed_envelopes_skipped": sum(
            _int(row["unparseable_envelopes_skipped"]) for row in round_rows),
        "data_provenance": "user-supplied-not-independently-authenticated",
        "independently_authenticated_genuine_traces": 0,
        "live_quality_improvement_verified": False,
        "end_to_end_latency_measured": False,
        "physical_ack_or_causal_initiator_proven": False,
        "enablement_decision": "blocked-pending-independent-trace-verification",
        "can_trigger_live_activation": False,
        "raw_device_ids_or_tool_arguments_in_output": False,
        "raw_input_saved_or_transmitted": False,
    }


__all__ = ["build_stage3e_private_trace_report"]
