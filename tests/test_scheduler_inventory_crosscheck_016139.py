from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from performance_inventory_check import (
    reconcile_scheduler_candidates, render_scheduler_inventory_crosscheck,
)
from performance_job_analysis import summarize_job_workload
from performance_api_finalizer import _compact_job_digest


def sample_jobs():
    return summarize_job_workload({
        "scheduledJobs": {"count": 5, "jobs": [
            {"id": "app1418Once.timeHandler", "handler": "timeHandler"},
            {"id": "app1418Once.midnightHandler", "handler": "midnightHandler"},
            {"id": "dev1089Recur.poll1", "handler": "poll1"},
            {"id": "dev7334Once.healthCheck", "handler": "healthCheck"},
            {"name": "Other event", "handler": "sendEventReminder"},
        ]}
    })


def test_match_entity_existence_not_job_ownership():
    digest = sample_jobs()
    report = reconcile_scheduler_candidates(
        digest,
        apps={"apps": [{"id": "1418", "label": "Calendar app"}],
              "totalOnHub": 1},
        devices={"devices": [{"id": 1089, "label": "Hub Info"},
                              {"id": "7334", "label": "FP2 Livingroom"}],
                 "total": 2},
        performance={"deviceStats": [
            {"id": 1089, "pctTotal": "0.294", "name": "Hub Info"}],
                     "appStats": [{"id": "1418", "pctTotal": "0.198"}]},
    )
    assert report["explicitOwnerJobs"] == 0
    assert report["keyCandidateJobs"] == 4
    assert report["app"]["candidateIds"] == 1
    assert report["device"]["candidateIds"] == 2
    assert report["device"]["presentInReturnedInventory"] == 2
    assert report["device"]["notListedInReturnedInventory"] == 0
    assert report["device"]["inventory"]["complete"] is True
    assert report["app"]["topMeasuredOverlaps"][0]["pctTotal"] == 0.198
    message = render_scheduler_inventory_crosscheck(report)
    assert "confirms that the entity was listed" in message
    assert "| device | 2 | 2 | 0 |" in message
    assert "0.294%" in message
    assert "not a quantified saving" in message


def test_incomplete_inventory_never_promotes_unlisted_candidate_to_deleted():
    report = reconcile_scheduler_candidates(
        sample_jobs(),
        apps={"apps": [{"id": 1418}], "totalOnHub": 155, "partial": True},
        devices={"devices": [{"id": 1089}], "total": 370},
    )
    assert report["device"]["presentInReturnedInventory"] == 1
    assert report["device"]["notListedInReturnedInventory"] == 1
    assert report["device"]["inventory"]["complete"] is False
    assert report["app"]["inventory"]["complete"] is False
    assert "partial/unverified completeness" in render_scheduler_inventory_crosscheck(report)
    assert "Do not label such IDs deleted" in render_scheduler_inventory_crosscheck(report)


def test_unavailable_inventory_does_not_fabricate_missing_entities():
    report = reconcile_scheduler_candidates(sample_jobs(), apps=None, devices=None)
    assert report["app"]["inventory"]["status"] == "unavailable"
    assert report["device"]["inventory"]["status"] == "unavailable"
    assert report["app"]["notListedInReturnedInventory"] == 0
    assert report["app"]["notCheckedDueToUnavailableInventory"] == 1
    assert report["device"]["notCheckedDueToUnavailableInventory"] == 2
    assert "| device | 2 | 0 | 0 | 2 | read unavailable |" in render_scheduler_inventory_crosscheck(report)


def test_wrong_entity_type_and_duplicate_id_are_not_accepted():
    report = reconcile_scheduler_candidates(
        sample_jobs(),
        apps={"apps": [{"id": "1089"}], "count": 1},
        devices={"devices": [{"id": 1089}, {"id": "1089"}], "count": 2},
    )
    assert report["app"]["presentInReturnedInventory"] == 0
    assert report["device"]["presentInReturnedInventory"] == 0
    assert report["device"]["inventory"]["ambiguousIds"] == 1


