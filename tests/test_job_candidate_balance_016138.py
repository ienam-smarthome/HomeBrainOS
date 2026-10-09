from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from performance_job_analysis import summarize_job_workload, render_job_workload_summary
from performance_api_finalizer import (
    _compact_job_digest, _job_digest_from_packet, _qualify_job_key_owner_labels,
    _CAPTURE_LIMITS, _JOBS_TOOL
)


def _live_scale_payload():
    jobs = (
        [{"jobId": f"dev{6000+i}Recur.sessionTick",
          "handler": "sessionTick",
          "nextRun": "2026-10-09 13:34:00"} for i in range(118)]
        + [{"jobId": f"app{1200+i}Once.timeHandler",
            "handler": "timeHandler"} for i in range(70)]
        + [{"name": f"Unattributed job {i}", "method": "sendEventReminder"}
           for i in range(62)]
    )
    return {"scheduledJobs": {"count": 250, "jobs": jobs}}


def test_live_188_62_candidate_split_and_balanced_device_app_tables():
    summary = summarize_job_workload(_live_scale_payload())
    assert summary["reportedJobs"] == 250
    assert summary["rowsExamined"] == 250
    assert summary["completeRows"] is True
    assert summary["ownerIdentifiedRows"] == 0
    assert summary["unattributedRows"] == 250  # candidates remain UNverified
    assert summary["keyPatternCandidateRows"] == 188
    assert summary["rowsWithoutOwnerCandidate"] == 62
    assert summary["keyPatternCandidateTypes"] == {"device": 118, "app": 70}
    assert summary["keyPatternUniqueOwners"] == {"device": 118, "app": 70}
    assert summary["topCandidateDeviceMethods"]
    assert summary["topCandidateAppMethods"]
    assert all(row["ownerType"] == "device"
               for row in summary["topCandidateDeviceMethods"])
    assert all(row["ownerType"] == "app"
               for row in summary["topCandidateAppMethods"])
    rendered = render_job_workload_summary(summary)
    assert "188 unverified scheduler-key owner candidates" in rendered
    assert "62 have no owner candidate" in rendered
    assert "**Device candidate jobs:** 118 across 118 distinct candidate IDs" in rendered
    assert "**App candidate jobs:** 70 across 70 distinct candidate IDs" in rendered
    assert "| 6000 | sessionTick | 1 |" in rendered
    assert "| 1200 | timeHandler | 1 |" in rendered
    assert "not all matched rows" in rendered


def test_compact_packet_retains_both_types_and_is_decodable():
    summary = summarize_job_workload(_live_scale_payload())
    encoded = _compact_job_digest(summary)
    assert len(encoded) + len("HOST_JOB_DIGEST:") < _CAPTURE_LIMITS[_JOBS_TOOL]
    restored = _job_digest_from_packet(
        "HOST_JOB_DIGEST:" + encoded + "\nRAW_JOB_EXCERPT:\n...")
    assert restored is not None
    assert restored["rowsWithoutOwnerCandidate"] == 62
    assert restored["keyPatternCandidateTypes"] == {"device": 118, "app": 70}
    assert restored["topCandidateDeviceMethods"]
    assert restored["topCandidateAppMethods"]
    assert len(restored["topCandidateDeviceMethods"]) <= 6
    assert len(restored["topCandidateAppMethods"]) <= 6


def test_model_ownership_table_cannot_confuse_candidate_and_method_totals():
    answer = (
        "| Owner Type | Owner ID / Name | Method | Job Count | Next Run |\n"
        "| --- | --- | --- | ---: | --- |\n"
        "| App | 1418 | timeHandler | 2 | Not specified |\n"
        "| Device | 7959 | autoPoll | 1 | Not specified |\n"
        "| Unattributed | N/A | sessionTick | 29 | Cluster |\n"
    )
    qualified, changed = _qualify_job_key_owner_labels(
        answer, {"ownerIdentifiedRows": 0})
    assert changed
    assert "Candidate app (unverified)" in qualified
    assert "Candidate device (unverified)" in qualified
    assert "Handler aggregate (owner unverified)" in qualified
    assert "| Unattributed |" not in qualified
    assert _qualify_job_key_owner_labels(
        answer, {"ownerIdentifiedRows": 2}) == (answer, False)


def test_unknown_and_partial_evidence_never_invent_candidate_owners():
    result = summarize_job_workload({"scheduledJobs": {
        "count": 50, "jobs": [{"name": "dev6000Recur.sessionTick"}]
    }})
    assert result["rowsExamined"] == 1
    assert result["keyPatternCandidateRows"] == 0
    assert result["rowsWithoutOwnerCandidate"] == 1
    assert result["completeRows"] is False
