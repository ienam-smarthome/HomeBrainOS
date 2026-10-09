from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from scheduler_secondary_inventory import (
    context_absent_candidates,
    probe_secondary_device_inventory,
)
from performance_inventory_check import render_scheduler_inventory_crosscheck
from performance_job_analysis import summarize_job_workload, render_job_workload_summary


class _Evidence:
    def __init__(self): self.rows = []
    def record(self, gateway, arguments, **kwargs):
        self.rows.append((gateway, arguments, kwargs))


class _Executor:
    def __init__(self, devices=None, *, pause=False):
        self.devices = {str(k): v for k, v in (devices or {}).items()}
        self.pause = pause
        self.calls = []
        self.evidence = _Evidence()

    async def execute(self, gateway, arguments, **kwargs):
        self.calls.append((gateway, arguments, kwargs))
        if self.pause:
            await asyncio.sleep(3)
        identifier = str(arguments["args"]["deviceId"])
        data = self.devices.get(identifier)
        return SimpleNamespace(
            success=data is not None,
            result=SimpleNamespace(data=data),
        )


def _context():
    return {"devices": [{"id": 1089, "name": "Hub Info"}], "totalDevices": 1,
            "idsComplete": True}


def test_context_absent_candidates_ignore_arbitrary_label_or_invalid_ids():
    assert context_absent_candidates([1089, 2065, "6910", True, "unknown"],
                                     _context()) == {"2065", "6910"}
    assert context_absent_candidates([1089], _context()) == set()
    assert context_absent_candidates([1089], None) == set()


def test_targeted_probe_confirms_only_exact_returned_id_and_not_ownership():
    executor = _Executor({
        2065: {"device": {"id": 2065, "name": "Legacy"}},
        6910: {"device": {"id": 9999, "name": "Wrong device"}},
    })
    result = asyncio.run(probe_secondary_device_inventory(
        executor, [1089, 2065, 6910], _context(), budget_seconds=1,
    ))
    assert result["status"] == "sampled"
    assert result["attemptedCandidateIds"] == 2
    assert result["foundInSecondarySource"] == 1
    assert result["unresolvedCandidateIds"] == 1
    assert result["unattemptedCandidateIds"] == 0
    assert result["presentExamples"] == [{"id": "2065", "name": "Legacy"}]
    assert result["ownershipVerified"] is False
    assert result["hubWideCensusVerified"] is False
    assert {c[1]["tool"] for c in executor.calls} == {"hub_get_device"}
    assert {c[1]["args"]["deviceId"] for c in executor.calls} == {"2065", "6910"}
    assert all(c[2]["record_evidence"] is False for c in executor.calls)
    assert all(row[2]["mutates"] is False and row[2]["effect"] == "read"
               for row in executor.evidence.rows)


def test_target_limit_is_six_and_unprobed_candidates_remain_unresolved():
    executor = _Executor({str(i): {"id": i} for i in range(2000, 2010)})
    result = asyncio.run(probe_secondary_device_inventory(
        executor, list(range(2000, 2010)), _context(),
        budget_seconds=1, max_targets=99,
    ))
    assert result["attemptedCandidateIds"] == 6
    assert result["foundInSecondarySource"] == 6
    assert result["unattemptedCandidateIds"] == 4
    assert result["unresolvedCandidateIds"] == 4
    assert len(executor.calls) == 6


def test_failure_or_not_found_never_becomes_deleted():
    executor = _Executor()
    result = asyncio.run(probe_secondary_device_inventory(
        executor, [2065, 6910], _context(), budget_seconds=1
    ))
    assert result["status"] == "unresolved"
    assert result["foundInSecondarySource"] == 0
    assert result["unresolvedCandidateIds"] == 2
    assert result["ownershipVerified"] is False
    assert result["hubWideCensusVerified"] is False


def test_timeout_is_bounded_and_missing_ids_stay_unresolved():
    executor = _Executor(pause=True)
    result = asyncio.run(probe_secondary_device_inventory(
        executor, [2065, 6910], _context(), budget_seconds=.025
    ))
    assert result["status"] in {"timed_out", "partial"}
    assert result["foundInSecondarySource"] == 0
    assert result["unresolvedCandidateIds"] == 2
    assert result["attemptedCandidateIds"] <= 2


def test_no_missing_candidates_produces_no_extra_tool_request():
    executor = _Executor()
    assert asyncio.run(probe_secondary_device_inventory(
        executor, [1089], _context()
    )) is None
    assert executor.calls == []


def test_no_candidate_handlers_are_ranked_only_within_unattributed_jobs():
    digest = summarize_job_workload({
        "scheduledJobs": {"count": 5, "jobs": [
            {"id": "dev1089Recur.poll1", "method": "poll1"},
            {"id": "app1418Once.timeHandler", "method": "timeHandler"},
            {"method": "sendEventReminder"},
            {"method": "sendEventReminder"},
            {"method": "deviceHealthCheck"},
        ]}
    })
    assert digest["rowsWithoutOwnerCandidate"] == 3
    assert digest["topNoCandidateMethods"] == [
        {"method": "sendEventReminder", "jobs": 2},
        {"method": "deviceHealthCheck", "jobs": 1},
    ]
    text = render_job_workload_summary(digest)
    assert "Scheduled entries with no owner candidate" in text
    assert "| sendEventReminder | 2 |" in text
    assert "Method names alone cannot identify" in text


def test_second_source_report_discloses_sample_scope_and_refuses_ownership():
    report = {
        "status": "compared",
        "app": {"candidateIds": 0, "inventory": {"status": "unavailable"}},
        "device": {"candidateIds": 43, "presentInReturnedInventory": 51,
                   "notListedInReturnedInventory": 43,
                   "inventory": {"status": "available", "complete": True,
                                 "reportedTotal": 181, "rowsReturned": 181,
                                 "source": "hubitat://context"}},
        "secondaryDeviceSource": {
            "source": "hub_read_devices/hub_get_device",
            "attemptedCandidateIds": 6, "targetLimit": 6, "status": "sampled",
            "candidateIdsAbsentFromContext": 43,
            "foundInSecondarySource": 1, "unresolvedCandidateIds": 42,
            "unattemptedCandidateIds": 37,
            "presentExamples": [{"id": "2065", "name": "Legacy Sensor"}],
        },
    }
    rendered = render_scheduler_inventory_crosscheck(report)
    assert "6 targeted ID read(s) attempted (limit 6)" in rendered
    assert "37 not sampled" in rendered
    assert "2065 (Legacy Sensor)" in rendered
    assert "Neither an additional match nor an unconfirmed ID proves job ownership" in rendered
    assert "hub-wide census" in rendered