def test_false_display_name_not_an_authoritative_inventory_id():
    report = reconcile_scheduler_candidates(
        sample_jobs(),
        apps={"apps": [{"name": "App 1418"}], "totalOnHub": 1},
        devices={"devices": [{"name": "dev1089Recur.poll1"}], "total": 1},
    )
    assert report["app"]["presentInReturnedInventory"] == 0
    assert report["device"]["presentInReturnedInventory"] == 0


def test_compact_packet_does_not_contain_full_id_sets():
    d = sample_jobs()
    assert "candidateIdsByType" in d
    compact = _compact_job_digest(d)
    assert "candidateIdsByType" not in compact


class _Metrics:
    def __init__(self): self.counters = {}
    def increment(self, key, amount=1):
        self.counters[key] = self.counters.get(key, 0) + amount


class _Evidence:
    def __init__(self): self.rows = []
    def record(self, gateway, arguments, **kwargs):
        self.rows.append((gateway, arguments, kwargs))


class _Executor:
    def __init__(self, *, slow_device=False):
        self.calls = []
        self.evidence = _Evidence()
        self.slow_device = slow_device

    async def execute(self, gateway, arguments, **kwargs):
        subtool = arguments["tool"]
        self.calls.append((subtool, arguments, kwargs))
        if subtool == "hub_list_devices" and self.slow_device:
            await asyncio.sleep(10)
        results = {
            "hub_get_metrics": {"current": {"freeMemory": 850}},
            "hub_get_performance_stats": {
                "appStats": [{"id": 1418, "name": "Calendar", "pctBusy": 1,
                              "pctTotal": 0.15, "averageMs": 2}],
                "deviceStats": [{"id": 1089, "name": "Hub Info", "pctBusy": 2,
                                 "pctTotal": 0.294, "averageMs": 100}],
            },
            "hub_get_jobs": {"scheduledJobs": {
                "count": 2, "jobs": [
                    {"id": "app1418Once.timeHandler", "method": "timeHandler"},
                    {"id": "dev1089Recur.poll1", "method": "poll1"},
                ],
            }},
            "hub_get_logs": {"logs": []},
            "hub_list_apps": {"apps": [{"id": 1418, "label": "Calendar"}], "totalOnHub": 1},
            "hub_list_devices": {"devices": [{"id": 1089, "label": "Hub Info"}], "total": 1},
        }
        return SimpleNamespace(success=True, result=SimpleNamespace(data=results[subtool]),
                               elapsed_ms=3, effect="read")


class _SimpleRun:
    async def run(self, f, **kwargs): return await f()


class _DirectRun:
    async def run(self, f, **kwargs):
        message = await f()
        return SimpleNamespace(message=message, evidence=[], metrics={"counters": {}})


class _Agent:
    def __init__(self, *, slow_device=False):
        self.request_metrics = _Metrics()
        self.executor = _Executor(slow_device=slow_device)
        self.direct_outcomes = _DirectRun()
        self.request_observation = _SimpleRun()


def test_host_plan_inventory_only_for_real_job_candidates_and_publishes_digest():
    from performance_host_plan import collect_broad_performance_outcome
    agent = _Agent()
    outcome = asyncio.run(collect_broad_performance_outcome(
        agent, "Analyse scheduled jobs by owning app and handler for efficiency."
    ))
    calls = [r[0] for r in agent.executor.calls]
    assert calls.count("hub_list_apps") == 1
    assert calls.count("hub_list_devices") == 1
    assert len(calls) == 6
    identities = outcome.metrics["scheduler_inventory_crosscheck"]
    assert identities["app"]["presentInReturnedInventory"] == 1
    assert identities["device"]["presentInReturnedInventory"] == 1
    assert identities["app"]["candidateIds"] == 1
    assert all(call[2].get("record_evidence") is False
               for call in agent.executor.calls if call[0].startswith("hub_list_"))
    assert len(agent.executor.evidence.rows) == 2
    assert all(x[2]["mutates"] is False for x in agent.executor.evidence.rows)


