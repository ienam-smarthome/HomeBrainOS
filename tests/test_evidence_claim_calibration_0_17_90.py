"""Regressions for evidence-faithful conclusions across HomeBrain API routes."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from evidence_claim_calibrator import (
    calibrate_supported_conclusions, calibrate_api_outcome,
)
from health_audit_service import _device_findings, render_comprehensive_system_audit


def _partial_fridge_receipts():
    return [
        {
            "success": True,
            "tool": "homebrain_device_history",
            "evidence_kind": "deterministic_device_event_history",
            "details": {
                "label": "Fridge Door Contact",
                "historySourceIntegrityVerified": False,
                "observedEventsTruncated": True,
                "temporalAnalysis": {
                    "coverage": "partial", "intervalCount": 7,
                    "totalActiveSeconds": 51, "totalIsLowerBound": True,
                },
            },
        },
        {
            "success": True, "tool": "hub_manage_logs",
            "sub_tool": "hub_get_logs",
            "arguments": {"tool": "hub_get_logs",
                          "args": {"appId": 2967, "limit": 50}},
            "details": {"logCount": 50, "logs": [{
                "message": "app|2967|Fridge Door Automation|Waiting to stay 0:04:00",
            }]},
        },
    ]


def test_partial_history_calibrates_confidence_without_losing_observations():
    repeated = "**Fridge Door Contact was open for about 51 seconds in total, across 7 recorded intervals.**"
    text = (
        "Fridge door state changes were caused by physical interactions; "
        "the automation functioned exactly as configured.\n\n"
        + repeated + "\n\n" + repeated + "\n\n"
        + "**Confidence**: High. Device history and app logs are perfectly aligned.\n"
        "No other controlling devices or mode changes were observed in the same window."
    )
    result, issues = calibrate_supported_conclusions(
        text, _partial_fridge_receipts(),
    )
    assert result.count(repeated) == 1
    assert "51 seconds" in result
    assert "7 recorded intervals" in result
    assert "0:04:00" not in result  # no invented details
    assert "**Confidence:** The returned observations" in result
    assert "High" not in result
    assert "perfectly aligned" not in result
    assert "functioned exactly as configured" not in result
    assert "caused by physical interactions" not in result
    assert "bounded evidence" in result
    assert "duplicate_summary_removed" in issues
    assert "unqualified_high_confidence" in issues
    assert "partial_history_causal_scope" in issues


def test_complete_verified_history_keeps_supported_strong_claim():
    msg = "**Confidence:** High. Two independent histories are verified."
    receipts = [{
        "success": True, "details": {
            "historySourceIntegrityVerified": True,
            "observedEventsTruncated": False,
            "temporalAnalysis": {"coverage": "complete", "totalIsLowerBound": False},
        },
    }]
    assert calibrate_supported_conclusions(msg, receipts) == (msg, ())


def test_device_watchdog_conclusions_cannot_promote_transport_cause():
    receipt = [{
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool":"hub_get_logs",
                     "args":{"deviceId":"7103","limit":50}},
        "details":{"logCount":2,"logs":[{
            "message":"dev|7103|Bedroom 3 Mesh|Watchdog fired after 32974s without data"
        }]},
    }]
    original = (
        "**Bedroom 3 Mesh is experiencing a complete telemetry failure.** "
        "The watchdog reports a dead connection. Its last recorded successful "
        "MQTT connection was 07:16.\n\n"
        "**Intermittent Connectivity: Contradicted by the logs**.\n"
    )
    result, labels = calibrate_supported_conclusions(
        original, receipt, domain="device_telemetry",
    )
    assert "complete telemetry failure" not in result
    assert "dead connection" not in result
    assert "last recorded successful MQTT connection" not in result
    assert "not excluded outside their coverage" in result
    assert "watchdog_communication_scope" in labels


def test_watchdog_edits_require_device_scoped_recorded_warning():
    original = "complete telemetry failure"
    assert calibrate_supported_conclusions(
        original, [], domain="device_telemetry",
    ) == (original, ())
    unscoped = [{
        "success":True,"sub_tool":"hub_get_logs",
        "arguments":{"tool":"hub_get_logs","args":{"limit":50}},
        "details":{"logs":[{"message":"Watchdog fired after 32974s without data"}]},
    }]
    assert calibrate_supported_conclusions(
        original, unscoped, domain="device_telemetry",
    ) == (original, ())


def test_api_outcome_retains_evidence_and_metrics_without_mutation():
    evidence = _partial_fridge_receipts()
    original = SimpleNamespace(
        message="**Confidence**: High. Histories are perfectly aligned.",
        route="unified-mcp-agent", request_class="live-read",
        metrics={"outcome":"success","counters":{"tool_calls":3}},
        evidence=evidence,
    )
    final = calibrate_api_outcome(original, "Choose a recent unexpected event to investigate")
    assert final.message != original.message
    assert final.route == original.route
    assert final.evidence is original.evidence
    assert final.metrics["counters"]["evidence_claim_calibrations"] > 0
    assert "evidence_claim_calibrations" not in original.metrics["counters"]


def test_standalone_duplicate_removal_preserves_table_rows_and_checklists():
    message = (
        "| State | State |\n| --- | --- |\n| on | on |\n| on | on |\n"
        "- Battery below threshold on the reported current device attribute.\n"
        "- Battery below threshold on the reported current device attribute.\n"
    )
    corrected, changes = calibrate_supported_conclusions(message, [])
    assert corrected == message
    assert changes == ()


def test_audit_recent_activity_does_not_infer_physical_recovery():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 16, 15, 28, tzinfo=timezone.utc)
    devices = [{
        "id": "7103", "label": "Bedroom 3 Mesh",
        "attributes": {"healthStatus": "offline", "lastActivity":"2026-10-16T15:26:21+00:00"},
    }]
    stats, issues = _device_findings(devices, low_battery_threshold=20, now=now)
    assert stats["offline_count"] == 1
    row = stats["offline"][0]
    assert row["reachability_independently_verified"] is False
    assert row["recent_activity_conflict"] is True
    audit = {
        "checked_at":now.isoformat(),
        "sections":{"devices":{"available":True, **stats}, "automations":{"available":True,"total":0},
                    "logs":{"available":True,"entries_checked":0,"checked_hours":24}},
        "issues":issues,
    }
    content = render_comprehensive_system_audit(audit, None)
    assert "Status/activity metadata overlap" in content
    assert "watchdog-generated health/status event" in content
    assert "not independent evidence of recovery" in content
