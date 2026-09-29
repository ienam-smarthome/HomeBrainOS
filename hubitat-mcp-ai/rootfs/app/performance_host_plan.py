"""Host-owned evidence acquisition for broad performance recommendations.

The model still authors the final analysis. This module only chooses the bounded,
authoritative source set before synthesis so broad performance requests do not pay
for unrelated hub-health snapshots, tool discovery, or speculative evidence paths.
"""

from __future__ import annotations

from typing import Any


_PERFORMANCE_TERMS = (
    "performance",
    "slow hub",
    "hub slow",
    "hub load",
    "resource consumer",
    "resource consumers",
    "optimisation",
    "optimization",
)
_RECOMMENDATION_TERMS = (
    "recommend",
    "improve",
    "improvement",
    "optimise",
    "optimize",
    "what else can be improved",
)
_SCHEDULER_TERMS = (
    "schedule",
    "scheduled",
    "scheduler",
    "job",
    "jobs",
    "sessiontick",
    "autopoll",
    "cadence",
    "polling",
)


def is_broad_performance_request(text: str) -> bool:
    """Return True only for broad performance analysis that asks for improvements."""

    folded = " ".join(str(text or "").casefold().split())
    return any(token in folded for token in _PERFORMANCE_TERMS) and any(
        token in folded for token in _RECOMMENDATION_TERMS
    )


def wants_scheduler_evidence(text: str) -> bool:
    """Only add the scheduler source when the user's objective actually mentions it."""

    folded = " ".join(str(text or "").casefold().split())
    return any(token in folded for token in _SCHEDULER_TERMS)


async def collect_broad_performance_outcome(agent: Any, user_prompt: str) -> Any:
    """Collect the bounded performance source set without a provider planning round.

    The returned observed outcome deliberately contains only a placeholder message.
    `performance_api_finalizer` consumes the normalized ToolExecutor packet and
    performs the one evidence-first model synthesis that writes the user answer.
    """

    async def collect() -> str:
        agent.request_metrics.increment("broad_performance_host_plan")
        source_specs: list[tuple[str, dict[str, Any]]] = [
            ("hub_read_diagnostics", {"tool": "hub_get_metrics"}),
            (
                "hub_manage_logs",
                {
                    "tool": "hub_get_performance_stats",
                    "args": {"limit": 20, "sortBy": "pct", "type": "both"},
                },
            ),
        ]
        if wants_scheduler_evidence(user_prompt):
            agent.request_metrics.increment("broad_performance_host_plan_jobs")
            source_specs.append(("hub_manage_logs", {"tool": "hub_get_jobs"}))
        source_specs.append(
            (
                "hub_manage_logs",
                {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
            )
        )

        failed: list[str] = []
        for gateway, arguments in source_specs:
            execution = await agent.executor.execute(
                gateway,
                arguments,
                supports_live_claim=True,
                evidence_kind="host_planned_performance_source",
            )
            if not execution.success:
                failed.append(str(arguments.get("tool") or gateway))

        if failed:
            return (
                "Host-planned performance evidence collection completed with failed "
                "sources: " + ", ".join(failed) + "."
            )
        return "Host-planned performance evidence collection completed."

    async def direct_outcome() -> Any:
        return await agent.direct_outcomes.run(collect, request_class="live-read")

    return await agent.request_observation.run(direct_outcome)


__all__ = [
    "collect_broad_performance_outcome",
    "is_broad_performance_request",
    "wants_scheduler_evidence",
]
