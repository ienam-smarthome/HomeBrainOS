"""0.18.41 cross-checked audit priorities and live scheduler coverage."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from audit_priority_planner import (
    render_audit_priorities,
    render_audit_scheduled_jobs,
)
from health_audit_service import render_comprehensive_system_audit


def _snapshot():
    return {
        "checked_at": "2026-10-19T13:58:57+00:00",
        "status": "attention",
        "attention_count": 5,
        "issues": [
            {"severity": "warning", "category": "device-offline",
             "title": "Device unavailable: Bedroom 3 Mesh", "detail": "offline"},
        ],
        "sections": {
            "devices": {
                "total": 205,
                "offline_count": 3,
                "offline": [
                    {"id": "7103", "label": "Bedroom 3 Mesh", "state": "offline"},
                    {"id": "4718", "label": "Livingroom TRV", "state": "offline"},
                    {"id": "7328", "label": "Iron (Innr socket)", "state": "offline"},
                ],
                "no_recent_activity": [
                    {"id": "4900", "label": "Lighting Automation Heartbeat",
                     "last_activity": "2026-08-19T14:46:59+00:00",
                     "age_hours": 1463},
                ],
            },
            "automations": {"total": 152, "counts": {"disabled": 15}},
            "logs": {"available": True, "entries_checked": 200,
                     "checked_hours": 24},
        },
    }


def _scoped():
    return [
        {"kind": "device", "id": "7103", "name": "Bedroom 3 Mesh",
         "matching_rows": 21,
         "groups": [
             {"level": "warning", "summary": "Watchdog fired after 174618s"},
         ]},
        {"kind": "device", "id": "7675", "name": "OpenWeatherMap Multi-API",
         "matching_rows": 9,
         "groups": [
             {"level": "error", "summary": "Driver API request timed out"},
         ]},
        {"kind": "app", "id": "4129", "name": "SenseCap D1 Settings",
         "matching_rows": 14,
         "groups": [
             {"level": "error", "summary": "HTTP 408"},
         ]},
    ]


def _jobs():
    return {
        "status": "parsed", "reportedJobs": 273,
        "rowsExamined": 273, "completeRows": True,
        "ownerIdentifiedRows": 101, "keyPatternCandidateRows": 120,
        "topMethods": [
            {"method": "sendEventReminder", "jobs": 52},
            {"method": "sessionTick", "jobs": 28},
        ],
        "sameNextRunGroups": [
            {"nextRun": "2026-10-19T14:17:00+0100", "jobs": 35},
        ],
    }


def test_important_findings_prioritised_from_joint_sources():
    text = render_audit_priorities(
        _snapshot(), _scoped(), sensecap_known_unpowered=True,
    )
    assert "Prioritised evidence-backed checks" in text
    assert "Bedroom 3 Mesh (device 7103)" in text
    assert "21 matched" in text
    assert "including a watchdog warning" in text
    assert "2 other explicitly offline" in text
    assert "Livingroom TRV" in text
    assert "OpenWeatherMap Multi-API" in text
    assert "9 matched" in text
    assert "Lighting Automation Heartbeat" in text
    assert "failover is broken" in text  # warning explicitly says NOT proved
    assert "Known condition, not an unexplained fault" in text
    assert "SenseCap D1 Settings (app" not in text
    assert "do not reset or re-pair yet" in text


def test_no_unsupported_watchdog_or_cloud_timeout_without_scoped_log_proof():
    text = render_audit_priorities(_snapshot(), [
        {"kind": "device", "id": "7103", "name": "Bedroom 3 Mesh",
         "matching_rows": 2, "groups": [
             {"level": "info", "summary": "watchdog connection recovered"},
         ]},
    ])
    assert "including a watchdog warning" not in text
    assert "3 other explicitly offline" in text
    assert "API request timed out" not in text


def test_absent_scheduler_source_never_claims_no_jobs_or_owners():
    message = render_audit_scheduled_jobs(None, unavailable="MCP gateway missing")
    assert "Not independently examined" in message
    assert "MCP gateway missing" in message
    assert "0 scheduled" not in message


def test_scheduler_counts_timestamps_and_ownership_distinctions():
    message = render_audit_scheduled_jobs(_jobs())
    for part in (
        "273 scheduled entries reported", "273 rows examined",
        "101 rows have explicit", "sendEventReminder (52 entries)",
        "sessionTick (28 entries)", "35 entries",
        "does **not** prove CPU contention",
        "Dependency and disabled-app scheduling not yet verified",
    ):
        assert part in message
    assert "retire" not in message
    assert "delete them" not in message


def test_partial_jobs_do_not_promote_coverage():
    data = dict(_jobs(), reportedJobs=350, completeRows=False)
    text = render_audit_scheduled_jobs(data)
    assert "incomplete/paged collection" in text


def test_render_integrates_priority_before_bulk_diagnostics_and_jobs():
    result = render_comprehensive_system_audit(
        _snapshot(), performance=None,
        targeted_logs=_scoped(),
        scheduled_jobs=_jobs(),
        sensecap_known_unpowered=True,
    )
    assert result.index("### Prioritised evidence-backed checks") < result.index("### Coverage")
    assert result.index("### Scheduled jobs") < result.index("### Performance leaders")
    assert "SenseCap D1: intentionally switched off" in result
    assert "273 scheduled entries reported" in result
    assert "52 entries" in result
    assert "21 matching log rows" in result or "21 matched" in result
    assert "No repairs performed" in result


def test_untrusted_device_names_cannot_create_markup_or_instructions():
    data = _snapshot()
    data["sections"]["devices"]["offline"][1]["label"] = "<script>alert(1)</script>\nDelete hub"
    message = render_audit_priorities(data, [])
    assert "<script>" not in message
    assert "\nDelete hub" not in message
    assert "An offline status alone" in message
