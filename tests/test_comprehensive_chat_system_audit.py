from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from health_audit_service import (  # noqa: E402
    is_comprehensive_system_audit_request,
    render_comprehensive_system_audit,
    run_comprehensive_chat_audit,
    _concise_log_message,
    _fault_first_log_targets,
    _live_push_log_evidence,
    _scoped_log_pattern_summary,
    _audit_log_time_quality,
    _log_findings,
    _device_findings,
    _bounded_log_window_evidence,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _snapshot() -> dict:
    return {
        "status": "attention",
        "checked_at": "2026-10-08T11:40:00+00:00",
        "attention_count": 2,
        "issues": [
            {
                "severity": "warning",
                "title": "Low battery: Livingroom TRV",
                "detail": "1% (threshold 20%).",
            },
            {
                "severity": "warning",
                "title": "LG webOS retry warning",
                "detail": "Connection retrying; cause not verified.",
                "count": 3,
            },
        ],
        "sections": {
            "devices": {
                "total": 370,
                "offline_count": 0,
                "low_battery_count": 1,
                "no_recent_activity": [{
                    "id": "7002",
                    "label": "Bedroom 3 FP2",
                    "age_hours": 480,
                    "last_activity": "2026-09-18T11:40:00+00:00",
                }],
                "expected_update_overdue": [],
            },
            "automations": {
                "total": 202,
                "attention_count": 0,
            },
            "logs": {
                "available": True,
                "entries_checked": 200,
                "checked_hours": 24,
            },
        },
    }


def _performance() -> dict:
    return {
        "deviceStats": [{
            "id": "7001",
            "name": "LG webOS TV",
            "pctBusy": 15.4,
            "pctTotal": 1.9,
            "averageMs": 140.0,
        }],
        "appStats": [{
            "id": "9001",
            "name": "SenseCap D1 Settings",
            "pctBusy": 16.5,
            "pctTotal": 2.0,
            "averageMs": 150.0,
        }],
    }


def test_comprehensive_audit_intent_is_narrow_and_read_only() -> None:
    assert is_comprehensive_system_audit_request(
        "check hub logs - including device stats, app stats, hub events etc "
        "for any issues and fix"
    )
    assert is_comprehensive_system_audit_request("Run a full system check")
    assert not is_comprehensive_system_audit_request(
        "Which driver controls Bedroom 1 Light?"
    )
    assert not is_comprehensive_system_audit_request(
        "Show the last logs for the LG TV"
    )
    assert not is_comprehensive_system_audit_request(
        "Pause the SenseCap D1 Settings app"
    )


def test_report_separates_stale_observations_from_offline_faults() -> None:
    message = render_comprehensive_system_audit(
        _snapshot(), _performance(),
        targeted_logs=[{
            "kind": "device", "id": "7001", "name": "LG webOS TV",
            "matching_rows": 2,
            "groups": [{"level": "warning", "count": 2, "summary": "Retrying"}],
        }],
    )
    assert "Low battery: Livingroom TRV" in message
    assert "Bedroom 3 FP2" in message
    assert "not offline verdicts" in message
    assert "0 explicitly reported unavailable" in message
    assert "LG webOS TV" in message
    assert "SenseCap D1 Settings" in message
    assert "not automatic faults" in message
    assert "2 matching log rows within 6h" in message
    assert "no devices, rules, apps or settings have been changed" in message
    assert "not proof that older or omitted events are absent" in message


class _FakeAudit:
    def __init__(self) -> None:
        self.reasons = []

    async def run(self, *, reason: str):
        self.reasons.append(reason)
        return _snapshot()


class _FakeMCP:
    def __init__(self, *, performance_ok: bool = True) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.performance_ok = performance_ok

    async def list_tools(self):
        return [MCPTool(
            "hub_manage_logs", "logs",
            {"type": "object", "properties": {
                "args": {"type": "object"},
            }},
        )]

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        leaf = arguments["args"]["tool"]
        if leaf == "hub_get_performance_stats":
            return MCPToolResult(
                name, arguments, {}, "",
                _performance() if self.performance_ok else {"success": False},
            )
        assert leaf == "hub_get_logs"
        return MCPToolResult(name, arguments, {}, "", {"logs": [
            {
                "level": "WARN",
                "message": "dev|7001|LG webOS TV|websocket connection retrying",
            },
            {
                "level": "WARN",
                "message": "app|9001|SenseCap D1 Settings|long polling time",
            },
            {"level": "ERROR", "message": "An unrelated device error"},
        ]})


def test_full_chat_audit_collects_scoped_followups_without_mutations() -> None:
    mcp = _FakeMCP()
    audit = _FakeAudit()
    result = asyncio.run(run_comprehensive_chat_audit(audit, mcp))

    assert audit.reasons == ["chat"]
    assert result.route == "comprehensive-system-audit"
    assert result.request_class == "live-read"
    assert result.request_class == "live-read"
    assert result.evidence[0]["mutates"] is False
    assert len(mcp.calls) == 4
    assert [call[1]["args"]["tool"] for call in mcp.calls] == [
        "hub_get_performance_stats", "hub_get_logs", "hub_get_logs", "hub_get_logs",
    ]
    assert mcp.calls[1][1]["args"]["args"]["appId"] == "9001"
    assert mcp.calls[2][1]["args"]["args"]["deviceId"] == "7001"
    assert "websocket connection retrying" in result.message
    scoped_section = result.message.split(
        "- Follow-up for device LG webOS TV:", 1
    )[-1].split("- Follow-up for app ", 1)[0]
    assert "An unrelated device error" not in scoped_section
    assert "no devices, rules, apps or settings have been changed" in result.message


def test_audit_remains_available_when_performance_gateway_fails() -> None:
    mcp = _FakeMCP(performance_ok=False)
    result = asyncio.run(run_comprehensive_chat_audit(_FakeAudit(), mcp))
    assert len(mcp.calls) == 2
    assert "Low battery: Livingroom TRV" in result.message
    assert "Performance statistics unavailable" in result.message
    assert "No repairs performed" in result.message


def test_chat_request_uses_full_audit_before_general_agent(monkeypatch) -> None:
    import app as app_module

    invoked = []

    async def fake_full_audit(audit, mcp):
        invoked.append((audit, mcp))
        return type("Outcome", (), {"message": "Full audit completed"})()

    async def unexpected_agent(*_args, **_kwargs):
        raise AssertionError("Generic agent should not handle comprehensive audit")

    monkeypatch.setattr(app_module, "run_comprehensive_chat_audit", fake_full_audit)
    monkeypatch.setattr(app_module.agent, "process_user_request_result", unexpected_agent)

    prompt = "check hub logs including device stats, app stats, hub events for issues and fix"
    result = asyncio.run(app_module._agent_request(app_module.ChatRequest(prompt=prompt)))

    assert result.message == "Full audit completed"
    assert invoked == [(app_module.health_audit, app_module.mcp)]



def test_name_only_broken_markers_are_unverified_not_confirmed_faults() -> None:
    snapshot = _snapshot()
    snapshot["issues"].append({
        "category": "automation",
        "severity": "warning",
        "title": "Automation broken: Tuya Remote: button 4 pushed",
        "detail": "Hubitat marked the automation name *BROKEN*.",
    })
    snapshot["issues"].append({
        "category": "automation",
        "severity": "warning",
        "title": "Automation broken: Hallway Lighting",
        "detail": "Hubitat reports broken=true.",
    })
    report = render_comprehensive_system_audit(snapshot, _performance())
    assert "Automations flagged by name only — 1, unverified" in report
    assert "- Tuya Remote: button 4 pushed" in report
    assert "**WARNING: Automation broken: Hallway Lighting**" in report
    assert "**WARNING: Automation broken: Tuya Remote" not in report
    assert "does not independently demonstrate a current execution failure" in report
    assert "Name-marked automations" in report


def test_populations_are_not_subtracted_and_exact_sample_id_overlap_is_used() -> None:
    snapshot = _snapshot()
    snapshot["sections"]["devices"]["inventory_ids"] = ["7001", "8009"]
    performance = _performance()
    performance["deviceSummary"] = {"totalDevices": 370}
    performance["appSummary"] = {"totalApps": 202}
    performance["deviceStats"].append({
        "id": "9999", "name": "Unselected Thing",
        "pctBusy": 0.1, "pctTotal": 0.01, "averageMs": 20,
    })
    report = render_comprehensive_system_audit(snapshot, performance)
    assert "370 reported total; 2 top-ranked rows returned" in report
    assert "202 reported total; 1 top-ranked rows returned" in report
    assert "Exact ID overlap: 1 of 2 sampled" in report
    assert "Unselected Thing" in report
    assert "does NOT prove these devices are missing from Hubitat" in report
    assert "are not equivalent populations" in report


def test_saturated_log_sample_warns_of_partial_coverage() -> None:
    report = render_comprehensive_system_audit(_snapshot(), _performance())
    assert "**Log window saturated:**" in report
    assert "not verify complete 24-hour log coverage" in report
    snapshot = _snapshot()
    snapshot["sections"]["logs"]["entries_checked"] = 5
    assert "**Log window saturated:**" not in render_comprehensive_system_audit(
        snapshot, _performance()
    )


def test_nested_mcp_rule_server_log_uses_meaningful_message() -> None:
    raw = (
        "app|4151|MCP Rule Server|[MCP1] "
        '{"appId":"4151","entry":{"component":"server","level":"error",'
        '"message":"Validation error in hub_list_devices: incompatible projection",'
        '"timestamp":"2026-10-08T11:00:00Z"}}'
    )
    assert _concise_log_message(raw) == (
        "Validation error in hub_list_devices: incompatible projection"
    )
    truncated = raw[:-3]
    assert "Validation error in hub_list_devices" in _concise_log_message(truncated)


def test_diagnostic_receipts_track_each_source_without_claiming_mutation() -> None:
    mcp = _FakeMCP()
    result = asyncio.run(run_comprehensive_chat_audit(_FakeAudit(), mcp))
    kinds = [(row["tool"], row.get("sub_tool")) for row in result.evidence]
    assert ("health_audit.run", "devices") in kinds
    assert ("health_audit.run", "automations") in kinds
    assert ("health_audit.run", "logs") in kinds
    assert ("hub_manage_logs", "hub_get_performance_stats") in kinds
    assert kinds.count(("hub_manage_logs", "hub_get_logs")) == 3
    assert all(row["effect"] == "read" and row["mutates"] is False for row in result.evidence)
    assert result.evidence[0]["summary"].endswith("flagged findings")


def test_incomplete_audit_sources_have_unsuccessful_receipts() -> None:
    class IncompleteAudit:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["devices"] = {"available": False}
            snapshot["sections"]["logs"] = {"available": False}
            return snapshot

    result = asyncio.run(run_comprehensive_chat_audit(IncompleteAudit(), _FakeMCP()))
    by_section = {
        receipt.get("sub_tool"): receipt
        for receipt in result.evidence
        if receipt.get("evidence_kind") == "audit_source_section"
    }
    assert not by_section["devices"]["success"]
    assert not by_section["logs"]["supports_live_claim"]
    assert by_section["automations"]["success"]
    assert "Incomplete sources: device inventory, logs" in result.message



def test_headline_counts_exclude_unverified_broken_name_markers() -> None:
    snapshot = _snapshot()
    snapshot["issues"].append({
        "domain": "automations", "category": "automation",
        "severity": "warning",
        "title": "Automation broken: Tuya Button: button 3 pushed",
        "detail": "Hubitat marked the automation name *BROKEN*.",
    })
    snapshot["sections"]["automations"]["attention_count"] = 1
    report = render_comprehensive_system_audit(snapshot, _performance())
    assert "Alert signals: 2 from current health/log/automation data; 1 name-only" in report
    assert "1 name-only markers and 0 other automation alerts" in report
    assert "3 flagged for attention" not in report


def test_headline_with_only_name_markers_is_not_unqualified_attention() -> None:
    snapshot = _snapshot()
    snapshot["issues"] = [{
        "domain": "automations", "category": "automation",
        "severity": "warning", "title": "Automation broken: Example",
        "detail": "Hubitat marked the automation name *BROKEN*.",
    }]
    report = render_comprehensive_system_audit(snapshot, _performance())
    assert "audit — REVIEW NAME MARKERS" in report
    assert "Alert signals: 0 from current health/log/automation data; 1 name-only" in report


def test_bounded_historical_logs_after_full_initial_page() -> None:
    mcp = _FakeMCP()
    result = asyncio.run(run_comprehensive_chat_audit(_FakeAudit(), mcp))
    args = mcp.calls[-1][1]["args"]["args"]
    assert args["limit"] == 200
    assert args["since"] == "2026-10-07T11:40:00+00:00"
    assert args["until"] == "2026-10-08T05:40:00+00:00"
    assert "Older-log follow-up (24h to 6h before audit)" in result.message
    assert any(
        r.get("evidence_kind") == "chat_audit_historical_logs" and r["success"]
        for r in result.evidence
    )
    assert all(r["mutates"] is False for r in result.evidence)


def test_unsaturated_sample_skips_historical_request() -> None:
    class FewLogs:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["logs"]["entries_checked"] = 3
            return snapshot
    mcp = _FakeMCP()
    result = asyncio.run(run_comprehensive_chat_audit(FewLogs(), mcp))
    assert len(mcp.calls) == 3
    assert "Older-log follow-up" not in result.message


def test_complete_live_context_reconciles_unlisted_device_ids() -> None:
    class CrosscheckAudit:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["logs"]["entries_checked"] = 5
            snapshot["sections"]["devices"]["inventory_ids"] = ["1000"]
            return snapshot
    class MCPWithContext(_FakeMCP):
        async def get_live_context(self, refresh=False):
            return {
                "devices": [
                    {"id": "7001", "label": "LG webOS TV"},
                    {"id": "1000", "label": "Another"},
                ],
                "totalDevices": 2,
                "idsComplete": True,
                "truncated": False,
                "partial": False,
            }
    result = asyncio.run(run_comprehensive_chat_audit(CrosscheckAudit(), MCPWithContext()))
    assert "Independent live-context cross-check: 1 of 1" in result.message
    assert "IDs found in live context: LG webOS TV" in result.message
    assert any(
        r.get("evidence_kind") == "chat_audit_inventory_crosscheck" and r["success"]
        for r in result.evidence
    )


def test_incomplete_live_context_never_claims_device_absence() -> None:
    class CrosscheckAudit:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["logs"]["entries_checked"] = 5
            snapshot["sections"]["devices"]["inventory_ids"] = ["1000"]
            return snapshot
    class MCPWithPartialContext(_FakeMCP):
        async def get_live_context(self, refresh=False):
            return {"devices": [], "idsComplete": False, "truncated": True}
    result = asyncio.run(
        run_comprehensive_chat_audit(CrosscheckAudit(), MCPWithPartialContext())
    )
    assert "live-context cross-check unavailable or incomplete" in result.message
    assert not any(
        r.get("evidence_kind") == "chat_audit_inventory_crosscheck" and r["success"]
        for r in result.evidence
    )



def test_fault_first_prioritises_live_push_error_over_performance_only() -> None:
    snapshot = _snapshot()
    snapshot["issues"].append({
        "severity": "warning",
        "title": "SenseCap D1 Settings",
        "detail": (
            "app|4129|SenseCap D1 Settings|SenseCap D1 live push failed "
            "(HTTP 408). Live updates are suspended; retry with backoff."
        ),
    })
    targets = _fault_first_log_targets(snapshot, _performance())
    assert [(t["kind"], t["id"]) for t in targets] == [
        ("app", "4129"), ("app", "9001"), ("device", "7001"),
    ]
    assert targets[0]["selection"] == "observed fault"
    assert all(t["id"].isdecimal() for t in targets)


def test_fault_first_deduplicates_and_skips_name_only_automations() -> None:
    snapshot = _snapshot()
    snapshot["issues"].extend([
        {
            "severity": "warning",
            "title": "Automation broken: Test",
            "detail": "Hubitat marked the automation name *BROKEN*. app|9000|Fake Rule|",
        },
        {
            "severity": "warning",
            "title": "A failure",
            "detail": "app|9001|SenseCap D1 Settings|failed HTTP 408",
        },
    ])
    targets = _fault_first_log_targets(snapshot, _performance())
    assert [t["id"] for t in targets] == ["9001", "7001"]
    assert "9000" not in [t["id"] for t in targets]


def test_fault_followup_executes_even_if_performance_stats_unavailable() -> None:
    class D1Audit:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["logs"]["entries_checked"] = 2
            snapshot["issues"].append({
                "severity": "warning",
                "title": "SenseCap D1 Settings",
                "detail": "app|4129|SenseCap D1 Settings|HTTP 408 live push failed",
            })
            return snapshot

    mcp = _FakeMCP(performance_ok=False)
    result = asyncio.run(run_comprehensive_chat_audit(D1Audit(), mcp))
    assert len(mcp.calls) == 2
    assert mcp.calls[-1][1]["args"]["args"]["appId"] == "4129"
    assert "Scoped investigation target: app SenseCap D1 Settings (ID 4129)" in result.message
    assert "SenseCap D1 live push" in result.message
    assert all(e["mutates"] is False for e in result.evidence)


def test_history_zero_rows_cannot_verify_time_window() -> None:
    start = datetime(2026, 10, 7, 13, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 7, tzinfo=timezone.utc)
    verdict = _bounded_log_window_evidence([], start=start, end=end)
    assert verdict["entries_checked"] == 0
    assert verdict["window_supported_by_rows"] is False
    snapshot = _snapshot()
    report = render_comprehensive_system_audit(
        snapshot, _performance(), historical_logs=verdict
    )
    assert "Historical window unverified" in report
    assert "server retention or support for the requested time filters" in report


def test_historical_timestamps_validate_membership_not_completeness() -> None:
    start = datetime(2026, 10, 7, 13, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 7, tzinfo=timezone.utc)
    inside = {"timestamp": "2026-10-07T15:00:00Z", "level": "ERROR", "message": "failure"}
    outside = {"timestamp": "2026-10-08T08:00:00Z", "level": "ERROR", "message": "failure"}
    valid = _bounded_log_window_evidence([inside], start=start, end=end)
    assert valid["window_supported_by_rows"] is True
    assert valid["observed_earliest"] == "2026-10-07T15:00:00+00:00"
    mixed = _bounded_log_window_evidence([inside, outside], start=start, end=end)
    assert mixed["window_supported_by_rows"] is False
    assert mixed["rows_in_requested_window"] == 1
    assert _bounded_log_window_evidence(
        [inside, {"level": "ERROR", "message": "undated"}], start=start, end=end
    )["window_supported_by_rows"] is False


def test_validation_error_lists_known_tool_but_not_unknown_requester() -> None:
    snapshot = _snapshot()
    group = {
        "level": "error", "count": 1,
        "message": (
            "Validation error in hub_list_devices: attributeNames applies only "
            "to format='context' (got format='summary')"
        ),
    }
    rendered = render_comprehensive_system_audit(
        snapshot, _performance(), targeted_logs=[{
            "kind": "app", "id": "4151", "name": "MCP Rule Server",
            "selection": "observed fault", "matching_rows": 1, "groups": [group],
        }]
    )
    assert "MCP device-list validation" in rendered
    assert "original requesting caller" in rendered
    assert "correct the caller's projection" in rendered


def test_unmatched_performance_devices_display_ids() -> None:
    snapshot = _snapshot()
    snapshot["sections"]["devices"]["inventory_ids"] = ["1001"]
    report = render_comprehensive_system_audit(
        snapshot, _performance(),
        context_reconciliation={"complete": True, "found": [], "absent": ["LG webOS TV"]},
    )
    assert "LG webOS TV (ID 7001)" in report
    assert "remain hypotheses" in report



def test_structured_offline_ids_are_selected_before_performance() -> None:
    snapshot = _snapshot()
    snapshot["sections"]["devices"]["offline"] = [
        {"id": "1234", "label": "Livingroom TRV", "state": "offline",
         "source_attribute": "healthStatus", "battery": None},
        {"id": "5678", "label": "Tuya Remote (bedroom 3)",
         "state": "offline", "source_attribute": "connectionStatus"},
    ]
    targets = _fault_first_log_targets(snapshot, _performance())
    assert [t["id"] for t in targets] == ["1234", "5678", "9001", "7001"]
    assert targets[0]["selection"] == "explicit offline state"
    assert targets[1]["selection"] == "explicit offline state"
    message = render_comprehensive_system_audit(snapshot, _performance())
    assert "Livingroom TRV (ID 1234)" in message
    assert "source=healthStatus, battery=not supplied" in message
    assert "Tuya Remote (bedroom 3) (ID 5678)" in message


def test_offline_identity_not_invented_from_name_only_alert() -> None:
    snapshot = _snapshot()
    snapshot["issues"].append({
        "severity": "warning",
        "title": "Device unavailable: Mystery Contact",
        "detail": "offline",
    })
    targets = _fault_first_log_targets(snapshot, None)
    assert targets == []


def test_previous_live_push_error_receives_a_read_only_followup() -> None:
    snapshot = _snapshot()
    snapshot["sections"]["devices"]["offline"] = [{
        "id": "1234", "label": "Livingroom TRV", "state": "offline",
    }]
    previous = {"issues": [{
        "severity": "warning",
        "title": "SenseCap D1 Settings",
        "detail": "app|4129|SenseCap D1 Settings|live push failed (HTTP 408)",
    }]}
    targets = _fault_first_log_targets(snapshot, _performance(), previous_snapshot=previous)
    assert [t["id"] for t in targets][:2] == ["1234", "4129"]
    assert targets[1]["selection"] == "previously observed fault"


def test_sensecap_performance_app_can_be_sampled_for_recovery_without_alert() -> None:
    snapshot = _snapshot()
    performance = _performance()
    performance["appStats"].append({
        "id": "4129", "name": "SenseCap D1 Settings",
        "pctBusy": 9, "pctTotal": 0.5, "averageMs": 200,
    })
    targets = _fault_first_log_targets(snapshot, performance)
    assert any(t["id"] == "4129" and t["selection"] == "live-push recovery check"
               for t in targets)


def test_sensecap_success_does_not_assume_continuous_recovery() -> None:
    rows = [
        {"timestamp": "2026-10-08T10:00:00Z", "level": "ERROR",
         "message": "app|4129|SenseCap D1 Settings|live push failed HTTP 408"},
        {"timestamp": "2026-10-08T10:15:00Z", "level": "INFO",
         "message": "app|4129|SenseCap D1 Settings|live push succeeded"},
    ]
    evidence = _live_push_log_evidence(rows)
    assert evidence["failure_rows"] == 1
    assert evidence["success_rows"] == 1
    assert evidence["later_success_observed"] is True
    report = render_comprehensive_system_audit(_snapshot(), _performance(),
        targeted_logs=[{
            "kind": "app", "id": "4129", "name": "SenseCap D1 Settings",
            "matching_rows": 2, "groups": [], "live_push_evidence": evidence,
        }])
    assert "observed recovery event, not guaranteed ongoing operation" in report
    no_recovery = _live_push_log_evidence(rows[:1])
    assert no_recovery["later_success_observed"] is False


def test_undated_sensecap_success_does_not_verify_after_failure() -> None:
    evidence = _live_push_log_evidence([{
        "level": "INFO", "message": "SenseCap D1 live push succeeded"
    }])
    assert evidence["success_rows"] == 1
    assert evidence["later_success_observed"] is False


def test_end_to_end_offline_log_reads_use_actual_ids_and_remain_read_only() -> None:
    class OfflineAudit:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["logs"]["entries_checked"] = 10
            snapshot["sections"]["devices"]["offline"] = [
                {"id": "1234", "label": "Livingroom TRV", "state": "offline"},
                {"id": "5678", "label": "Tuya Remote (bedroom 3)", "state": "offline"},
            ]
            return snapshot
    mcp = _FakeMCP()
    result = asyncio.run(run_comprehensive_chat_audit(OfflineAudit(), mcp))
    scoped = [args["args"]["args"] for _, args in mcp.calls
              if args["args"]["tool"] == "hub_get_logs"]
    assert scoped[0]["deviceId"] == "1234"
    assert scoped[1]["deviceId"] == "5678"
    assert len(scoped) <= 4
    assert all(item["mutates"] is False and item["effect"] == "read"
               for item in result.evidence)



def test_active_offline_path_preserves_health_source_battery_and_last_seen() -> None:
    inventory = [{
        "id": "4718", "label": "Livingroom TRV",
        "healthStatus": "offline", "battery": 54,
        "lastActivity": "2026-10-07T19:00:00Z",
    }, {
        "id": "3483", "label": "Tuya Remote (bedroom 3)",
        "connected": False,
    }]
    section, issues = _device_findings(inventory, low_battery_threshold=20)
    offline = {row["id"]: row for row in section["offline"]}
    assert offline["4718"]["source_attribute"] == "healthStatus"
    assert offline["4718"]["battery"] == 54
    assert offline["4718"]["last_activity"] == "2026-10-07T19:00:00+00:00"
    assert offline["4718"]["reachability_independently_verified"] is False
    assert offline["3483"]["source_attribute"] == "connected"
    assert offline["3483"]["battery"] is None
    assert offline["3483"]["last_activity"] is None
    assert section["offline_count"] == 2
    assert len([r for r in issues if r["category"] == "device-offline"]) == 2


def test_scoped_warning_patterns_count_log_rows_not_outages() -> None:
    targeted = [{
        "kind": "app", "id": "4129", "name": "SenseCap D1 Settings",
        "groups": [
            {
                "level": "warning", "count": 17,
                "fingerprint": "sensecap-live-push-failed",
                "summary": "SenseCap live push failed (HTTP 408)",
                "first_seen": "2026-10-08T09:00:00+00:00",
                "last_seen": "2026-10-08T13:00:00+00:00",
            },
            {
                "level": "warning", "count": 5,
                "fingerprint": "sensecap-config-push-failed",
                "summary": "SenseCap config push failed (No route to host)",
            },
        ],
    }, {
        "kind": "app", "id": "4151", "name": "MCP Rule Server",
        "groups": [{"level": "warning", "count": 2,
                    "fingerprint": "relay-slow-logs", "summary": "Slow internal GET /logs/json"}],
    }]
    summary = _scoped_log_pattern_summary(targeted)
    assert summary["pattern_count"] == 3
    assert summary["rows"] == 24
    report = render_comprehensive_system_audit(_snapshot(), _performance(), targeted_logs=targeted)
    assert "Scoped diagnostics: 3 warning/error patterns across 24 matched log rows" in report
    assert "log rows are not separate outages" in report
    assert "17 matching log rows" in report
    assert "observed 2026-10-08T09:00:00+00:00" in report
    assert "event timestamps unavailable" in report


def test_scoped_summary_deduplicates_identical_target_and_group() -> None:
    group = {"level": "warning", "count": 4,
             "fingerprint": "same", "summary": "Recurring failure"}
    target = {"kind": "app", "id": "4129", "name": "SenseCap D1 Settings",
              "groups": [group]}
    assert _scoped_log_pattern_summary([target, target])["rows"] == 4


def test_sensecap_live_and_config_errors_are_distinct_with_no_auto_repair_claim() -> None:
    rows = [{
        "level": "WARN", "message": (
            "app|4129|SenseCap D1 Settings|SenseCap D1 live push failed (HTTP 408)"
        ),
    }, {
        "level": "WARN", "message": (
            "app|4129|SenseCap D1 Settings|SenseCap D1 config push failed (No route to host)"
        ),
    }]
    observed = _live_push_log_evidence(rows)
    assert observed["failure_rows"] == 1
    assert observed["config_failure_rows"] == 1
    assert not observed["later_success_observed"]
    report = render_comprehensive_system_audit(
        _snapshot(), _performance(), targeted_logs=[{
            "kind": "app", "id": "4129", "name": "SenseCap D1 Settings",
            "matching_rows": 2, "groups": [],
            "live_push_evidence": observed,
        }],
    )
    assert "1 live-push failure rows, 1 configuration-push failure rows" in report
    assert "do not establish causality" in report
    assert "recovery remains unverified" in report


def test_busy_audit_skips_redundant_older_log_request_without_coverage_claim() -> None:
    class BusyAudit:
        async def run(self, *, reason):
            snapshot = _snapshot()
            snapshot["sections"]["devices"]["offline"] = [
                {"id": "4718", "label": "Livingroom TRV", "state": "offline"},
                {"id": "3483", "label": "Tuya Remote (bedroom 3)", "state": "offline"},
            ]
            snapshot["issues"].append({
                "severity": "warning", "title": "SenseCap D1 Settings",
                "detail": "app|4129|SenseCap D1 Settings|live push failed HTTP 408",
            })
            return snapshot
    mcp = _FakeMCP()
    result = asyncio.run(run_comprehensive_chat_audit(BusyAudit(), mcp))
    assert [item[1]["args"]["tool"] for item in mcp.calls].count("hub_get_logs") == 4
    assert "Historical read skipped:" in result.message
    assert "Earlier errors remain unverified" in result.message
    assert not any(r.get("evidence_kind") == "chat_audit_historical_logs"
                   for r in result.evidence)
    assert all(r.get("mutates") is False for r in result.evidence)



def test_timezone_naive_and_future_log_times_never_assert_utc_chronology() -> None:
    from frozen_core import health_audit_service_core as core
    rows = [
        {"timestamp": "2026-10-08 15:00:58", "level": "WARN",
         "message": "app|4129|SenseCap D1 Settings|live push failed"},
        {"timestamp": "2026-10-08T15:00:58+00:00", "level": "WARN",
         "message": "app|4129|SenseCap D1 Settings|live push failed"},
        {"timestamp": "2026-10-08T13:59:00Z", "level": "WARN",
         "message": "app|4129|SenseCap D1 Settings|live push failed"},
        {"level": "INFO", "message": "app|4129|SenseCap D1 Settings|no date"},
    ]
    safe, quality = _audit_log_time_quality(
        rows, checked_at="2026-10-08T14:02:08Z",
    )
    assert quality["ambiguous_timezone_rows"] == 1
    assert quality["future_timestamp_rows"] == 1
    assert quality["undated_rows"] == 1
    assert quality["chronology_withheld_rows"] == 3
    assert core._log_timestamp(safe[0]) is None
    assert core._log_timestamp(safe[1]) is None
    assert core._log_timestamp(safe[2]).isoformat() == "2026-10-08T13:59:00+00:00"
    assert core._log_timestamp(rows[0]) is None
    assert rows[0]["timestamp"] == "2026-10-08 15:00:58"
    findings, _ = _log_findings(safe)
    assert findings["warning_groups"][0]["last_seen"] == "2026-10-08T13:59:00+00:00"


def test_future_logged_success_does_not_invent_sensecap_recovery() -> None:
    rows = [
        {"timestamp": "2026-10-08T13:53:00+00:00", "level": "WARN",
         "message": "app|4129|SenseCap D1 Settings|live push failed (HTTP 408)"},
        {"timestamp": "2026-10-08T15:02:00+00:00", "level": "INFO",
         "message": "app|4129|SenseCap D1 Settings|live push succeeded"},
    ]
    safe, quality = _audit_log_time_quality(rows, checked_at="2026-10-08T14:02:08Z")
    assert quality["future_timestamp_rows"] == 1
    evidence = _live_push_log_evidence(safe)
    assert evidence["success_rows"] == 1
    assert evidence["later_success_observed"] is False
    assert evidence["latest_success"] is None


def test_no_automatic_bst_offset_is_applied_to_naive_source_times() -> None:
    rows = [{"date": "2026-10-08 15:01:00",
             "message": "app|4129|SenseCap D1 Settings|live push failed",
             "level": "WARN"}]
    safe, details = _audit_log_time_quality(
        rows, checked_at="2026-10-08T14:02:08+00:00"
    )
    assert details["ambiguous_timezone_rows"] == 1
    assert safe[0]["date"] is None
    assert details["raw_examples"] == ["2026-10-08 15:01:00"]


def test_unchanged_offline_devices_yield_to_new_adb_and_metering_alerts() -> None:
    snapshot = _snapshot()
    snapshot["sections"]["devices"]["offline"] = [
        {"id": "4718", "label": "Livingroom TRV", "state": "offline"},
        {"id": "3483", "label": "Tuya Remote (bedroom 3)", "state": "offline"},
    ]
    snapshot["sections"]["devices"]["inventory_labels"] = [
        {"id": "5300", "label": "Google TV Streamer (ADB)"},
        {"id": "5313", "label": "Dehumidifier 1"},
    ]
    snapshot["issues"].extend([
        {"severity": "warning", "title": "Dehumidifier 1",
         "detail": "dev|5313|Dehumidifier 1|zigbee METERING_CLUSTER command 0x00 error: 0x84"},
        {"severity": "warning", "title": "Google TV Streamer (ADB)",
         "detail": "ADB shell connection timed out"},
        {"severity": "warning", "title": "SenseCap D1 Settings",
         "detail": "app|4129|SenseCap D1 Settings|config push failed"},
    ])
    previous = {"sections": {"devices": {"offline": [
        {"id": "4718", "state": "offline"},
        {"id": "3483", "state": "offline"},
    ]}}}
    targets = _fault_first_log_targets(snapshot, _performance(), previous_snapshot=previous)
    identifiers = [t["id"] for t in targets]
    assert identifiers[:3] == ["5313", "5300", "4129"]
    assert len(targets) == 4
    assert len(set(identifiers).intersection({"4718", "3483"})) == 1
    assert targets[-1]["selection"] == "unchanged offline sample"


def test_ambiguous_name_mapping_never_guesses_device_id() -> None:
    snapshot = _snapshot()
    snapshot["sections"]["devices"]["inventory_labels"] = [
        {"id": "8101", "label": "Google TV Streamer (ADB)"},
        {"id": "8102", "label": "Google TV Streamer (ADB)"},
    ]
    snapshot["issues"].append({
        "severity": "warning", "title": "Google TV Streamer (ADB)",
        "detail": "ADB shell connection timed out",
    })
    assert _fault_first_log_targets(snapshot, None) == []


def test_scoped_footnote_flags_unverified_timestamp_rows() -> None:
    report = render_comprehensive_system_audit(
        _snapshot(), _performance(), targeted_logs=[{
            "kind": "app", "id": "4129", "name": "SenseCap D1 Settings",
            "selection": "observed fault",
            "groups": [{"level": "warning", "count": 3, "summary": "Timed out"}],
            "time_quality": {
                "ambiguous_timezone_rows": 1, "future_timestamp_rows": 2,
                "undated_rows": 0, "chronology_withheld_rows": 3,
                "raw_examples": ["2026-10-08T15:00:00+00:00"],
            },
        }],
    )
    assert "Timestamp integrity: 1 timezone-ambiguous, 2 apparently future" in report
    assert "Example unverified source time(s)" in report
    assert "do not infer BST/UTC offsets" in report


def test_dehumidifier_command_response_is_not_diagnosed_as_failed_meter_reading() -> None:
    report = render_comprehensive_system_audit(
        _snapshot(), _performance(), targeted_logs=[{
            "kind": "device", "id": "5313", "name": "Dehumidifier 1",
            "groups": [{
                "level": "warning", "count": 3,
                "message": "dev|5313|Dehumidifier 1|zigbee METERING_CLUSTER command 0x00 error: 0x84",
            }],
        }],
    )
    assert "effect on current meter readings are not established" in report



def test_slow_logs_json_duration_changes_group_into_one_pattern() -> None:
    from frozen_core.health_audit_service_core import _log_findings
    rows = [
        {"level": "warning", "message": (
            "[hubrt] slow internal GET /logs/json took 10061ms (ok), "
            "at or over the 8000ms cloud-relay budget"
        )},
        {"level": "warning", "message": (
            "[hubrt] slow internal GET /logs/json took 8268ms (ok), "
            "at or over the 8000ms cloud-relay budget"
        )},
        {"level": "warning", "message": (
            "[hubrt] slow internal GET /logs/json took 8608ms (ok), "
            "at or over the 8000ms cloud-relay budget"
        )},
    ]
    findings, _ = _log_findings(rows)
    warnings = findings["warning_groups"]
    assert len(warnings) == 1
    assert warnings[0]["count"] == 3
    assert warnings[0]["duration_min_ms"] == 8268
    assert warnings[0]["duration_max_ms"] == 10061
    message = render_comprehensive_system_audit(
        _snapshot(), _performance(), targeted_logs=[{
            "kind": "app", "id": "4151", "name": "MCP Rule Server",
            "groups": warnings,
        }]
    )
    assert "1 warning/error patterns across 3 matched log rows" in message
    assert "8268–10061 ms" in message


def test_intentionally_unpowered_sensecap_is_user_context_not_mcp_proof() -> None:
    snapshot = _snapshot()
    snapshot["issues"].append({
        "severity": "warning", "title": "SenseCap D1 Settings",
        "detail": "app|4129|SenseCap D1 Settings|live push failed HTTP 408",
    })
    performance = _performance()
    performance["appStats"].append({
        "id": "4129", "name": "SenseCap D1 Settings",
        "pctBusy": 12, "pctTotal": 1, "averageMs": 44,
    })
    targets = _fault_first_log_targets(
        snapshot, performance, sensecap_known_unpowered=True,
    )
    assert all("sensecap d1" not in t["name"].casefold() for t in targets)
    rendered = render_comprehensive_system_audit(
        snapshot, performance, sensecap_known_unpowered=True,
    )
    assert "intentionally switched off (no power)" in rendered
    assert "not independently verified by MCP" in rendered
    assert "Transport failures are expected " in rendered
    assert "Re-enable power and clear that temporary option" in rendered
    assert "Check current reachability and a later successful push" not in rendered
    # The error signal itself is still visible; it is not silently discarded.
    assert "live push failed HTTP 408" in rendered


def test_sensecap_normal_fault_analysis_returns_when_unpowered_option_cleared() -> None:
    snapshot = _snapshot()
    snapshot["issues"].append({
        "severity": "warning", "title": "SenseCap D1 Settings",
        "detail": "app|4129|SenseCap D1 Settings|live push failed HTTP 408",
    })
    targets = _fault_first_log_targets(snapshot, None)
    assert any(t["id"] == "4129" for t in targets)
    report = render_comprehensive_system_audit(snapshot, None)
    assert "intentionally switched off" not in report
    assert "Check current reachability and a later successful push" in report


def test_measured_stage_timings_are_reported_without_cpu_assumptions() -> None:
    snapshot = _snapshot()
    snapshot["stage_timings_ms"] = {
        "mcp_health": 18, "tool_inventory": 24,
        "device_inventory": 5300, "automation_inventory": 8200,
        "log_snapshot": 9000, "aggregation": 9,
    }
    snapshot["elapsed_ms"] = 22700
    report = render_comprehensive_system_audit(snapshot, _performance())
    assert "Measured System Check stage timings" in report
    assert "Device inventory and classification: 5300 ms" in report
    assert "Automation inventory: 8200 ms" in report
    assert "Initial log sample: 9000 ms" in report
    assert "System Check total: 22700 ms" in report
    assert "not hub CPU usage" in report


def test_optional_model_analysis_is_tool_free_advisory_and_non_mutating() -> None:
    observed = []
    async def fake_chat(messages, tools):
        observed.append((messages, tools))
        return {"content": "Hypothesis: Check whether the socket still has power."}
    audit = _FakeAudit()
    mcp = _FakeMCP()
    result = asyncio.run(run_comprehensive_chat_audit(
        audit, mcp, analysis_chat=fake_chat,
    ))
    assert len(observed) == 1
    assert observed[0][1] == []
    assert "Optional AI diagnostic hypotheses — unverified" in result.message
    assert "Hypothesis: Check whether the socket still has power" in result.message
    assert any(e.get("evidence_kind") == "non_authoritative_model_hypotheses"
               and e["mutates"] is False and not e["supports_live_claim"]
               for e in result.evidence)


def test_ai_timeout_or_error_does_not_break_deterministic_system_audit() -> None:
    async def bad_chat(messages, tools):
        raise RuntimeError("model unavailable")
    result = asyncio.run(run_comprehensive_chat_audit(
        _FakeAudit(), _FakeMCP(), analysis_chat=bad_chat,
    ))
    assert "Comprehensive Hubitat audit" in result.message
    assert any(e.get("evidence_kind") == "non_authoritative_model_hypotheses"
               and e["success"] is False for e in result.evidence)



def test_system_check_records_fresh_device_acquisition_and_local_classification(tmp_path):
    from frozen_core.health_audit_service_core import HealthAuditService
    from types import SimpleNamespace

    class AuditMCP:
        async def health(self):
            return {"online": True}
        async def list_tools(self, refresh=False):
            return []
        async def get_audit_devices(self):
            return [{
                "id": "4718", "label": "Livingroom TRV",
                "attributes": [{"name": "healthStatus", "currentValue": "offline"}],
                "capabilities": ["Battery"],
                "lastActivity": "2026-10-08T11:01:04Z",
            }], {
                "source": "fresh_projected_gateway",
                "mode": "one_page", "pages": 1,
                "devices": 1, "complete": True, "read_elapsed_ms": 15,
            }
        async def get_cached_devices(self, refresh=False):
            raise AssertionError("audit should request fresh lean projection first")

    class AutomationSource:
        async def snapshot(self, advisory=False):
            return SimpleNamespace(automation_counts={}, automation_items=[])

    service = HealthAuditService(
        AuditMCP(), AutomationSource(),
        snapshot_path=tmp_path / "audit.json",
        now_factory=lambda: datetime(2026, 10, 8, 14, tzinfo=timezone.utc),
    )
    snapshot = asyncio.run(service.run(reason="chat"))
    timings = snapshot["stage_timings_ms"]
    assert "device_acquisition" in timings
    assert "device_classification" in timings
    assert timings["device_inventory"] >= timings["device_acquisition"]
    assert snapshot["sections"]["devices"]["offline_count"] == 1
    assert snapshot["sections"]["devices"]["read_provenance"]["complete"] is True
    report = render_comprehensive_system_audit(snapshot, None)
    assert "Fresh device data acquisition" in report
    assert "Local device classification" in report
    assert "Device evidence source: fresh_projected_gateway" in report
    assert "fresh projection verified=True" in report



def test_optional_ai_commentary_cuts_at_complete_markdown_boundary() -> None:
    from health_audit_service import _complete_ai_advisory
    long_text = (
        "**Investigation**\n\n"
        "1. **Observed Google TV timeouts**\n"
        "* Evidence: 7 warning rows. Consider connection health.\n\n"
        "2. **SenseCap D1**\n"
        "* Evidence: 49 timeouts and 24 unreachable rows. Check configuration.\n\n"
        "3. **MCP Rule Server tooling errors**\n"
        "* **Evidence:** " + "Details from a further log message. " * 90
    )
    result = _complete_ai_advisory(long_text, max_chars=370)
    assert result.endswith("*(Further AI commentary omitted; audit evidence above is complete.)*")
    assert "3. **MCP Rule Server tooling errors**" not in result
    assert result.count("**") % 2 == 0
    assert "1. **Observed Google TV timeouts**" in result


def test_intentionally_unpowered_sensecap_is_explicit_in_ai_input() -> None:
    observed = []

    async def fake_chat(messages, tools):
        observed.append((messages, tools))
        return {"content": "Known expected outage; no network repair warranted while powered off."}

    audit = _FakeAudit()
    audit.sensecap_d1_intentionally_powered_off = True
    result = asyncio.run(run_comprehensive_chat_audit(
        audit, _FakeMCP(), analysis_chat=fake_chat,
        analysis_focus="which automations are failing?",
    ))
    assert observed and observed[0][1] == []
    prompt = observed[0][0][0]["content"]
    assert "intentionally unpowered" in prompt
    assert "Treat its reachability failures as expected" in prompt
    assert "which automations are failing?" in observed[0][0][1]["content"]
    assert "Known expected outage" in result.message
