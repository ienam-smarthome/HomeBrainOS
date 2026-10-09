from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import RequestCoordinator
from request_runtime import SensitiveUrlFilter, remember_verified_outcome, set_request_stage
from performance_api_finalizer import finalize_performance_api_outcome


def outcome():
    return SimpleNamespace(message="Unverified model recommendation", route="unified-mcp-agent",
                           metrics={"counters": {}, "timings_ms": {}},
                           evidence=[{"sub_tool": "hub_get_jobs", "success": True},
                                     {"sub_tool": "hub_get_logs", "success": False},
                                     {"sub_tool": "hub_get_performance_stats", "success": True}])


@pytest.mark.asyncio
async def test_coordinator_deadline_without_checkpoint_returns_504():
    coordinator = RequestCoordinator()
    cancelled = asyncio.Event()
    async def run():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    with pytest.raises(HTTPException) as exc:
        await coordinator.run("session", run(), deadline_seconds=0.12)
    assert exc.value.status_code == 504
    assert cancelled.is_set()
    await coordinator.close()


@pytest.mark.asyncio
async def test_deadline_keeps_verified_evidence_only_and_cancels():
    coordinator = RequestCoordinator()
    done = asyncio.Event()
    async def run():
        remember_verified_outcome(outcome())
        set_request_stage("Generating AI recommendations")
        try:
            await asyncio.Event().wait()
        finally:
            done.set()
    work = asyncio.create_task(coordinator.run("session", run(), request_id="123", deadline_seconds=0.15))
    await asyncio.sleep(0.04)
    assert coordinator.progress("session", "123")["stage"] == "Generating AI recommendations"
    assert coordinator.progress("session", "456")["stage"] == "Waiting for request"
    result = await work
    assert done.is_set()
    assert result.route == "investigation-timeout"
    assert "hub_get_jobs" in result.message
    assert "hub_get_logs" not in result.message
    assert "Unverified model recommendation" not in result.message
    await coordinator.close()


@pytest.mark.asyncio
async def test_synthesis_timeout_returns_partial_without_second_model_round(monkeypatch):
    import performance_api_finalizer as module
    class SlowCoordinator:
        def __init__(self, *args): pass
        async def answer(self, messages): await asyncio.Event().wait()
    monkeypatch.setattr(module, "FinalAnswerCoordinator", SlowCoordinator)
    result = await finalize_performance_api_outcome(
        SimpleNamespace(performance_synthesis_timeout_seconds=0.01),
        SimpleNamespace(), outcome(), "Review all devices and optimise the whole hub."
    )
    assert result.route == "investigation-timeout"
    assert result.metrics["counters"]["performance_api_synthesis_timeout"] == 1
    assert "Unverified model recommendation" not in result.message


def test_sensitive_url_filter():
    record = logging.LogRecord("httpx", 20, __file__, 1,
                               "HTTP Request POST http://hub/mcp?access_token=%s&x=1", ("placeholder",), None)
    assert SensitiveUrlFilter().filter(record)
    assert "placeholder" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()
    assert "x=1" in record.getMessage()


def test_webui_progress_includes_request_isolation_and_timer_cleanup():
    from webui import render_page
    markup = render_page("HomeBrain", "0.16.135")
    assert "api/request-progress" in markup
    assert "request_id:requestId" in markup
    assert "clearInterval(progressTimer)" in markup
    assert "activeRequest===controller" in markup


def _real_observed_outcome():
    from mcp_agent_orchestrator import AgentOutcome
    from observed_agent_outcome import build_observed_agent_outcome

    return build_observed_agent_outcome(
        AgentOutcome(
            message="Unverified model recommendation",
            request_class="live-read",
            evidence=[
                {"tool": "hub_manage_logs", "sub_tool": "hub_get_jobs",
                 "success": True, "mutates": False, "effect": "read"},
                {"tool": "hub_manage_logs", "sub_tool": "hub_get_logs",
                 "success": False, "mutates": False, "effect": "read"},
            ],
            choices=[],
        ),
        {"outcome": "success", "counters": {}, "timings_ms": {}},
    )


@pytest.mark.asyncio
async def test_deadline_accepts_real_slotted_observed_outcome_and_serializes_receipts():
    """Regression: v0.16.141 raised no-attribute 'route' instead of a partial answer."""
    from api_response_builder import build_agent_response

    coordinator = RequestCoordinator()
    cancelled = asyncio.Event()

    async def run():
        remember_verified_outcome(_real_observed_outcome())
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    result = await coordinator.run("live-scheduler", run(), deadline_seconds=0.08)
    assert cancelled.is_set()
    assert result.route == "investigation-timeout"
    assert result.request_class == "live-read"
    assert "hub_get_jobs" in result.message
    assert "hub_get_logs" not in result.message
    assert "Unverified model recommendation" not in result.message
    assert result.confirmation_required is False
    response = build_agent_response(
        result, model="gemma4:31b", elapsed_ms=140, version="0.16.142"
    )
    assert response["success"] is True
    assert response["route"] == "investigation-timeout"
    assert response["request_class"] == "live-read"
    assert response["evidence"][0]["sub_tool"] == "hub_get_jobs"
    assert all(receipt["mutates"] is False for receipt in response["evidence"])
    await coordinator.close()


@pytest.mark.asyncio
async def test_synthesis_timeout_accepts_real_observed_outcome_and_returns_safe_partial(
    monkeypatch,
):
    """Also guard the independent 30s synthesis timeout path."""
    import performance_api_finalizer as module
    from api_response_builder import build_agent_response

    class SlowCoordinator:
        def __init__(self, *args): pass
        async def answer(self, messages): await asyncio.Event().wait()

    monkeypatch.setattr(module, "FinalAnswerCoordinator", SlowCoordinator)
    outcome = _real_observed_outcome()
    result = await finalize_performance_api_outcome(
        SimpleNamespace(performance_synthesis_timeout_seconds=0.01),
        SimpleNamespace(),
        outcome,
        "Review all devices and optimise the whole hub.",
    )
    assert result.route == "investigation-timeout"
    assert "Unverified model recommendation" not in result.message
    assert "hub_get_jobs" in result.message
    response = build_agent_response(
        result, model="gemma4:31b", elapsed_ms=200, version="0.16.142"
    )
    assert response["route"] == "investigation-timeout"


def test_observed_outcome_preserves_explicit_route_and_default_route():
    from mcp_agent_orchestrator import AgentOutcome
    from observed_agent_outcome import build_observed_agent_outcome

    observed = _real_observed_outcome()
    assert observed.route == "unified-mcp-agent"

    base = AgentOutcome(
        message="OK", request_class="live-read", evidence=[], choices=[],
        route="special-read-only-route",
    )
    decorated = build_observed_agent_outcome(
        base, {"outcome": "success", "counters": {}, "timings_ms": {}}
    )
    assert decorated.route == base.route
