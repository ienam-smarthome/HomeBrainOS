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
        "model_rounds", "tool_calls", "tool_discovery_calls", "mcp_retries",
        "mcp_concurrent_peak",
        "evidence_retries", "grounding_refusals", "confirmation_queued",
        "confirmation_expired", "confirmation_evicted",
        "mutation_verification_failures",
        "proposal_validation_failures",
        "request_cancellations", "device_resolution_ambiguous",
        "device_resolution_missing", "device_control_failures",
        "device_control_needs_input",
        "resolution_cache_hit", "resolution_cache_metadata_miss",
        "control_local_identity_cache_hit", "control_identity_lookup",
        "identity_cache_hit", "identity_refresh",
        "evidence_sufficiency_stop",
        "causal_room_plan", "causal_provenance_read", "causal_sensor_read", "causal_sensor_aligned", "causal_location_read", "causal_app_navigation", "causal_provenance_aligned", "causal_completion_retry", "causal_inferred_attribute_retry", "causal_subject_prefetch", "causal_command_producer_reads", "causal_command_producer_provenance", "causal_native_log_reads", "causal_native_log_correlations", "causal_repeated_controller_pattern", "causal_open_start_provenance", "causal_deterministic_finalization", "causal_subject_empty_stop", "investigative_finalization",
        "investigative_attribute_required", "gateway_operation_rejected",
        "history_attribute_rejected", "history_known_tool_fastpath",
        "semantic_fastpath_plans", "semantic_planner_plans",
        "semantic_planner_failures", "semantic_plan_compile_failures",
        "semantic_relative_controls", "semantic_temperature_controls",
        "semantic_world_context", "semantic_target_grounded",
        "semantic_needs_input",
    })
    ALLOWED_TIMINGS = frozenset({
        "provider", "tool_discovery", "mcp", "mcp_lock_wait",
        "mcp_queue_wait", "mcp_session_lock_wait", "mcp_http",
        "mcp_shared_wait", "local_tool", "verification", "total",
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
        return deepcopy({
            "outcome": state.outcome,
            "counters": state.counters,
            "timings_ms": state.timings_ms,
        })

    def active_request_identity(self) -> object | None:
        """Return the current request state object for request-local coordination."""

        return self._state.get()


def active_request_identity() -> object | None:
    """Return an opaque identity unique to the active observed request."""

    metrics = _ACTIVE_REQUEST_METRICS.get()
    return metrics.active_request_identity() if metrics is not None else None


def increment_active_metric(name: str, amount: int = 1) -> None:
    metrics = _ACTIVE_REQUEST_METRICS.get()
    if metrics is not None:
        metrics.increment(name, amount)


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
    "observe_active_metric_max",
]
