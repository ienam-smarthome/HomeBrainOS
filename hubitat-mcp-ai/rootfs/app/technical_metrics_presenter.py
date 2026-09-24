from __future__ import annotations

from typing import Any


_COUNTER_LABELS = (
    ("model_rounds", "Model rounds"),
    ("tool_calls", "Tool calls"),
    ("tool_discovery_calls", "Tool discovery calls"),
    ("mcp_retries", "MCP retries"),
    ("mcp_concurrent_peak", "MCP concurrent peak"),
    ("evidence_retries", "Evidence retries"),
    ("grounding_refusals", "Grounding refusals"),
    ("confirmation_queued", "Confirmations queued"),
    ("confirmation_expired", "Confirmations expired"),
    ("confirmation_evicted", "Confirmations evicted"),
    ("mutation_verification_failures", "Verification failures"),
    ("proposal_validation_failures", "Proposal validation failures"),
    ("device_control_failures", "Device control failures"),
    ("device_control_needs_input", "Device controls needing input"),
    ("request_cancellations", "Cancellations"),
    ("device_resolution_ambiguous", "Ambiguous resolutions"),
    ("device_resolution_missing", "Missing-device resolutions"),
    ("resolution_cache_hit", "Resolution cache hits"),
    ("resolution_cache_metadata_miss", "Resolution cache metadata misses"),
    ("control_local_identity_cache_hit", "Control identity cache hits"),
    ("control_identity_lookup", "Control identity refreshes"),
    ("identity_cache_hit", "Identity cache hits"),
    ("identity_refresh", "Identity refreshes"),
    ("causal_room_plan", "Causal room plans"),
    ("causal_provenance_read", "Causal provenance reads"),
    ("causal_sensor_read", "Causal motion/presence reads"),
    ("causal_sensor_aligned", "Causal sensor boundary alignments"),
    ("causal_location_read", "Causal location reads"),
    ("causal_app_navigation", "Causal app navigation loads"),
    ("causal_provenance_aligned", "Aligned provenance events"),
    ("causal_completion_retry", "Causal completion retries"),
    ("causal_inferred_attribute_retry", "Causal inferred-state retries"),
    ("causal_subject_prefetch", "Causal subject prefetches"),
    ("causal_command_producer_reads", "Command-producer reads"),
    ("causal_command_producer_provenance", "Command-producer provenance"),
    ("causal_boundary_producer_provenance", "Boundary producer provenance"),
    ("causal_reporting_source_correlation", "Reporting-source correlation passes"),
    ("causal_native_log_reads", "Causal native-log reads"),
    ("causal_native_log_correlations", "Causal native-log correlations"),
    ("causal_repeated_controller_pattern", "Repeated controller patterns"),
    ("causal_open_start_provenance", "Open-start controller provenance"),
    ("causal_deterministic_finalization", "Deterministic causal finalizations"),
    ("causal_subject_empty_stop", "Empty-subject causal stops"),
    ("causal_broad_inventory_blocked", "Blocked broad causal inventories"),
    ("investigative_finalization", "Investigative finalizations"),
    ("evidence_sufficiency_stop", "Evidence sufficiency stops"),
    ("investigative_attribute_required", "Investigative attribute retries"),
    ("gateway_operation_rejected", "Gateway operation rejections"),
    ("history_attribute_rejected", "History attribute rejections"),
    ("history_known_tool_fastpath", "Known-history fast paths"),
    ("semantic_fastpath_plans", "Semantic fast-path plans"),
    ("semantic_planner_plans", "Semantic AI plans"),
    ("semantic_planner_failures", "Semantic planner failures"),
    ("semantic_plan_compile_failures", "Semantic compile failures"),
    ("semantic_relative_controls", "Relative semantic controls"),
    ("semantic_temperature_controls", "Semantic thermostat controls"),
    ("semantic_world_context", "Capability-grounded semantic contexts"),
    ("semantic_target_grounded", "Semantic targets host-grounded"),
    ("semantic_needs_input", "Semantic clarifications"),
)

_DURATION_LABELS = (
    ("provider", "Provider"),
    ("mcp", "MCP"),
    ("mcp_lock_wait", "MCP lock wait"),
    ("mcp_queue_wait", "MCP queue wait"),
    ("mcp_session_lock_wait", "MCP session lock wait"),
    ("mcp_shared_wait", "MCP shared-read wait"),
    ("mcp_http", "MCP HTTP"),
    ("local_tool", "Local tool path"),
    ("tool_discovery", "Discovery"),
    ("verification", "Verification"),
    ("total", "Total"),
)

_OUTCOME_PRESENTATION = {
    "success": {"label": "Success", "tone": "positive"},
    "needs_input": {"label": "Needs input", "tone": "warning"},
    "unresolved": {"label": "Unresolved", "tone": "warning"},
    "refused": {"label": "Refused", "tone": "warning"},
    "cancelled": {"label": "Cancelled", "tone": "neutral"},
    "failed": {"label": "Failed", "tone": "critical"},
}


def _non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _duration_text(milliseconds: float) -> str:
    if milliseconds < 1000:
        return f"{round(milliseconds):d} ms"
    seconds = milliseconds / 1000
    return f"{seconds:.1f} s"


def present_request_outcome(value: Any) -> dict[str, str] | None:
    """Return stable, UI-safe presentation metadata for a fixed outcome value."""

    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    presentation = _OUTCOME_PRESENTATION.get(normalized)
    if presentation is None:
        return None
    return {"value": normalized, **presentation}


def present_request_metrics(metrics: Any) -> list[dict[str, str]]:
    """Return stable, human-readable rows for a RequestMetrics snapshot."""

    if not isinstance(metrics, dict):
        return []
    counters = metrics.get("counters")
    timings = metrics.get("timings_ms")
    if not isinstance(counters, dict):
        counters = {}
    if not isinstance(timings, dict):
        timings = {}

    rows: list[dict[str, str]] = []
    for key, label in _COUNTER_LABELS:
        number = _non_negative_number(counters.get(key))
        if number is None or number == 0:
            continue
        rows.append({"label": label, "value": str(int(number))})
    for key, label in _DURATION_LABELS:
        number = _non_negative_number(timings.get(key))
        if number is None:
            continue
        rows.append({"label": label, "value": _duration_text(number)})

    outcome = present_request_outcome(metrics.get("outcome"))
    if outcome is not None:
        rows.append({"label": "Outcome", "value": outcome["value"]})
    return rows


__all__ = ["present_request_metrics", "present_request_outcome"]