def test_no_scheduler_question_does_not_add_inventory_reads():
    from performance_host_plan import collect_broad_performance_outcome
    agent = _Agent()
    asyncio.run(collect_broad_performance_outcome(
        agent, "Analyse my Hubitat performance and recommend improvements."
    ))
    calls = [row[0] for row in agent.executor.calls]
    assert "hub_get_jobs" not in calls
    assert "hub_list_apps" not in calls
    assert "hub_list_devices" not in calls



def test_slow_identity_read_is_bounded_and_retains_other_inventory(monkeypatch):
    import performance_host_plan as plan
    monkeypatch.setattr(plan, "_SCHEDULER_INVENTORY_TIMEOUT_SECONDS", 0.03)
    agent = _Agent(slow_device=True)
    import time
    started = time.monotonic()
    outcome = asyncio.run(plan.collect_broad_performance_outcome(
        agent, "Analyse scheduled jobs and group by owning app and handler for efficiency."
    ))
    assert time.monotonic() - started < 1.0
    result = outcome.metrics["scheduler_inventory_crosscheck"]
    assert result["app"]["presentInReturnedInventory"] == 1
    assert result["device"]["inventory"]["status"] == "unavailable"
    assert result["device"]["presentInReturnedInventory"] == 0
    assert agent.request_metrics.counters["scheduler_inventory_timeout"] == 1
    assert len(agent.executor.evidence.rows) == 2
    assert any(not receipt[2]["success"] for receipt in agent.executor.evidence.rows)


def test_real_metrics_registry_supports_all_scheduler_inventory_paths():
    """Exercise the production allowlist, not only the permissive _Metrics stub."""
    from request_metrics import RequestMetrics

    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        for name in (
            "scheduler_inventory_crosscheck",
            "scheduler_inventory_timeout",
            "scheduler_inventory_read_failure",
        ):
            metrics.increment(name)
        snapshot = metrics.snapshot()
        assert all(snapshot["counters"][name] == 1 for name in (
            "scheduler_inventory_crosscheck",
            "scheduler_inventory_timeout",
            "scheduler_inventory_read_failure",
        ))
    finally:
        metrics.reset(token)


def test_host_scheduler_inventory_path_runs_with_real_request_metrics():
    """Regression: v0.16.139 live request failed before either inventory read."""
    from performance_host_plan import collect_broad_performance_outcome
    from request_metrics import RequestMetrics

    agent = _Agent()
    agent.request_metrics = RequestMetrics()
    token = agent.request_metrics.begin()
    try:
        outcome = asyncio.run(collect_broad_performance_outcome(
            agent, "Analyse all scheduled jobs on my Hubitat hub, "
                   "group them by owning app and handler. Read-only."
        ))
        snapshot = agent.request_metrics.snapshot()
    finally:
        agent.request_metrics.reset(token)

    assert snapshot["counters"]["scheduler_inventory_crosscheck"] == 1
    assert outcome.metrics["scheduler_inventory_crosscheck"]["app"][
        "presentInReturnedInventory"
    ] == 1
    assert outcome.metrics["scheduler_inventory_crosscheck"]["device"][
        "presentInReturnedInventory"
    ] == 1
    assert len([call for call in agent.executor.calls
                if call[0] in ("hub_list_apps", "hub_list_devices")]) == 2


