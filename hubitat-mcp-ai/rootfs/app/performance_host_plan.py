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
bonus rather than an all-or-nothing admission rule. Adaptive receipts also retain
the exact performance-stat row that selected each scoped target so identity and
selection rationale are auditable without re-resolving a name.
"""

from __future__ import annotations

from typing import Any
import asyncio
import time

from performance_job_analysis import summarize_job_workload
from performance_inventory_check import reconcile_scheduler_candidates
from scheduler_secondary_inventory import probe_secondary_device_inventory
from device_read_contract import live_context_is_complete
from request_runtime import set_request_stage


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

_ADAPTIVE_BUSY_READ_PCT = 15.0
_ADAPTIVE_BUSY_PRIORITY_PCT = 20.0
_ADAPTIVE_TOTAL_PCT = 15.0
_ADAPTIVE_AVERAGE_MS = 2500.0
_ADAPTIVE_SINCE = "6h"
_ADAPTIVE_LIMIT = 120
_SCHEDULER_INVENTORY_TIMEOUT_SECONDS = 6.0
_ADAPTIVE_ROW_FIELDS = (
    "id", "name", "pctBusy", "pctTotal", "averageMs", "count", "stateSize", "totalMs"
)


def is_whole_hub_optimization_request(text: str) -> bool:
    """Prefer a performance review over a health-only audit for optimisation.

    Requests to simply run System Check keep their existing deterministic path.
    Whole-hub review must convey both an efficiency objective and broad scope,
    so a targeted question about one rule or driver is not hijacked.
    """
    folded = " ".join(str(text or "").casefold().split())
    goal = any(term in folded for term in (
        "optimise", "optimize", "optimisation", "optimization",
        "more efficient", "hub efficiency", "reduce hub overhead",
        "reduce unnecessary work", "improve hub performance",
    ))
    scope = any(term in folded for term in (
        "all devices", "all apps", "all rules", "all automations",
        "whole hub", "entire hub", "hub performance",
        "make the hub", "hub more efficient", "review all",
        "review my hub",
    ))
    return goal and scope


def is_scheduler_optimization_request(text: str) -> bool:
    """Route explicit job ownership/efficiency analyses to the host evidence plan.

    Counting jobs alone remains a standard read and is not hijacked.
    """
    folded = " ".join(str(text or "").casefold().split())
    scheduled = any(term in folded for term in (
        "scheduled job", "scheduled task", "scheduler jobs",
        "sessiontick", "autopoll", "scheduled work",
    ))
    analysis = any(term in folded for term in (
        "analys", "analyz", "group", "owner", "handler",
        "optimis", "optimiz", "efficien", "unnecessary work",
        "reduce workload",
    ))
    return scheduled and analysis


def is_broad_performance_request(text: str) -> bool:
    folded = " ".join(str(text or "").casefold().split())
    return is_whole_hub_optimization_request(text) or is_scheduler_optimization_request(text) or (
        any(token in folded for token in _PERFORMANCE_TERMS)
        and any(token in folded for token in _RECOMMENDATION_TERMS)
    )


def wants_scheduler_evidence(text: str) -> bool:
    folded = " ".join(str(text or "").casefold().split())
    return is_whole_hub_optimization_request(text) or any(
        token in folded for token in _SCHEDULER_TERMS
    )


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


def _compact_performance_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in _ADAPTIVE_ROW_FIELDS if field in row}


def _strongest_target(rows: Any, *, kind: str) -> dict[str, Any] | None:
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
        "performanceRow": _compact_performance_row(winner),
        "selectionScore": round(winner_score, 3),
    }


def _select_adaptive_log_target_records(performance_data: Any) -> list[dict[str, Any]]:
    if not isinstance(performance_data, dict):
        return []
    targets: list[dict[str, Any]] = []
    device = _strongest_target(performance_data.get("deviceStats"), kind="device")
    app = _strongest_target(performance_data.get("appStats"), kind="app")
    if device is not None:
        targets.append(device)
    if app is not None:
        targets.append(app)
    return targets


def select_adaptive_log_targets(performance_data: Any) -> list[dict[str, str]]:
    """Public target selection keeps its historical compact return shape."""
    return [
        {"kind": str(row["kind"]), "id": str(row["id"]), "name": str(row["name"])}
        for row in _select_adaptive_log_target_records(performance_data)
    ]


def _adaptive_target_details(target: dict[str, Any]) -> dict[str, Any]:
    row = target.get("performanceRow")
    row = row if isinstance(row, dict) else {}
    return {
        "adaptiveTarget": {
            "kind": str(target.get("kind") or ""),
            "id": str(target.get("id") or ""),
            "name": str(target.get("name") or ""),
            "selectionSource": "hub_get_performance_stats",
            "selectedFromExactRow": bool(
                row
                and str(row.get("id") or "") == str(target.get("id") or "")
                and str(row.get("name") or "") == str(target.get("name") or "")
            ),
            "selectionScore": target.get("selectionScore"),
            "performanceRow": row,
        }
    }


async def collect_broad_performance_outcome(agent: Any, user_prompt: str) -> Any:
    identity_report: dict[str, Any] | None = None

    async def collect() -> str:
        nonlocal identity_report
        agent.request_metrics.increment("broad_performance_host_plan")
        source_specs: list[tuple[str, dict[str, Any]]] = [
            ("hub_read_diagnostics", {"tool": "hub_get_metrics"}),
            (
                "hub_manage_logs",
                {"tool": "hub_get_performance_stats", "args": {"limit": 20, "sortBy": "pct", "type": "both"}},
            ),
        ]
        if wants_scheduler_evidence(user_prompt):
            agent.request_metrics.increment("broad_performance_host_plan_jobs")
            source_specs.append(("hub_manage_logs", {"tool": "hub_get_jobs"}))
        source_specs.append(("hub_manage_logs", {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}}))

        failed: list[str] = []
        performance_data: Any = None
        job_data: Any = None
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
            if arguments.get("tool") == "hub_get_jobs" and result is not None:
                job_data = getattr(result, "data", None)

        # At most two bounded read-only inventory stages: app instances and a
        # compact device context resource with a first-page identity fallback.
        # Each stage has a six-second total deadline; no model round is added.
        if job_data is not None:
            job_digest = summarize_job_workload(job_data)
            candidate_ids = job_digest.get("candidateIdsByType") or {}
            if candidate_ids.get("app") or candidate_ids.get("device"):
                set_request_stage("Cross-checking scheduled-job entity IDs")
                agent.request_metrics.increment("scheduler_inventory_crosscheck")
                checks = (
                    ("app", "hub_read_apps_code",
                     {"tool": "hub_list_apps", "args": {"scope": "instances"}}),
                    ("device", "hub_read_devices",
                     {"tool": "hub_list_devices", "args": {
                         "detailed": False, "fields": ["id", "name", "label", "room"],
                         "limit": 125, "offset": 0
                     }}),
                )

                async def read_inventory(
                    kind: str, gateway: str, arguments: dict[str, Any],
                ) -> tuple[str, Any]:
                    started = time.monotonic()
                    data = None
                    partial_context = None
                    success = False
                    summary = "Read timed out or failed"
                    receipt_arguments = arguments

                    # The MCP client already offers a compact bulk identity
                    # resource. Prefer it over requesting hundreds of devices
                    # through the slower list endpoint. Retain only identity
                    # fields, never full live state or secrets.
                    reader = getattr(getattr(agent.executor, "mcp", None),
                                     "get_live_context", None)
                    if kind == "device" and callable(reader):
                        try:
                            context = await asyncio.wait_for(
                                reader(),
                                timeout=_SCHEDULER_INVENTORY_TIMEOUT_SECONDS,
                            )
                            if isinstance(context, dict) and isinstance(
                                context.get("devices"), list
                            ):
                                identities = [
                                    {field: row[field] for field in (
                                        "id", "deviceId", "label", "name"
                                    ) if field in row}
                                    for row in context["devices"]
                                    if isinstance(row, dict)
                                ]
                                projected = {
                                    "devices": identities,
                                    "totalDevices": context.get("totalDevices"),
                                    "idsComplete": context.get("idsComplete"),
                                    "partial": not live_context_is_complete(context),
                                    "identitySource": "hubitat://context",
                                }
                                if live_context_is_complete(context):
                                    data = projected
                                    success = True
                                    receipt_arguments = {
                                        "resource": "hubitat://context",
                                        "projection": "device identities only",
                                    }
                                    summary = "Compact device identity resource read succeeded"
                                else:
                                    partial_context = projected
                        except asyncio.TimeoutError:
                            # The same overall six-second budget still applies.
                            pass
                        except Exception:
                            # Resource unavailable: the bounded list fallback
                            # can still work on older MCP server versions.
                            pass

                    if not success:
                        try:
                            remaining = (
                                _SCHEDULER_INVENTORY_TIMEOUT_SECONDS
                                - (time.monotonic() - started)
                            )
                            if remaining <= 0:
                                raise asyncio.TimeoutError()
                            execution = await asyncio.wait_for(
                                agent.executor.execute(
                                    gateway, arguments,
                                    supports_live_claim=True,
                                    evidence_kind="host_planned_scheduler_inventory",
                                    record_evidence=False,
                                ),
                                timeout=remaining,
                            )
                            success = bool(execution.success)
                            if success and execution.result is not None:
                                data = getattr(execution.result, "data", None)
                            summary = ("Identity inventory read succeeded" if success
                                       else "Identity inventory read failed")
                        except asyncio.TimeoutError:
                            summary = "Identity inventory exceeded six-second total budget"
                            agent.request_metrics.increment("scheduler_inventory_timeout")
                        except Exception:
                            summary = "Identity inventory read unavailable"
                            agent.request_metrics.increment("scheduler_inventory_read_failure")

                    if data is None and partial_context is not None:
                        # A partial context can prove present IDs, but cannot
                        # prove an absent ID is removed. Do not turn it into a
                        # complete result, even if the list fallback times out.
                        data = partial_context
                        success = True
                        receipt_arguments = {
                            "resource": "hubitat://context",
                            "projection": "partial device identities only",
                        }
                        summary += "; preserved incomplete context identities"
                    recorder = getattr(agent.executor, "evidence", None)
                    if callable(getattr(recorder, "record", None)):
                        recorder.record(
                            gateway, receipt_arguments, success=success,
                            elapsed_ms=round((time.monotonic() - started) * 1000),
                            summary=summary, supports_live_claim=success,
                            evidence_kind="host_planned_scheduler_inventory",
                            mutates=False, effect="read",
                        )
                    return kind, data

                results = await asyncio.gather(
                    *(read_inventory(*check) for check in checks)
                )
                inventories = dict(results)
                identity_report = reconcile_scheduler_candidates(
                    job_digest,
                    apps=inventories.get("app"),
                    devices=inventories.get("device"),
                    performance=performance_data,
                )

        targets = _select_adaptive_log_target_records(performance_data)
        if targets:
            agent.request_metrics.increment("performance_adaptive_expansion")
        for target in targets:
            scope_key = "deviceId" if target["kind"] == "device" else "appId"
            metric_key = "performance_adaptive_device_target" if target["kind"] == "device" else "performance_adaptive_app_target"
            agent.request_metrics.increment(metric_key)
            agent.request_metrics.increment("performance_adaptive_reads")
            adaptive_arguments = {
                "tool": "hub_get_logs",
                "args": {scope_key: target["id"], "since": _ADAPTIVE_SINCE, "limit": _ADAPTIVE_LIMIT},
            }
            execution = await agent.executor.execute(
                "hub_manage_logs",
                adaptive_arguments,
                supports_live_claim=True,
                evidence_kind="host_planned_performance_diagnostic",
                record_evidence=False,
            )
            result = getattr(execution, "result", None)
            details_builder = getattr(agent.executor, "result_details", None)
            details = details_builder(result) if result is not None and callable(details_builder) else None
            enriched_details = dict(details or {})
            enriched_details.update(_adaptive_target_details(target))
            summary_builder = getattr(agent.executor, "result_summary", None)
            summary = (
                summary_builder(result)
                if result is not None and callable(summary_builder)
                else f"adaptive target {target['kind']}:{target['id']} {'read succeeded' if execution.success else 'read failed'}"
            )
            recorder = getattr(agent.executor, "evidence", None)
            if recorder is not None and callable(getattr(recorder, "record", None)):
                recorder.record(
                    "hub_manage_logs",
                    adaptive_arguments,
                    success=execution.success,
                    elapsed_ms=int(getattr(execution, "elapsed_ms", 0) or 0),
                    summary=summary,
                    supports_live_claim=True,
                    evidence_kind="host_planned_performance_diagnostic",
                    mutates=False,
                    effect=getattr(execution, "effect", "read"),
                    details=enriched_details,
                )
            if not execution.success:
                agent.request_metrics.increment("performance_adaptive_read_failures")

        # Run scheduler candidate probes only AFTER all diagnostic log reads.
        # A failed hub_get_device lookup can itself emit a Rule Server
        # "Device not found" log row. Running the probe earlier allowed the
        # adaptive app-log read to ingest HomeBrain's own diagnostic side
        # effect and misdescribe it as a pre-existing error loop.
        #
        # This ordering is a provenance boundary: baseline/adaptive logs must
        # describe hub activity that existed before the targeted probes.
        if identity_report is not None and job_data is not None:
            device_inventory = inventories.get("device") if "inventories" in locals() else None
            if (isinstance(device_inventory, dict)
                    and device_inventory.get("identitySource") == "hubitat://context"
                    and (identity_report.get("device") or {}).get("inventory", {}).get("complete")):
                set_request_stage("Checking context-absent device IDs against secondary source")
                secondary = await probe_secondary_device_inventory(
                    agent.executor,
                    (job_digest.get("candidateIdsByType") or {}).get("device") or [],
                    device_inventory,
                )
                if secondary is not None:
                    secondary["ranAfterDiagnosticLogReads"] = True
                    secondary["probeMayEmitExpectedNotFoundLogs"] = True
                    identity_report["secondaryDeviceSource"] = secondary

        if failed:
            return "Host-planned performance evidence collection completed with failed sources: " + ", ".join(failed) + "."
        return "Host-planned performance evidence collection completed."

    async def direct_outcome() -> Any:
        return await agent.direct_outcomes.run(collect, request_class="live-read")

    outcome = await agent.request_observation.run(direct_outcome)
    if identity_report is not None and isinstance(getattr(outcome, "metrics", None), dict):
        # Bounded digest only: no raw home inventory or auth information.
        outcome.metrics["scheduler_inventory_crosscheck"] = identity_report
    return outcome


__all__ = [
    "collect_broad_performance_outcome",
    "is_broad_performance_request",
    "is_whole_hub_optimization_request",
    "is_scheduler_optimization_request",
    "select_adaptive_log_targets",
    "wants_scheduler_evidence",
]
