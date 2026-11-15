"""Current-request read-source progress, not answer correctness or coverage.

This is a metadata-only summary of original tool receipts. A failed read
proves that a source was attempted, not that it returned zero events.
Successful transport does NOT prove that the requested target, attribute,
period, history coverage or physical outcome was established.

No extra MCP calls, hidden model inference, synthetic tool receipts or
permission decisions are made by this module.
"""
from __future__ import annotations

import json
from typing import Any

from investigation_review import is_read_only_review_tool


_NON_OBSERVATIONS = frozenset({
    "homebrain_read_prior_evidence", "homebrain_inspect_mcp_catalog",
    "homebrain_read_clock",
})
_READ_RESULT_TYPES = frozenset({"tool_result", "local_monitor_read"})


def current_source_progress(receipts: list[dict] | None) -> dict[str, Any]:
    """Count executed, actual current-request read attempts and successes.

    Distinct successful source *requests* are identified by native tool name
    and canonical argument scope. Multiple identical reads never count as
    multiple independent coverage frontiers. No raw source arguments or
    private values leave this function.
    """
    attempts = 0
    successful = 0
    failed = 0
    successful_scopes: set[str] = set()
    for item in receipts if isinstance(receipts, list) else ():
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if (not isinstance(name, str) or name in _NON_OBSERVATIONS
                or not is_read_only_review_tool(name)):
            continue
        # Some model/tool schema and pre-dispatch validation failures never
        # reached an actual read. Do not count them as executed observations.
        if item.get("operation_executed") is False or (
            item.get("result_kind") not in _READ_RESULT_TYPES
            and item.get("success") is True
        ):
            continue
        attempts += 1
        if item.get("success") is True:
            successful += 1
            args = item.get("arguments")
            # Keys are used for scope counting only, never exposed.
            try:
                key = json.dumps(
                    [name, args if isinstance(args, dict) else {}],
                    sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                    default=str,
                )
            except (TypeError, ValueError):
                key = json.dumps([name, {}])
            successful_scopes.add(key)
        else:
            failed += 1
    return {
        "read_attempts": attempts,
        "successful_read_receipts": successful,
        "failed_read_receipts": failed,
        "distinct_successful_request_scopes": len(successful_scopes),
        "has_successful_current_source": bool(successful_scopes),
        "historical_coverage_verified": False,
        "source_sufficiency_assessed": False,
        "metric_scope": (
            "current-request executed source reads only; read success and "
            "distinct arguments do not prove requested facts, target, window, "
            "nonempty data, retention, independent corroboration or physical cause"
        ),
    }
