from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from request_outcome_policy import classify_completed_request


@dataclass(slots=True)
class RequestMetricState:
    started_at: float = field(default_factory=monotonic)
    counters: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, int] = field(default_factory=dict)
    outcome: str | None = None
    model_round_details: list[dict[str, str]] = field(default_factory=list)
    paid_guard: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RequestMetricToken:
    state: Token
    active: Token


_ACTIVE_REQUEST_METRICS: ContextVar[RequestMetrics | None] = ContextVar(
    "homebrain_active_request_metrics",
    default=None,
)


class RequestMetrics:
    """Collect privacy-safe request counters and stage timings."""

    ALLOWED_COUNTERS = frozenset({
        "paid_model_requested", "paid_model_reserved", "paid_model_selected",
        "paid_routing_disabled", "paid_routing_budget_disabled",
        "paid_routing_reservation_blocked",
        "ai_read_route_arbitrated", "ai_read_route_model_led",
        "ai_read_route_system_audit", "ai_read_route_performance",
        "ai_read_route_fallback",
        "model_rounds", "tool_calls", "tool_discovery_calls", "mcp_retries",
        "conversation_recall_no_mcp",
        "mcp_concurrent_peak",
        "evidence_retries", "grounding_refusals", "confirmation_queued",
        "confirmation_expired", "confirmation_evicted",
        "mutation_verification_failures",
        "proposal_validation_failures", "proposal_write_attempts_blocked",
        "write_unverified_no_confirmation", "rule_create_staging_unverified",
        "planner_write_intent_corrected",
        "rule_night_idle_fastpath", "rule_create_timeout_found",
        "rule_create_timeout_unknown",
        "rule_schedule_fastpath", "rule_schedule_gateway_missing",
        "task_evidence_retry", "task_evidence_incomplete",
        "unified_investigation_input_followup",
        "target_history_scope_retry", "unscoped_history_claim_rejected",
        "unified_investigation_evidence_bridge",
        "unified_group_timeline_reconciled",
        "unified_group_journal_recovery", "unified_input_journal_recovery",
        "causal_journal_discovery_checkpoint", "causal_initiator_unresolved",
        "unified_recent_edge_checked",
        "unified_recent_edge_reconciled",
        "unified_group_app_log_checks",
        "shared_completion_checked", "shared_completion_partial",
        "request_cancellations", "device_resolution_ambiguous",
        "device_resolution_missing", "device_control_failures",
        "device_control_needs_input",
        "resolution_cache_hit", "resolution_cache_metadata_miss",
        "control_local_identity_cache_hit", "control_identity_lookup",
        "control_confirmation_preview_cache",
        "control_confirmation_manifest_fallback",
        "control_confirmation_fresh_revalidation",
        "identity_cache_hit", "identity_refresh",
        "evidence_sufficiency_stop", "source_trace_sufficiency_stop",
        "source_method_projection_added",
        "investigation_snapshot_shortcut_bypassed",
        "investigation_source_target_mismatch",
        "investigation_inventory_only_retry",
        "investigation_inventory_only_stopped",
        "investigation_unfulfilled_at_boundary",
        "device_incident_depth_retry", "device_incident_progress_retry",
        "incident_evidence_checkpoint_retry",
        "investigation_read_reflection", "investigation_general_evidence_retry",
        "investigation_write_blocked", "investigation_reflection_synthesized",
        "investigation_grounded_fallback",
        "evidence_claim_calibrations",
        "causal_room_plan", "causal_cached_candidate_plan", "causal_cached_context_shape_plan", "causal_cached_candidate_plan_fallback", "causal_provenance_read", "causal_sensor_read", "causal_sensor_aligned", "causal_location_read", "causal_app_navigation", "causal_provenance_aligned", "causal_completion_retry", "causal_inferred_attribute_retry", "causal_subject_prefetch", "causal_group_clarification", "causal_clarification_resume", "causal_command_producer_reads", "causal_command_producer_provenance", "causal_boundary_producer_provenance", "causal_reporting_source_correlation", "causal_subject_pattern_read", "causal_level_recovery_pattern", "causal_known_automation_match", "causal_composite_sensor_match", "causal_topology_sensor_plan", "causal_topology_sensor_fallback", "causal_native_log_reads", "causal_native_log_correlations", "causal_native_app_execution_provenance", "causal_repeated_controller_pattern", "causal_open_start_provenance", "causal_deterministic_finalization", "causal_subject_empty_stop", "investigative_finalization",
        "lockout_prefetch_sufficiency_stop",
        "lockout_cross_source_sufficiency_stop",
        "lockout_focal_evidence_report",
        "investigative_attribute_required", "gateway_operation_rejected", "gateway_read_rerouted",
        "history_attribute_rejected", "history_known_tool_fastpath",
        "semantic_fastpath_plans", "semantic_planner_plans",
        "semantic_planner_failures", "semantic_plan_compile_failures",
        "semantic_relative_controls", "semantic_temperature_controls",
        "semantic_world_context", "semantic_target_grounded",
        "semantic_needs_input",
        "broad_performance_host_plan",
        "broad_performance_host_plan_jobs",
        "scheduler_inventory_crosscheck",
        "scheduler_inventory_timeout",
        "scheduler_inventory_read_failure",
        "performance_adaptive_expansion",
        "performance_adaptive_reads",
        "performance_adaptive_device_target",
        "performance_adaptive_app_target",
        "performance_adaptive_read_failures",
        "broad_performance_log_host_attempt",
        "broad_performance_log_host_success",
        "broad_performance_log_host_retry",
        "broad_performance_log_host_unavailable",
        "broad_performance_log_host_failed",
        "rule_analysis_partial", "historical_rule_execution_routed",
        "historical_command_obligation_reads",
        "historical_command_obligation_unavailable",
        "historical_provenance_app_log_reads",
        "historical_provenance_app_log_failures",
        "historical_provenance_app_log_unavailable",
        "read_only_model_write_blocked",
        "requested_device_drift_guard", "unscoped_historical_logs_blocked",
        "causal_adaptive_expansion", "causal_adaptive_sensor_reads",
        "causal_focal_window_reads", "causal_focal_window_evidence_recovered",
        "causal_focal_history_gap_stop",
        "causal_adaptive_sufficient_stop", "causal_adaptive_candidate_plans",
        "causal_adaptive_unexamined_candidates",
        "causal_graph_mode_reads", "causal_graph_sufficient",
        "causal_local_off_evidence_stop", "causal_completed_unresolved",
        "causal_physical_response_reads",
        "causal_off_provenance_reads", "causal_off_command_reused",
        "causal_off_app_log_reads", "causal_off_app_config_reads",
        "causal_archived_app_log_checks", "causal_broad_inventory_blocked",
        "causal_controller_sufficient_stop", "causal_physical_command_reused",
        "answer_quality_gaps_found", "answer_quality_revision_rounds",
        "answer_quality_revision_rejected", "answer_quality_revision_incomplete",
        "answer_quality_revision_accepted",
        "configuration_semantics_source_retry",
        "source_focus_repair_attempted", "source_focus_repair_satisfied",
        "source_focus_repair_unresolved", "groovy_source_reads_reused",
        "synthesis_validation_issues", "synthesis_localized_corrections",
        "synthesis_repair_rounds", "synthesis_repair_causal_coverage",
        "synthesis_repair_causal_provenance", "synthesis_repair_performance",
        "synthesis_repair_other", "synthesis_repair_failed", "synthesis_causal_fail_closed", "telemetry_claims_reconciled",
        "typed_device_history_projections",
        "causal_configured_sensor_prioritized",
        "causal_historical_sensor_fallback_reads",
        "causal_irrelevant_off_skipped", "causal_preceding_command_clues", "causal_final_output_reconciled",
        "skills_framework_activated", "skills_topology_plan", "skills_required_source_read", "skills_grounded_answer_selected", "skills_focal_state_window", "skills_focal_producer_logs", "skills_focal_state_rows_retained", "skills_focal_read_failed", "skills_focal_unverified_stop", "skills_early_focal_stop", "skills_focal_journal_read", "skills_focal_journal_on_recovered", "skills_focal_journal_failed",
        "causal_read_round_budget", "causal_read_round_budget_exhausted",
        "ollama_empty_message_recovery", "ollama_empty_message_recovery_failed",
        "ollama_cloud_failover_eligible", "ollama_authorized_cloud_failover",
        "ollama_cloud_to_local_fallback", "ollama_free_quota_paid_escalation",
    })
    ALLOWED_TIMINGS = frozenset({
        "provider", "tool_discovery", "mcp", "mcp_lock_wait",
        "mcp_queue_wait", "mcp_session_lock_wait", "mcp_http",
        "mcp_shared_wait", "local_tool", "verification", "total",
    })
    ALLOWED_PAID_GUARD_STATUSES = frozenset({
        "disabled", "zero_budget", "round_exceeds_budget", "invalid_ledger",
        "storage_unavailable", "reserved", "no_local_budget", "unknown_model",
    })
    ALLOWED_OUTCOMES = frozenset({
        "success", "needs_input", "refused", "unresolved", "cancelled", "failed",
    })

    def __init__(self) -> None:
        self._state: ContextVar[RequestMetricState | None] = ContextVar(
            "homebrain_request_metrics", default=None
        )

    def begin(self) -> RequestMetricToken:
        return RequestMetricToken(
            state=self._state.set(RequestMetricState()),
            active=_ACTIVE_REQUEST_METRICS.set(self),
        )

    def reset(self, token: RequestMetricToken) -> None:
        _ACTIVE_REQUEST_METRICS.reset(token.active)
        self._state.reset(token.state)

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self.ALLOWED_COUNTERS:
            raise ValueError(f"Unsupported metric counter: {name}")
        state = self._state.get()
        if state is not None:
            state.counters[name] = state.counters.get(name, 0) + max(0, int(amount))

    def observe_counter_max(self, name: str, value: int) -> None:
        if name not in self.ALLOWED_COUNTERS:
            raise ValueError(f"Unsupported metric counter: {name}")
        state = self._state.get()
        if state is not None:
            state.counters[name] = max(
                state.counters.get(name, 0),
                max(0, int(value)),
            )

    def record_provider_model(self, model: str, provider: str) -> None:
        """Record only provider/model per successful HTTP model round."""
        state = self._state.get()
        if state is not None and model and provider and len(state.model_round_details) < 64:
            state.model_round_details.append({"model": str(model)[:100], "provider": provider})

    def observe_ms(self, name: str, elapsed_ms: int | float) -> None:
        if name not in self.ALLOWED_TIMINGS:
            raise ValueError(f"Unsupported metric timing: {name}")
        state = self._state.get()
        if state is not None:
            state.timings_ms[name] = max(0, round(float(elapsed_ms)))

    def add_ms(self, name: str, elapsed_ms: int | float) -> None:
        if name not in self.ALLOWED_TIMINGS:
            raise ValueError(f"Unsupported metric timing: {name}")
        state = self._state.get()
        if state is not None:
            state.timings_ms[name] = state.timings_ms.get(name, 0) + max(
                0, round(float(elapsed_ms))
            )

    def completed_outcome(self) -> str:
        """Classify a normally returned request without inspecting its message."""

        state = self._state.get()
        return classify_completed_request(state.counters if state is not None else None)

    def finish(self, outcome: str) -> dict[str, Any]:
        if outcome not in self.ALLOWED_OUTCOMES:
            raise ValueError(f"Unsupported request outcome: {outcome}")
        state = self._state.get()
        if state is None:
            return {"outcome": outcome, "counters": {}, "timings_ms": {}}
        state.outcome = outcome
        state.timings_ms.setdefault(
            "total", max(0, round((monotonic() - state.started_at) * 1000))
        )
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        state = self._state.get()
        if state is None:
            return {"outcome": None, "counters": {}, "timings_ms": {}}
        result = {
            "outcome": state.outcome,
            "counters": state.counters,
            "timings_ms": state.timings_ms,
        }
        if state.model_round_details:
            result["model_round_details"] = state.model_round_details
        if state.paid_guard:
            result["paid_guard"] = state.paid_guard
        return deepcopy(result)

    def record_paid_guard(self, status: str, *, budget_usd: float | None = None,
                          already_reserved_usd: float | None = None,
                          estimated_round_usd: float | None = None) -> None:
        if status not in self.ALLOWED_PAID_GUARD_STATUSES:
            raise ValueError('Unsupported paid guard status')
        state = self._state.get()
        if state is None:
            return
        amounts = {
            'configured_budget_usd': budget_usd,
            'already_reserved_usd': already_reserved_usd,
            'estimated_round_usd': estimated_round_usd,
        }
        # A bounded, allowlisted diagnostic without prompts, keys or paths.
        state.paid_guard = {'status': status}
        for key, value in amounts.items():
            if value is not None:
                state.paid_guard[key] = round(float(value), 4)
        if budget_usd is not None and already_reserved_usd is not None:
            state.paid_guard['remaining_estimated_budget_usd'] = round(
                max(0.0, float(budget_usd) - float(already_reserved_usd)), 4
            )

    def active_request_identity(self) -> object | None:
        """Return the current request state object for request-local coordination."""

        return self._state.get()


