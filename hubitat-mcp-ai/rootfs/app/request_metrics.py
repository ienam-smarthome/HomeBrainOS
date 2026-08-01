from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from dataclasses import dataclass, field
from time import monotonic
from typing import Any


@dataclass(slots=True)
class RequestMetricState:
    started_at: float = field(default_factory=monotonic)
    counters: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, int] = field(default_factory=dict)
    outcome: str | None = None


class RequestMetrics:
    """Collect privacy-safe request counters and stage timings.

    Metric keys are fixed internal names. Device labels, prompts, tool arguments,
    tokens, and other user data are never accepted as metric labels.
    """

    ALLOWED_COUNTERS = frozenset({
        "model_rounds",
        "tool_calls",
        "tool_discovery_calls",
        "evidence_retries",
        "grounding_refusals",
        "confirmation_queued",
        "confirmation_expired",
        "mutation_verification_failures",
        "request_cancellations",
        "device_resolution_ambiguous",
    })
    ALLOWED_TIMINGS = frozenset({
        "provider",
        "tool_discovery",
        "mcp",
        "verification",
        "total",
    })
    ALLOWED_OUTCOMES = frozenset({
        "success",
        "refused",
        "cancelled",
        "failed",
    })

    def __init__(self) -> None:
        self._state: ContextVar[RequestMetricState | None] = ContextVar(
            "homebrain_request_metrics",
            default=None,
        )

    def begin(self) -> Token:
        return self._state.set(RequestMetricState())

    def reset(self, token: Token) -> None:
        self._state.reset(token)

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self.ALLOWED_COUNTERS:
            raise ValueError(f"Unsupported metric counter: {name}")
        state = self._state.get()
        if state is None:
            return
        state.counters[name] = state.counters.get(name, 0) + max(0, int(amount))

    def observe_ms(self, name: str, elapsed_ms: int | float) -> None:
        if name not in self.ALLOWED_TIMINGS:
            raise ValueError(f"Unsupported metric timing: {name}")
        state = self._state.get()
        if state is None:
            return
        state.timings_ms[name] = max(0, round(float(elapsed_ms)))

    def finish(self, outcome: str) -> dict[str, Any]:
        if outcome not in self.ALLOWED_OUTCOMES:
            raise ValueError(f"Unsupported request outcome: {outcome}")
        state = self._state.get()
        if state is None:
            return {"outcome": outcome, "counters": {}, "timings_ms": {}}
        state.outcome = outcome
        state.timings_ms.setdefault(
            "total",
            max(0, round((monotonic() - state.started_at) * 1000)),
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


__all__ = ["RequestMetricState", "RequestMetrics"]