def test_host_scheduler_inventory_timeout_runs_with_real_request_metrics(monkeypatch):
    """Also covers the runtime-only metrics branch on an inventory deadline."""
    import performance_host_plan as plan
    from request_metrics import RequestMetrics

    monkeypatch.setattr(plan, "_SCHEDULER_INVENTORY_TIMEOUT_SECONDS", 0.03)
    agent = _Agent(slow_device=True)
    agent.request_metrics = RequestMetrics()
    token = agent.request_metrics.begin()
    try:
        outcome = asyncio.run(plan.collect_broad_performance_outcome(
            agent, "Analyse scheduled jobs by owning app and handler. Read-only."
        ))
        snapshot = agent.request_metrics.snapshot()
    finally:
        agent.request_metrics.reset(token)

    assert snapshot["counters"]["scheduler_inventory_crosscheck"] == 1
    assert snapshot["counters"]["scheduler_inventory_timeout"] == 1
    assert outcome.metrics["scheduler_inventory_crosscheck"]["app"][
        "presentInReturnedInventory"
    ] == 1
    assert outcome.metrics["scheduler_inventory_crosscheck"]["device"][
        "inventory"
    ]["status"] == "unavailable"


def test_complete_app_inventory_exposes_unlisted_candidate_id_without_deletion_claim():
    report = reconcile_scheduler_candidates(
        sample_jobs(),
        apps={"apps": [{"id": 4209}], "totalOnHub": 1},
        devices=None,
    )
    assert report["app"]["notListedExamples"] == ["1418"]
    assert report["app"]["notCheckedDueToUnavailableInventory"] == 0
    rendering = render_scheduler_inventory_crosscheck(report)
    assert "absent from the returned hub_list_apps snapshot" in rendering
    assert "1418" in rendering
    assert "not proof of stale scheduled jobs" in rendering


def test_complete_compact_context_skips_slow_device_list_and_proves_identity():
    """Real MCP client offers a complete hubitat://context resource."""
    from performance_host_plan import collect_broad_performance_outcome

    class _Context:
        async def get_live_context(self):
            return {
                "devices": [{"id": 1089, "name": "Hub Info",
                             "attributes": {"switch": "on"}}],
                "totalDevices": 1,
                "idsComplete": True,
            }

    agent = _Agent(slow_device=True)
    agent.executor.mcp = _Context()
    outcome = asyncio.run(collect_broad_performance_outcome(
        agent, "Analyse scheduled jobs by owning app and handler for efficiency."
    ))
    device = outcome.metrics["scheduler_inventory_crosscheck"]["device"]
    assert device["presentInReturnedInventory"] == 1
    assert device["inventory"]["complete"] is True
    assert device["inventory"]["source"] == "hubitat://context"
    assert not any(call[0] == "hub_list_devices" for call in agent.executor.calls)
    receipt = [x for x in agent.executor.evidence.rows
               if x[0] == "hub_read_devices"][0]
    assert receipt[1]["resource"] == "hubitat://context"
    assert receipt[2]["mutates"] is False
    assert "attributes" not in str(receipt)


def test_incomplete_compact_context_is_not_promoted_to_complete_when_fallback_times_out(
    monkeypatch,
):
    import performance_host_plan as plan

    class _PartialContext:
        async def get_live_context(self):
            return {
                "devices": [{"id": 1089, "name": "Hub Info"}],
                "totalDevices": 370,
                "idsComplete": False,
            }

    monkeypatch.setattr(plan, "_SCHEDULER_INVENTORY_TIMEOUT_SECONDS", 0.03)
    agent = _Agent(slow_device=True)
    agent.executor.mcp = _PartialContext()
    outcome = asyncio.run(plan.collect_broad_performance_outcome(
        agent, "Analyse scheduled jobs by owning app and handler for efficiency."
    ))
    section = outcome.metrics["scheduler_inventory_crosscheck"]["device"]
    assert section["presentInReturnedInventory"] == 1
    assert section["notListedInReturnedInventory"] == 0
    assert section["notCheckedDueToUnavailableInventory"] == 0
    assert section["inventory"]["complete"] is False
    assert section["inventory"]["source"] == "hubitat://context"
    assert agent.request_metrics.counters["scheduler_inventory_timeout"] == 1


