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
    assert outcome.metrics["outcome"] == "needs_input"
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


@pytest.mark.asyncio
async def test_blocked_write_attempt_cannot_claim_pending_actuation():
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation():
        coordinator.metrics.increment("proposal_write_attempts_blocked")
        return AgentOutcome(
            message=(
                "To turn off everything except the freezer, I will turn "
                "off the fridge and the kettle."
            ),
            request_class="live-read",
            evidence=[{
                "tool": "hub_read_devices", "mutates": False, "effect": "read",
                "success": True,
            }],
            choices=[],
        )

    result = await coordinator.run(operation)
    assert result.metrics["outcome"] == "unresolved"
    assert result.message.startswith("**Nothing was changed.**")
    assert "I will turn" not in result.message
    assert result.metrics["counters"]["proposal_write_attempts_blocked"] == 1


@pytest.mark.asyncio
async def test_blocked_write_correction_does_not_suppress_ordinary_read_answer():
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation():
        coordinator.metrics.increment("proposal_write_attempts_blocked")
        return AgentOutcome(
            message="The freezer is currently on, based on Hubitat.",
            request_class="live-read", choices=[],
            evidence=[{"tool": "hub_read_devices", "mutates": False}],
        )

    result = await coordinator.run(operation)
    assert "freezer is currently on" in result.message


@pytest.mark.asyncio
async def test_blocked_write_correction_never_claims_zero_writes_if_any_occurred():
    coordinator = RequestObservationCoordinator(RequestMetrics())

    async def operation():
        coordinator.metrics.increment("proposal_write_attempts_blocked")
        return AgentOutcome(
            message="I will switch the next device off.",
            request_class="live-read", choices=[],
            evidence=[{
                "tool": "hub_manage_devices", "effect": "routine_write",
                "mutates": True,
            }],
        )

    result = await coordinator.run(operation)
    assert result.message == "I will switch the next device off."
