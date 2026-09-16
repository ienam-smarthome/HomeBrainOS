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
async def test_request_observation_reconciles_nested_mcp_and_local_path_timings() -> None:
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation() -> AgentOutcome:
        coordinator.metrics.add_ms("mcp", 457)
        return AgentOutcome(
            message="1 room is active: Living Room.",
            request_class="live-read",
            evidence=[
                {
                    "tool": "hub_read_devices",
                    "elapsed_ms": 41118,
                    "success": True,
                },
                {
                    "tool": "homebrain_active_rooms",
                    "elapsed_ms": 41121,
                    "success": True,
                },
            ],
            choices=[],
        )

    outcome = await coordinator.run(operation)

    assert outcome.metrics["timings_ms"]["mcp"] == 41118
    assert outcome.metrics["timings_ms"]["local_tool"] == 41121


@pytest.mark.asyncio
async def test_request_observation_does_not_double_count_existing_mcp_timing() -> None:
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation() -> AgentOutcome:
        coordinator.metrics.add_ms("mcp", 50000)
        return AgentOutcome(
            message="done",
            request_class="live-read",
            evidence=[{"tool": "hub_read_devices", "elapsed_ms": 41118}],
            choices=[],
        )

    outcome = await coordinator.run(operation)

    assert outcome.metrics["timings_ms"]["mcp"] == 50000


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
