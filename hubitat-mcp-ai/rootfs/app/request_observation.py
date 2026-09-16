from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import ObservedAgentOutcome, build_observed_agent_outcome
from request_metrics import RequestMetrics


class RequestObservationCoordinator:
    """Own one request's metrics lifecycle and observed outcome construction."""

    def __init__(self, metrics: RequestMetrics) -> None:
        self.metrics = metrics

    @staticmethod
    def _elapsed_ms(receipt: Any) -> int:
        if not isinstance(receipt, dict):
            return 0
        try:
            return max(0, int(receipt.get("elapsed_ms") or 0))
        except (TypeError, ValueError):
            return 0

    def _reconcile_evidence_timings(self, outcome: AgentOutcome) -> None:
        """Make request timings reflect nested MCP work performed by local adapters.

        ToolExecutor records direct remote calls in the ``mcp`` bucket, but local
        ``homebrain_*`` adapters can themselves call the Hubitat MCP client. Those
        nested calls already emit authoritative evidence receipts with their own
        elapsed time, yet historically that time was absent from ``timings_ms``.
        A live ``Which rooms are active?`` request demonstrated the gap clearly:
        ``hub_read_devices`` took ~41 s while the request metrics claimed MCP used
        only ~0.5 s (the separate discovery call).

        Reconcile, rather than add, the longest observed ``hub_*`` evidence span
        into the MCP timing. Using a floor avoids double-counting calls that were
        already measured by ToolExecutor while ensuring a slow nested read can no
        longer disappear from the technical-details panel. Also expose the longest
        local adapter path separately; it intentionally includes any nested MCP
        work and is therefore a diagnostic path duration, not an additive stage.
        """

        evidence = list(getattr(outcome, "evidence", []) or [])
        remote_floor = max(
            (
                self._elapsed_ms(item)
                for item in evidence
                if isinstance(item, dict)
                and str(item.get("tool") or "").startswith("hub_")
            ),
            default=0,
        )
        local_path = max(
            (
                self._elapsed_ms(item)
                for item in evidence
                if isinstance(item, dict)
                and str(item.get("tool") or "").startswith("homebrain_")
            ),
            default=0,
        )

        current = self.metrics.snapshot().get("timings_ms", {})
        if not isinstance(current, dict):
            current = {}
        try:
            current_mcp = max(0, int(current.get("mcp") or 0))
        except (TypeError, ValueError):
            current_mcp = 0
        if remote_floor > current_mcp:
            self.metrics.observe_ms("mcp", remote_floor)
        if local_path > 0:
            self.metrics.observe_ms("local_tool", local_path)

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
            self._reconcile_evidence_timings(outcome)
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
