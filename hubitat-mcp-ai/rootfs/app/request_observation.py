from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import ObservedAgentOutcome, build_observed_agent_outcome
from request_metrics import RequestMetrics


class RequestObservationCoordinator:
    """Own one request's metrics lifecycle and observed outcome construction."""

    def __init__(self, metrics: RequestMetrics) -> None:
        self.metrics = metrics

    async def run(
        self,
        operation: Callable[[], Awaitable[AgentOutcome]],
    ) -> ObservedAgentOutcome:
        metrics_token = self.metrics.begin()
        try:
            outcome = await operation()
            self.metrics.increment("tool_calls", len(outcome.evidence))
            if outcome.confirmation_required:
                self.metrics.increment("confirmation_queued")
            metrics = self.metrics.finish(self.metrics.completed_outcome())
            return build_observed_agent_outcome(outcome, metrics)
        except asyncio.CancelledError:
            self.metrics.increment("request_cancellations")
            self.metrics.finish("cancelled")
            raise
        except Exception:
            self.metrics.finish("failed")
            raise
        finally:
            self.metrics.reset(metrics_token)


__all__ = ["RequestObservationCoordinator"]
