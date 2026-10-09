from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_job_analysis import summarize_job_workload, render_job_workload_summary
from performance_host_plan import (
    is_scheduler_optimization_request, is_broad_performance_request,
    wants_scheduler_evidence,
)
from performance_api_finalizer import _repair_unverified_app_cleanup_and_empty_scoped_reads


def test_encoded_job_id_is_only_unverified_candidate():
    payload = {"scheduledJobs": {
        "total": 4,
        "jobs": [
            {"id": "dev7334Once", "handlerMethod": "deviceHealthCheck"},
            {"jobId": "app4151Once", "method": "sessionTick"},
            {"deviceId": 5383, "id": "dev5383Once", "method": "autoPoll"},
            {"name": "dev891Once", "handler": "heartbeat"},
        ],
    }}
    d = summarize_job_workload(payload)
    assert d["status"] == "parsed"
    assert d["rowsExamined"] == 4
    assert d["ownerIdentifiedRows"] == 1
    assert d["unattributedRows"] == 3
    assert d["keyPatternCandidateRows"] == 2
    assert {"candidateOwnerId": "7334", "ownerType": "device",
            "method": "deviceHealthCheck", "jobs": 1,
            "attribution": "scheduler-key-pattern"} in d["topCandidateOwnerMethods"]
    assert {"candidateOwnerId": "4151", "ownerType": "app",
            "method": "sessionTick", "jobs": 1,
            "attribution": "scheduler-key-pattern"} in d["topCandidateOwnerMethods"]
    output = render_job_workload_summary(d)
    assert "Scheduler-key owner candidates — not verified" in output
    assert "not proof" in output
    assert "Exact owner IDs were present for 1 of 4" in output
    assert "| 7334 | deviceHealthCheck | 1 |" in output


def test_scheduler_dict_key_is_preserved_and_decoded_without_guessing():
    summary = summarize_job_workload({"scheduledJobs": {
        "count": 3,
        "dev7334Once": {"id": "unrelated-job-id", "handler": "watchdogCheck"},
        "app4151Once": {"handler": "sessionTick"},
        "dev7334OnceExtra": {"handler": "other"},
    }})
    assert summary["rowsExamined"] == 3
    assert summary["ownerIdentifiedRows"] == 0
    assert summary["unattributedRows"] == 3
    assert summary["keyPatternCandidateRows"] == 2
    assert summary["completeRows"]


def test_false_lookalike_job_ids_do_not_become_owners():
    snapshot = {"scheduledJobs": [
        {"id": "dev100"},
        {"id": "dev100OnceOnce"},
        {"id": "device100Once"},
        {"id": "app0Once"},
        {"id": "dev100OnceExtra"},
        {"name": "dev7555Once"},
    ]}
    result = summarize_job_workload(snapshot)
    assert result["keyPatternCandidateRows"] == 0
    assert result["unattributedRows"] == 6


def test_exact_scheduler_efficiency_prompt_uses_evidence_host_plan():
    prompt = (
        "Analyse all scheduled jobs on my Hubitat hub, group them by owning app and handler, "
        "identify unnecessary work and recommend safe efficiency improvements. Read-only."
    )
    assert is_scheduler_optimization_request(prompt)
    assert is_broad_performance_request(prompt)
    assert wants_scheduler_evidence(prompt)
    assert not is_scheduler_optimization_request("How many scheduled jobs are running?")
    assert not is_scheduler_optimization_request("What's the Bedroom temperature?")


def test_hypothesis_heading_respects_successful_empty_scoped_lg_log_read():
    text = (
        "### Diagnostic Hypotheses\n"
        "**Hypothesis 2: LG webOS TV Latency**\n"
        "- **Confirmed Finding:** Device 7486 has 3043 ms average latency.\n"
        "- **Diagnostic Evidence:** No bounded log rows were retained for deviceId=7486.\n"
        "- **Hypothesis:** No target-scoped diagnostic evidence was read for this outlier in this turn, "
        "so the mechanism remains unresolved.\n"
        "- **Verification:** Perform read-only connectivity inspection.\n"
    )
    evidence = [{"sub_tool": "hub_get_logs", "success": True,
                 "arguments": {"args": {"deviceId": "7486", "since": "6h"}},
                 "details": {"logCount": 0, "adaptiveTarget": {
                     "kind": "device", "id": "7486", "name": "LG webOS TV"
                 }}}]
    corrected, changed = _repair_unverified_app_cleanup_and_empty_scoped_reads(
        text, evidence
    )
    assert changed
    assert "No target-scoped diagnostic evidence was read" not in corrected
    assert "succeeded but returned no rows for 6h" in corrected
    assert "zero log rows do not prove normal operation" in corrected
    assert "No bounded log rows were retained" in corrected
