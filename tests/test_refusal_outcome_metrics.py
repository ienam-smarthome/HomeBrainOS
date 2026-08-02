from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_agent_orchestrator import AgentOutcome  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent as BaseUnifiedMCPAgent  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


class FakeMCP:
    pass


class FakeAI:
    async def aclose(self) -> None:
        return None


def _outcome(message: str) -> AgentOutcome:
    return AgentOutcome(
        message=message,
        request_class="live-read",
        evidence=[],
        choices=[],
    )


@pytest.mark.asyncio
async def test_grounding_refusal_finishes_with_refused_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_base_result(agent, *_args, **_kwargs) -> AgentOutcome:
        agent.request_metrics.increment("grounding_refusals")
        return _outcome("I cannot verify that live claim.")

    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base_result,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI())

    outcome = await agent.process_user_request_result("private live request")

    assert outcome.metrics["outcome"] == "refused"
    assert outcome.metrics["counters"]["grounding_refusals"] == 1
    assert "private live request" not in repr(outcome.metrics)


@pytest.mark.asyncio
async def test_ambiguous_device_resolution_finishes_with_refused_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_base_result(agent, *_args, **_kwargs) -> AgentOutcome:
        agent.request_metrics.increment("device_resolution_ambiguous")
        return _outcome("The device could not be resolved uniquely.")

    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base_result,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI())

    outcome = await agent.process_user_request_result("private ambiguous device")

    assert outcome.metrics["outcome"] == "refused"
    assert outcome.metrics["counters"]["device_resolution_ambiguous"] == 1
    assert "private ambiguous device" not in repr(outcome.metrics)


@pytest.mark.asyncio
async def test_normal_return_still_finishes_with_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_base_result(*_args, **_kwargs) -> AgentOutcome:
        return _outcome("Grounded answer.")

    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base_result,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=FakeAI())

    outcome = await agent.process_user_request_result("ordinary request")

    assert outcome.metrics["outcome"] == "success"
    assert "grounding_refusals" not in outcome.metrics["counters"]
    assert "device_resolution_ambiguous" not in outcome.metrics["counters"]


def test_completed_outcome_ignores_events_outside_request_context() -> None:
    metrics = RequestMetrics()

    metrics.increment("grounding_refusals")
    metrics.increment("device_resolution_ambiguous")

    assert metrics.completed_outcome() == "success"
