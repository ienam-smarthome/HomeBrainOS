"""Evidence-coverage checks derived from live read receipts, not question words.

This module never issues MCP commands. It identifies missing independent
evidence and gives the model a bounded opportunity to choose an appropriate
READ operation. An event history can establish callers, not root cause.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence


def gap_for_target(witnesses: Sequence[Mapping[str, Any]],
                   focus_ids: Sequence[str],
                   *, can_read_events: bool) -> dict[str, Any] | None:
    if not focus_ids or not can_read_events:
        return None
    focus = set(focus_ids)
    relevant_warnings = []
    has_scoped_history = False
    for witness in witnesses:
        operation = witness.get("operation")
        filters = witness.get("read_filters")
        filters = filters if isinstance(filters, dict) else {}
        if operation == "hub_list_device_events":
            if str(filters.get("deviceId")) in focus:
                has_scoped_history = True
        if operation != "hub_get_logs":
            continue
        payload = witness.get("source_data")
        if not isinstance(payload, dict):
            continue
        summary = payload.get("log_summary")
        if not isinstance(summary, dict):
            continue
        for entry in summary.get("warning_error_groups", [])[:30]:
            if isinstance(entry, dict) and str(entry.get("source_id")) in focus:
                relevant_warnings.append(witness.get("read"))
    if not relevant_warnings or has_scoped_history:
        return None
    return {
        "kind": "target_warning_actor_provenance_unchecked",
        "focus_ids": sorted(focus),
        "supporting_warning_reads": sorted(set(relevant_warnings)),
        "candidate_read": "hub_list_device_events",
        "materiality": "Model must decide whether caller history could clarify this question",
        "limitation": "An issuing app or close timestamp alone does not prove slow-driver causation",
    }


def gateway_offers_operation(manifest: Mapping[str, Any],
                             discovered: Mapping[str, set[str]],
                             operation: str) -> bool:
    for name, tool in manifest.items():
        if not name.startswith("hub_read_"):
            continue
        enum = tool.input_schema.get("properties", {}).get("tool", {}).get("enum")
        if isinstance(enum, list) and operation in enum:
            return True
        if operation in discovered.get(name, set()):
            return True
    return False


def useful_discovery_fingerprint(source: Mapping[str, Any]) -> tuple[str, ...]:
    result = source.get("results")
    if not isinstance(result, list):
        return ()
    return tuple(sorted({
        str(item.get("gateway")) + ":" + str(item.get("tool"))
        for item in result
        if isinstance(item, dict)
        and isinstance(item.get("gateway"), str)
        and isinstance(item.get("tool"), str)
    }))


__all__ = ["gap_for_target", "gateway_offers_operation",
           "useful_discovery_fingerprint"]
