"""Host-owned evidence acquisition for broad performance recommendations.

The model still authors the final analysis. This module only chooses the bounded,
authoritative source set before synthesis so broad performance requests do not pay
for unrelated hub-health snapshots, tool discovery, or speculative evidence paths.

0.16.81 adds one bounded adaptive stage after the accepted baseline reads. Numeric
performance outliers are retrieval triggers only -- never health classifications.
When a strong device/app outlier is present, HomeBrain may read a longer log window
scoped server-side to at most one device and one app. No provider planning round is
added and the final evidence-first synthesis remains the only model round.

0.16.86 keeps that bounded architecture but removes a hard 20% busy-share cliff
from retrieval eligibility. A sustained near-threshold busy leader may now compete
for the single adaptive slot, while the higher 20% threshold remains a priority
bonus rather than an all-or-nothing admission rule.

0.16.87 preserves the exact triggering performance row with each adaptive receipt.
That provenance remains available even when the scoped log query returns zero rows,
so target identity never has to be inferred from later model prose.
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

# Retrieval-policy thresholds only. They decide whether a bounded diagnostic read
# is worth its cost; they are not user-facing health/severity thresholds. Keep the
# admission threshold below the priority threshold so small snapshot variation
# around 20% cannot discard a sustained busy-share leader entirely.
_ADAPTIVE_BUSY_READ_PCT = 15.0
_ADAPTIVE_BUSY_PRIORITY_PCT = 20.0
_ADAPTIVE_TOTAL_PCT = 15.0
_ADAPTIVE_AVERAGE_MS = 2500.0
_ADAPTIVE_SINCE = "6h"
_ADAPTIVE_LIMIT = 120


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


def _number(value: Any) -> float:
    if isinstance(value, bool) or value in (None, ""):
        return 0.0
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _adaptive_score(row: dict[str, Any]) -> tuple[bool, float]:
    """Return retrieval eligibility/score without declaring the row unhealthy."""

    busy = _number(row.get("pctBusy"))
    total = _number(row.get("pctTotal"))
    average = _number(row.get("averageMs"))
    strong = (
        busy >= _ADAPTIVE_BUSY_READ_PCT
        or total >= _ADAPTIVE_TOTAL_PCT
        or average >= _ADAPTIVE_AVERAGE_MS
    )
    if not strong:
        return False, 0.0

    score = busy * 4.0 + total * 3.0 + min(average / 1000.0, 30.0)
    if busy >= _ADAPTIVE_BUSY_PRIORITY_PCT:
        score += 100.0
    if total >= _ADAPTIVE_TOTAL_PCT:
        score += 80.0
    if average >= _ADAPTIVE_AVERAGE_MS:
        score += 60.0
    return True, score


def _strongest_target(rows: Any, *, kind: str) -> dict[str, str] | None:
    if not isinstance(rows, list):
        return None
    winner: dict[str, Any] | None = None
    winner_score = -1.0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        identifier = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not identifier or not name:
            continue
        eligible, score = _adaptive_score(raw)
        if eligible and score > winner_score:
            winner = raw
            winner_score = score
    if winner is None:
        return None
    return {
        "kind": kind,
        "id": str(winner.get("id") or "").strip(),
        "name": str(winner.get("name") or "").strip(),
    }


def select_adaptive_log_targets(performance_data: Any) -> list[dict[str, str]]:
    """Select at most one strong device and one strong app for scoped log reads."""

    if not isinstance(performance_data, dict):
        return []
    targets: list[dict[str, str]] = []
    device = _strongest_target(performance_data.get("deviceStats"), kind="device")
    app = _strongest_target(performance_data.get("appStats"), kind="app")
    if device is not None:
        targets.append(device)
    if app is not None:
        targets.append(app)
    return targets


def _performance_row_for_target(performance_data: Any, target: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(performance_data, dict):
        return None
    key = "deviceStats" if target.get("kind") == "device" else "appStats"
    rows = performance_data.get(key)
    if not isinstance(rows, list):
        return None
    target_id = str(target.get("id") or "").strip()
    target_name = str(target.get("name") or "").strip()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("id") or "").strip() != target_id:
            continue
        if str(raw.get("name") or "").strip() != target_name:
            continue
        return raw
    return None


def _adaptive_target_details(performance_data: Any, target: dict[str, str]) -> dict[str, Any]:
    row = _performance_row_for_target(performance_data, target)
    selected_row: dict[str, Any] = {}
    if isinstance(row, dict):
        for key in ("id", "name", "pctBusy", "pctTotal", "averageMs", "count", "stateSize", "totalMs"):
            if key in row:
                selected_row[key] = row.get(key)
    return {
        "kind": str(target.get("kind") or ""),
        "id": str(target.get("id") or ""),
        "name": str(target.get("name") or ""),
        "selectionSource": "hub_get_performance_stats",
        "selectedFromExactRow": row is not None,
        "performanceRow": selected_row,
    }


def _record_adaptive_execution(
    agent: Any,
    arguments: dict[str, Any],
    execution: Any,
    target: dict[str, str],
    performance_data: Any,
) -> None:
    executor = getattr(agent, "executor", None)
    recorder = getattr(executor, "evidence", None)
    record = getattr(recorder, "record", None)
    if not callable(record):
        return

    details: dict[str, Any] = {}
    result = getattr(execution, "result", None)
    details_fn = getattr(executor, "result_details", None)
    if result is not None and callable(details_fn):
        result_details = details_fn(result)
        if isinstance(result_details, dict):
            details.update(result_details)
    details["adaptiveTarget"] = _adaptive_target_details(performance_data, target)

    summary = f"adaptive diagnostic logs for {target.get('kind')} {target.get('id')} ({target.get('name')})"
    summary_fn = getattr(executor, "result_summary", None)
    if result is not None and callable(summary_fn):
        summary = summary_fn(result)

    record(
        "hub_manage_logs",
        arguments,
        success=bool(getattr(execution, "success", False)),
        elapsed_ms=int(getattr(execution, "elapsed_ms", 0) or 0),
        summary=summary,
        supports_live_claim=True,
        evidence_kind="host_planned_performance_diagnostic",
        mutates=False,
        effect=getattr(execution, "effect", "read"),
        details=details,
    )


async def collect_broad_performance_outcome(agent: Any, user_prompt: str) -> Any:
    """Collect baseline evidence plus bounded strong-outlier diagnostics."""

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
        source_specs.append(("hub_manage_logs", {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}}))

        failed: list[str] = []
        performance_data: Any = None
        for gateway, arguments in source_specs:
            execution = await agent.executor.execute(
                gateway,
                arguments,
                supports_live_claim=True,
                evidence_kind="host_planned_performance_source",
            )
            if not execution.success:
                failed.append(str(arguments.get("tool") or gateway))
                continue
            result = getattr(execution, "result", None)
            if arguments.get("tool") == "hub_get_performance_stats" and result is not None:
                performance_data = getattr(result, "data", None)

        targets = select_adaptive_log_targets(performance_data)
        if targets:
            agent.request_metrics.increment("performance_adaptive_expansion")
        for target in targets:
            scope_key = "deviceId" if target["kind"] == "device" else "appId"
            metric_key = "performance_adaptive_device_target" if target["kind"] == "device" else "performance_adaptive_app_target"
            agent.request_metrics.increment(metric_key)
            agent.request_metrics.increment("performance_adaptive_reads")
            arguments = {
                "tool": "hub_get_logs",
                "args": {scope_key: target["id"], "since": _ADAPTIVE_SINCE, "limit": _ADAPTIVE_LIMIT},
            }
            execution = await agent.executor.execute(
                "hub_manage_logs",
                arguments,
                supports_live_claim=True,
                evidence_kind="host_planned_performance_diagnostic",
                record_evidence=False,
            )
            _record_adaptive_execution(agent, arguments, execution, target, performance_data)
            if not execution.success:
                agent.request_metrics.increment("performance_adaptive_read_failures")

        if failed:
            return "Host-planned performance evidence collection completed with failed sources: " + ", ".join(failed) + "."
        return "Host-planned performance evidence collection completed."

    async def direct_outcome() -> Any:
        return await agent.direct_outcomes.run(collect, request_class="live-read")

    return await agent.request_observation.run(direct_outcome)


__all__ = [
    "collect_broad_performance_outcome",
    "is_broad_performance_request",
    "select_adaptive_log_targets",
    "wants_scheduler_evidence",
]