def test_compact_context_reader_failure_uses_bounded_list_fallback():
    from performance_host_plan import collect_broad_performance_outcome

    class _UnavailableContext:
        async def get_live_context(self):
            raise RuntimeError("resource unavailable")

    agent = _Agent()
    agent.executor.mcp = _UnavailableContext()
    outcome = asyncio.run(collect_broad_performance_outcome(
        agent, "Analyse scheduled jobs by owning app and handler for efficiency."
    ))
    section = outcome.metrics["scheduler_inventory_crosscheck"]["device"]
    assert section["presentInReturnedInventory"] == 1
    assert "hub_list_devices" in [call[0] for call in agent.executor.calls]
    fallback_args = [call[1]["args"] for call in agent.executor.calls
                     if call[0] == "hub_list_devices"][0]
    assert fallback_args["limit"] == 125
    assert fallback_args["fields"] == ["id", "name", "label", "room"]


def test_context_completeness_does_not_mean_all_hub_devices_are_present():
    digest = sample_jobs()
    report = reconcile_scheduler_candidates(
        digest,
        apps={"apps": [{"id": 1418}], "totalOnHub": 1},
        devices={"devices": [{"id": 1089}], "totalDevices": 1,
                 "idsComplete": True, "identitySource": "hubitat://context"},
    )
    device = report["device"]
    assert device["inventory"]["complete"] is True
    assert device["presentInReturnedInventory"] == 1
    assert device["notListedInReturnedInventory"] == 1
    message = render_scheduler_inventory_crosscheck(report)
    assert "complete context response; hub-wide census unverified" in message
    assert "may exist elsewhere on Hubitat" in message
    assert "absent from the returned hubitat://context snapshot" in message
    assert "deleted or orphaned entity" not in message


def test_app_inventory_reports_correct_source_not_device_gateway():
    report = reconcile_scheduler_candidates(
        sample_jobs(),
        apps={"apps": [{"id": 1418}], "totalOnHub": 1},
        devices=None,
    )
    assert report["app"]["inventory"]["source"] == "hub_list_apps"


def test_host_scheduler_workflow_probes_context_absent_ids_without_confirming_owner():
    from performance_host_plan import collect_broad_performance_outcome

    class _Context:
        async def get_live_context(self):
            return {"devices": [{"id": 1089, "name": "Hub Info"}],
                    "totalDevices": 1, "idsComplete": True}

    class _SecondaryExecutor(_Executor):
        async def execute(self, gateway, arguments, **kwargs):
            result = await super().execute(gateway, arguments, **kwargs)
            if arguments["tool"] == "hub_get_jobs":
                jobs = result.result.data["scheduledJobs"]
                jobs["count"] = 3
                jobs["jobs"].append({
                    "id": "dev2065Once.checkEventInterval",
                    "method": "checkEventInterval",
                })
            return result

    agent = _Agent()
    agent.executor = _SecondaryExecutor()
    agent.executor.mcp = _Context()
    outcome = asyncio.run(collect_broad_performance_outcome(
        agent, "Analyse all scheduled jobs by owning app and handler. Read-only."
    ))
    summary = outcome.metrics["scheduler_inventory_crosscheck"]
    assert summary["device"]["presentInReturnedInventory"] == 1
    assert summary["device"]["notListedInReturnedInventory"] == 1
    second = summary["secondaryDeviceSource"]
    assert second["candidateIdsAbsentFromContext"] == 1
    assert second["foundInSecondarySource"] == 0
    assert second["unresolvedCandidateIds"] == 1
    assert second["ownershipVerified"] is False
    device_calls = [c for c in agent.executor.calls if c[0] == "hub_list_devices"]
    assert len(device_calls) == 1
    assert device_calls[0][1]["args"]["fields"] == ["id", "name", "label"]
    assert len(agent.executor.evidence.rows) == 3
    assert all(row[2]["mutates"] is False for row in agent.executor.evidence.rows)
