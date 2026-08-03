from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp_agent_orchestrator import AgentOutcome


@dataclass(slots=True)
class ObservedAgentOutcome(AgentOutcome):
    """Agent result with a privacy-safe, request-local metrics snapshot."""

    metrics: dict[str, Any] = field(default_factory=dict)


def build_observed_agent_outcome(
    outcome: AgentOutcome,
    metrics: dict[str, Any],
) -> ObservedAgentOutcome:
    """Copy a base agent result into the production observed result contract."""

    return ObservedAgentOutcome(
        message=outcome.message,
        request_class=outcome.request_class,
        evidence=outcome.evidence,
        choices=outcome.choices,
        confirmation_required=outcome.confirmation_required,
        confirmation_count=outcome.confirmation_count,
        metrics=metrics,
    )


__all__ = ["ObservedAgentOutcome", "build_observed_agent_outcome"]
