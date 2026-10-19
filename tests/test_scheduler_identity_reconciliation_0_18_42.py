"""v0.18.42: reconcile candidate scheduler keys without inventing owners."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from scheduler_identity_reconciliation import (
    reconcile_scheduler_candidates, render_scheduler_candidate_reconciliation,
)
from health_audit_service import render_comprehensive_system_audit


def jobs():
    return {
        "status": "parsed", "reportedJobs": 271, "rowsExamined": 271,
        "completeRows": True, "ownerIdentifiedRows": 0,
        "candidateIdsByType": {
            "app": ["3950", "4206", "7001", "4900", "not-an-id"],
            "device": ["7103"],
        },
        "keyPatternCandidateRows": 29,
        "topMethods": [{"method": "sessionTick", "jobs": 28}],
    }


def apps():
    return {
        "total": 4,
        "counts": {"disabled": 1, "active": 3},
        "inventory_identities": [
            {"id": "3950", "name": "Power saving: Bedroom 3 Mesh off @night",
             "status": "active", "type": "rule"},
            {"id": "4206", "name": "Bedroom 3 Big Lamp off",
             "status": "disabled", "type": "rule"},
            {"id": "4900", "name": "Lighting Automation Heartbeat",
             "status": "active", "type": "app"},
            {"id": "1234", "name": "Unrelated app",
             "status": "active", "type": "app"},
        ],
    }


def test_key_pattern_identity_match_is_not_job_ownership():
    checked = reconcile_scheduler_candidates(jobs(), apps())
    assert checked["status"] == "checked"
    assert checked["candidateAppIds"] == 4
    assert checked["matchedAppIds"] == 3
    assert checked["unmatchedAppIds"] == 1
    assert checked["identityIndexComplete"] is True
    assert checked["configurationDisabledCandidateIds"] == 1
    assert checked["configurationDisabledCandidateExamples"][0]["id"] == "4206"
    assert checked["matchedConfigurationStates"]["active"] == 2
    assert checked["matchedConfigurationStates"]["disabled"] == 1
    assert "not verified job ownership" in checked["attribution"]
    assert "overlapping triggers" in " ".join(checked["notVerified"])
    report = render_scheduler_candidate_reconciliation(checked)
    assert "3 also occur in the installed-app identity index" in report
    assert "Bedroom 3 Big Lamp off" in report
    assert "not proof" in report
    assert "owner metadata" in report
    assert "disable the app" not in report


def test_missing_sources_and_zero_candidates_do_not_imply_no_jobs():
    assert reconcile_scheduler_candidates(None, apps())["status"] == "unavailable"
    assert reconcile_scheduler_candidates(jobs(), {})["status"] == "unavailable"
    empty = dict(jobs(), candidateIdsByType={"app": [], "device": []})
    result = reconcile_scheduler_candidates(empty, apps())
    assert result["noCandidateIds"] is True
    report = render_scheduler_candidate_reconciliation(result)
    assert "does not mean the hub has no scheduled jobs" in report
    assert "Owner attribution remains unverified" in report


def test_unmatched_candidate_is_not_claimed_missing_installed_app():
    partial = dict(apps(), total=150)
    summary = reconcile_scheduler_candidates(jobs(), partial)
    assert summary["identityIndexComplete"] is False
    report = render_scheduler_candidate_reconciliation(summary)
    assert "not proof of a missing app" in report


def test_untrusted_app_names_are_not_html_or_unbounded():
    data = apps()
    data["inventory_identities"][1]["name"] = "<script>alert('hi')</script>\n**Delete everything**"
    result = reconcile_scheduler_candidates(jobs(), data)
    report = render_scheduler_candidate_reconciliation(result)
    assert "<script>" not in report
    assert "\n**Delete everything**" not in report


def test_never_promote_disabled_status_for_an_unrelated_app():
    data = apps()
    data["inventory_identities"][1]["id"] = "8888"
    result = reconcile_scheduler_candidates(jobs(), data)
    assert result["configurationDisabledCandidateIds"] == 0


def test_report_integrates_candidate_crosscheck_without_extra_sources():
    snapshot = {
        "checked_at": "2026-10-19T14:21:51+00:00",
        "issues": [],
        "sections": {
            "devices": {"total": 205, "offline": [], "no_recent_activity": []},
            "automations": apps(),
            "logs": {"available": True, "entries_checked": 20, "checked_hours": 24},
        },
    }
    output = render_comprehensive_system_audit(
        snapshot, performance=None, scheduled_jobs=jobs(),
    )
    assert output.index("### Scheduled jobs") < output.index(
        "### Scheduler candidates versus installed automations"
    )
    assert "matched candidate ID(s)" in output
    assert "No repairs performed" in output