def active_request_identity() -> object | None:
    """Return an opaque identity unique to the active observed request."""

    metrics = _ACTIVE_REQUEST_METRICS.get()
    return metrics.active_request_identity() if metrics is not None else None


def record_active_paid_guard(status: str, *, budget_usd: float | None = None,
                             already_reserved_usd: float | None = None,
                             estimated_round_usd: float | None = None) -> None:
    metrics = _ACTIVE_REQUEST_METRICS.get()
    if metrics is not None:
        metrics.record_paid_guard(status, budget_usd=budget_usd,
                                  already_reserved_usd=already_reserved_usd,
                                  estimated_round_usd=estimated_round_usd)


def increment_active_metric(name: str, amount: int = 1) -> None:
    metrics = _ACTIVE_REQUEST_METRICS.get()
    if metrics is not None:
        metrics.increment(name, amount)


def record_active_provider_model(model: str, provider: str) -> None:
    metrics = _ACTIVE_REQUEST_METRICS.get()
    if metrics is not None:
        metrics.record_provider_model(model, provider)


def add_active_metric_ms(name: str, elapsed_ms: int | float) -> None:
    metrics = _ACTIVE_REQUEST_METRICS.get()
    if metrics is not None:
        metrics.add_ms(name, elapsed_ms)


def observe_active_metric_max(name: str, value: int) -> None:
    metrics = _ACTIVE_REQUEST_METRICS.get()
    if metrics is not None:
        metrics.observe_counter_max(name, value)


__all__ = [
    "RequestMetricState", "RequestMetricToken", "RequestMetrics",
    "active_request_identity", "increment_active_metric", "add_active_metric_ms",
    "observe_active_metric_max", "record_active_provider_model",
    "record_active_paid_guard",
]
