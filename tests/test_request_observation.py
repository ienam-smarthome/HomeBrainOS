from __future__ import annotations

import asyncio

import pytest

from mcp_agent_orchestrator import AgentOutcome
from request_metrics import RequestMetrics
from request_observation import RequestObservationCoordinator


@pytest.mark.asyncio
async def test_request_observation_builds_observed_outcome() -> None:
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation() -> AgentOutcome:
        return AgentOutcome(
            message="done",
            request_class="read",
            evidence=[{"tool": "hub_read_devices"}],
            choices=[],
            confirmation_required=True,
            confirmation_count=1,
        )

    outcome = await coordinator.run(operation)

    assert outcome.message == "done"
    assert outcome.metrics["outcome"] == "success"
    assert outcome.metrics["counters"]["tool_calls"] == 1
    assert outcome.metrics["counters"]["confirmation_queued"] == 1


@pytest.mark.asyncio
async def test_request_observation_reraises_cancellation() -> None:
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation() -> AgentOutcome:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await coordinator.run(operation)


@pytest.mark.asyncio
async def test_request_observation_reraises_failure() -> None:
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation() -> AgentOutcome:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await coordinator.run(operation)
