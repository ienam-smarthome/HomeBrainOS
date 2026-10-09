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
    def __init__(self):
        self.rows = []

    def record(self, gateway, arguments, **kwargs):
        self.rows.append((gateway, arguments, kwargs))


class _Executor:
    def __init__(self, pages=None, *, pause=False):
        self.pages = pages or {}
        self.pause = pause
        self.calls = []
        self.evidence = _Evidence()

    async def execute(self, gateway, arguments, **kwargs):
        self.calls.append((gateway, arguments, kwargs))
        if self.pause:
            await asyncio.sleep(3)
        offset = arguments["args"]["offset"]
        data = self.pages.get(offset)
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


def test_secondary_pagination_can_verify_additional_presence_not_job_ownership():
    executor = _Executor({
        0: {"devices": [{"id": 1089}, {"id": 2065, "name": "Legacy"}],
            "hasMore": True, "nextOffset": 2, "total": 3},
        2: {"devices": [{"id": 6000}], "hasMore": False, "total": 3},
    })
    result = asyncio.run(probe_secondary_device_inventory(
        executor, [1089, 2065, 6910], _context(),
        page_size=2, max_pages=3, budget_seconds=1,
    ))
    assert result["status"] == "complete"
    assert result["foundInSecondarySource"] == 1
    assert result["unresolvedCandidateIds"] == 1
    assert result["presentExamples"] == [{"id": "2065", "name": "Legacy"}]
    assert result["ownershipVerified"] is False
    assert result["hubWideCensusVerified"] is False
    assert [c[1]["args"]["offset"] for c in executor.calls] == [0, 2]
    assert all(c[1]["args"]["fields"] == ["id", "name", "label"]
               for c in executor.calls)
    assert all(c[2]["record_evidence"] is False for c in executor.calls)
    assert all(row[2]["mutates"] is False and row[2]["effect"] == "read"
               for row in executor.evidence.rows)


def test_partial_and_duplicate_results_never_claim_complete_inventory():
    executor = _Executor({
        0: {"devices": [{"id": 2065}, {"id": 2065}],
            "hasMore": False, "total": 2},
    })
    result = asyncio.run(probe_secondary_device_inventory(
        executor, [2065, 6910], _context(), page_size=2, budget_seconds=1
    ))
    assert result["status"] == "partial"
    assert result["foundInSecondarySource"] == 1
    assert result["unresolvedCandidateIds"] == 1
    assert result["ownershipVerified"] is False


def test_timeout_is_bounded_and_missing_id_stays_unresolved():
    executor = _Executor(pause=True)
    result = asyncio.run(probe_secondary_device_inventory(
        executor, [2065], _context(), budget_seconds=.025
    ))
    assert result["status"] == "timed_out"
    assert result["foundInSecondarySource"] == 0
    assert result["unresolvedCandidateIds"] == 1
    assert result["pageCount"] == 0
    assert len(executor.calls) == 1
    assert executor.evidence.rows[0][2]["success"] is False


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


def test_second_source_report_explicitly_refuses_ownership_inference():
    report = {
        "status": "compared",
        "app": {"candidateIds": 0, "inventory": {"status": "unavailable"}},
        "device": {"candidateIds": 2, "presentInReturnedInventory": 1,
                   "notListedInReturnedInventory": 1,
                   "inventory": {"status": "available", "complete": True,
                                 "reportedTotal": 1, "rowsReturned": 1,
                                 "source": "hubitat://context"}},
        "secondaryDeviceSource": {
            "source": "hub_read_devices/hub_list_devices", "pageCount": 1,
            "rowsReturned": 2, "status": "complete",
            "candidateIdsAbsentFromContext": 1,
            "foundInSecondarySource": 1, "unresolvedCandidateIds": 0,
            "presentExamples": [{"id": "2065", "name": "Legacy Sensor"}],
        },
    }
    rendered = render_scheduler_inventory_crosscheck(report)
    assert "Second-source device-ID check" in rendered
    assert "2065 (Legacy Sensor)" in rendered
    assert "Neither an additional match nor an unconfirmed ID proves job ownership" in rendered
    assert "hub-wide census" in rendered
