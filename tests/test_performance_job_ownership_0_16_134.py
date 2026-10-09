from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance_job_analysis import summarize_job_workload, render_job_workload_summary
from performance_api_finalizer import _job_digest_from_packet


def test_group_253_scheduler_rows_without_guessing_cpu_or_daily_executions():
    entries = [
        {
            "appId": 301, "handlerMethod": "sessionTick",
            "nextRun": "2026-10-09T12:14:00",
        }
        for _ in range(35)
    ]
    entries += [
        {"deviceId": 5383, "method": "autoPoll",
         "nextRun": "2026-10-09T12:14:00"}
        for _ in range(5)
    ]
    entries += [
        {"appId": i, "handler": "otherTick",
         "nextRun": f"2026-10-09T12:15:{i % 60:02d}"}
        for i in range(213)
    ]
    snapshot = {"scheduledJobs": {"count": 253, "jobs": entries}}
    summary = summarize_job_workload(snapshot)
    assert summary["reportedJobs"] == 253
    assert summary["rowsExamined"] == 253
    assert summary["completeRows"] is True
    assert summary["ownerIdentifiedRows"] == 253
    assert summary["unattributedRows"] == 0
    assert summary["topOwnerMethods"][0] == {
        "ownerType": "app", "ownerId": "301",
        "method": "sessionTick", "jobs": 35,
    }
    assert summary["topMethods"][0] == {"method": "otherTick", "jobs": 213}
    assert summary["sameNextRunGroups"][0]["jobs"] == 40
    rendered = render_job_workload_summary(summary)
    assert "Scheduled-job workload breakdown" in rendered
    assert "| app | 301 | sessionTick | 35 |" in rendered
    assert "| sessionTick | 35 |" in rendered
    assert "do not prove simultaneous execution or CPU contention" in rendered
    assert "estimated savings" not in rendered.casefold()


def test_partial_response_and_missing_owners_cannot_claim_complete_breakdown():
    data = {"scheduledJobs": {
        "total": 253,
        "entries": [
            {"name": "Block Bedroom3-PC", "handler": "sessionTick",
             "nextRun": "2026-10-09T12:14:00"},
            {"name": "Block Phone", "handler": "sessionTick",
             "nextRun": "2026-10-09T12:14:00"},
        ],
    }}
    summary = summarize_job_workload(data)
    assert summary["rowsExamined"] == 2
    assert summary["reportedJobs"] == 253
    assert summary["completeRows"] is False
    assert summary["ownerIdentifiedRows"] == 0
    assert summary["unattributedRows"] == 2
    assert not summary["topOwnerMethods"]
    output = render_job_workload_summary(summary)
    assert "Only part of the reported job list was returned" in output
    assert "No authoritative owner IDs" in output
    assert "| sessionTick | 2 |" in output


def test_nested_owner_and_map_encoding_are_supported_without_fabricating_ids():
    result = summarize_job_workload({"result": {"scheduledJobs": {
        "count": 2,
        "abc": {"app": {"id": 42}, "handlerMethod": "foo"},
        "def": {"device": {"id": 88}, "methodName": "bar"},
    }}})
    assert result["completeRows"]
    assert result["ownerIdentifiedRows"] == 2
    assert set(r["ownerId"] for r in result["topOwnerMethods"]) == {"42", "88"}


def test_unknown_payload_is_reported_as_unavailable_without_fake_scheduler_rows():
    assert summarize_job_workload({})["status"] == "unavailable"
    assert summarize_job_workload({"scheduledJobs": 253})["status"] == "unavailable"
    assert render_job_workload_summary({"status": "unavailable"}) == ""


def test_job_digest_packet_can_be_decoded_without_relying_on_truncated_raw_rows():
    raw = {"scheduledJobs": {"jobs": [{"appId": 100, "method": "sessionTick"}]}}
    summary = summarize_job_workload(raw)
    prefix = "HOST_JOB_DIGEST:" + json.dumps(summary) + "\nRAW_JOB_EXCERPT:\n..."
    assert _job_digest_from_packet(prefix) == summary
    assert _job_digest_from_packet('{"result":{"scheduledJobs":[]}}') is None
    assert _job_digest_from_packet("HOST_JOB_DIGEST:corrupt") is None


def test_unknown_method_explicitly_shows_unknown_not_invented_polling_frequency():
    summary = summarize_job_workload({"scheduledJobs": [{"appId": 4321}]})
    assert summary["unknownMethodRows"] == 1
    assert summary["topMethods"] == [{"method": "unknown method", "jobs": 1}]
    text = render_job_workload_summary(summary)
    assert "unknown method" in text
    assert "hourly" not in text.lower()
