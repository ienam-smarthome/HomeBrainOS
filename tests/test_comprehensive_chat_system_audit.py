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
    assert not result.confirmation_required if hasattr(result, "confirmation_required") else True
    assert result.evidence[0]["mutates"] is False
    assert len(mcp.calls) == 3
    assert [call[1]["args"]["tool"] for call in mcp.calls] == [
        "hub_get_performance_stats", "hub_get_logs", "hub_get_logs",
    ]
    assert mcp.calls[1][1]["args"]["args"]["deviceId"] == "7001"
    assert mcp.calls[2][1]["args"]["args"]["appId"] == "9001"
    assert "websocket connection retrying" in result.message
    assert "An unrelated device error" not in result.message
    assert "no devices, rules, apps or settings have been changed" in result.message


def test_audit_remains_available_when_performance_gateway_fails() -> None:
    mcp = _FakeMCP(performance_ok=False)
    result = asyncio.run(run_comprehensive_chat_audit(_FakeAudit(), mcp))
    assert len(mcp.calls) == 1
    assert "Low battery: Livingroom TRV" in result.message
    assert "Performance statistics unavailable" in result.message
    assert "No repairs performed" in result.message
