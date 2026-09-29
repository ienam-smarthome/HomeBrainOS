from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_host_plan import (  # noqa: E402
    collect_broad_performance_outcome,
    is_broad_performance_request,
    wants_scheduler_evidence,
)
from performance_log_observation_guard import (  # noqa: E402
    guard_performance_log_observations,
)
from request_metrics import RequestMetrics  # noqa: E402
from synthesis_validator import consume_performance_repair_issues  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


class _FakeMetrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount


class _FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, str]] = []

    async def execute(
        self,
        gateway: str,
        arguments: dict,
        *,
        supports_live_claim: bool,
        evidence_kind: str,
    ) -> SimpleNamespace:
        assert supports_live_claim is True
        self.calls.append((gateway, dict(arguments), evidence_kind))
        return SimpleNamespace(success=True)


class _FakeDirectOutcomes:
    async def run(self, operation, *, request_class: str):
        message = await operation()
        return SimpleNamespace(
            message=message,
            request_class=request_class,
            evidence=[],
            choices=[],
        )


class _FakeObservation:
    async def run(self, operation):
        return await operation()


class _FakeAgent:
    def __init__(self) -> None:
        self.request_metrics = _FakeMetrics()
        self.executor = _FakeExecutor()
        self.direct_outcomes = _FakeDirectOutcomes()
        self.request_observation = _FakeObservation()


def _log_evidence() -> list[dict]:
    return [
        {
            "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "success": True,
            "details": {
                "logCount": 1,
                "logs": [
                    {
                        "date": "2026-09-29 23:55:20.661",
                        "level": "WARN",
                        "message": (
                            'app|4151|MCP Rule Server|[MCP1] {"entry":{'
                            '"component":"hub-admin","level":"warn",'
                            '"message":"[hubrt] slow internal GET /logs/js took 3201ms"}}'
                        ),
                    }
                ],
            },
        }
    ]


def test_01678_broad_performance_classifier_is_narrow() -> None:
    assert is_broad_performance_request(
        "Analyse my Hubitat performance and recommend improvements."
    )
    assert not is_broad_performance_request("Check the hub health status")
    assert not is_broad_performance_request("Why is the hallway light slow?")
    assert wants_scheduler_evidence("Analyse scheduled jobs and recommend improvements")
    assert not wants_scheduler_evidence(
        "Analyse my Hubitat performance and recommend improvements."
    )


def test_01678_host_plan_skips_health_snapshot_discovery_and_jobs_by_default() -> None:
    agent = _FakeAgent()

    asyncio.run(
        collect_broad_performance_outcome(
            agent,
            "Analyse my Hubitat performance and recommend improvements.",
        )
    )

    sub_tools = [arguments.get("tool") for _gateway, arguments, _kind in agent.executor.calls]
    gateways = [gateway for gateway, _arguments, _kind in agent.executor.calls]
    assert sub_tools == [
        "hub_get_metrics",
        "hub_get_performance_stats",
        "hub_get_logs",
    ]
    assert "hub_get_jobs" not in sub_tools
    assert "homebrain_hub_info_snapshot" not in gateways
    assert "hub_search_tools" not in gateways
    assert agent.request_metrics.counters["broad_performance_host_plan"] == 1
    assert "broad_performance_host_plan_jobs" not in agent.request_metrics.counters


def test_01678_host_plan_adds_jobs_only_for_explicit_scheduler_objective() -> None:
    agent = _FakeAgent()

    asyncio.run(
        collect_broad_performance_outcome(
            agent,
            "Analyse Hubitat performance, especially scheduled jobs, and recommend improvements.",
        )
    )

    sub_tools = [arguments.get("tool") for _gateway, arguments, _kind in agent.executor.calls]
    assert sub_tools == [
        "hub_get_metrics",
        "hub_get_performance_stats",
        "hub_get_jobs",
        "hub_get_logs",
    ]
    assert agent.request_metrics.counters["broad_performance_host_plan_jobs"] == 1


def test_01678_request_metrics_accept_host_plan_counters() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("broad_performance_host_plan")
        metrics.increment("broad_performance_host_plan_jobs")
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["broad_performance_host_plan"] == 1
    assert snapshot["counters"]["broad_performance_host_plan_jobs"] == 1


def test_01678_repair_reason_comes_from_serialized_counter_not_contextvar() -> None:
    consume_performance_repair_issues()
    rows = present_request_metrics(
        {
            "outcome": "success",
            "counters": {
                "model_rounds": 1,
                "tool_calls": 3,
                "broad_performance_host_plan": 1,
                "performance_api_deterministic_repair": 1,
                "performance_api_repair_evidence_first": 1,
            },
            "timings_ms": {"performance_api_model": 5000},
        }
    )

    assert {"label": "Host-planned performance paths", "value": "1"} in rows
    assert {"label": "Agent model rounds", "value": "0"} in rows
    assert {"label": "Performance synthesis model rounds", "value": "1"} in rows
    assert {
        "label": "Performance repair reason",
        "value": "Evidence-first performance contract",
    } in rows


def test_01678_corrupted_warn_line_is_restored_from_current_log_evidence() -> None:
    draft = (
        '*   **Warnings:** One `WARN` entry from `app|4151|MCP Rule Server` '
        'The returned activity is worth reviewing; this turn does not establish material '
        'background overhead, log growth, or slower history lookups from that activity...".'
    )

    corrected, changed = guard_performance_log_observations(draft, _log_evidence())

    assert changed is True
    assert "app|4151|MCP Rule Server" in corrected
    assert "slow internal GET /logs/js took 3201ms" in corrected
    assert "recent log observation" in corrected
    assert "does not establish that it caused" in corrected
    assert "returned activity is worth reviewing" not in corrected.casefold()


def test_01678_clean_literal_warn_observation_is_not_rewritten() -> None:
    draft = (
        '*   **Warnings:** WARN from `app|4151|MCP Rule Server` reported '
        '`[hubrt] slow internal GET /logs/js took 3201ms`.'
    )

    corrected, changed = guard_performance_log_observations(draft, _log_evidence())

    assert changed is False
    assert corrected == draft
