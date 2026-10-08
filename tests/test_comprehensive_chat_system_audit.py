from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from health_audit_service import (  # noqa: E402
    is_comprehensive_system_audit_request,
    render_comprehensive_system_audit,
    run_comprehensive_chat_audit,
    _concise_log_message,
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
    assert mcp.calls[1][1]["args"]["args"]["deviceId"] == "7001"
    assert mcp.calls[2][1]["args"]["args"]["appId"] == "9001"
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
