"""Regression: v0.18.79 completed an audit but silently skipped AI reasoning
and prioritised offline status above explicit Hubitat excess-load exceptions.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit_priority_planner import render_audit_priorities
from health_audit_service import render_comprehensive_system_audit, run_comprehensive_chat_audit
from api_response_builder import build_agent_response
from mcp_client import MCPTool, MCPToolResult


def snapshot():
    return {
        "checked_at": "2026-10-23T21:01:31+00:00",
        "status": "attention",
        "issues": [],
        "sections": {
            "devices": {
                "offline": [{"id": "7103", "label": "Bedroom 3 Mesh"},
                            {"id": "3483", "label": "Tuya Remote"}],
                "offline_count": 2,
                "low_battery_count": 0,
                "total": 204,
                "no_recent_activity": [],
            },
            "automations": {"total": 160},
            "logs": {"entries_checked": 200, "checked_hours": 24},
        },
    }


def error_row(device_id, label, app_id, count, message):
    return {
        "kind": "device", "id": str(device_id), "name": label,
        "matching_rows": count,
        "groups": [{
            "level": "error",
            "count": count,
            "summary": "dev|" + str(device_id) + "|" + label
                       + "|App " + str(app_id) + " " + message,
        }],
    }


def logged_load_errors():
    return [
        error_row(7182, "Device Status Report Display", 3977, 15,
                  "generates excessive hub load on line 64 (method setReportData)"),
        error_row(7167, "Life360 member A", 4061, 61,
                  "generates excessive hub load on line 420 (method updateMember)"),
        error_row(7168, "Life360 member B", 4061, 61,
                  "generates excessive hub load on line 420 (method updateMember)"),
        error_row(5864, "Octopus Live Meter", 3933, 120,
                  "generates excessive hub load (telemetry update)"),
    ]


def test_explicit_hub_load_errors_are_prioritised_and_grouped_by_app():
    p = render_audit_priorities(snapshot(), logged_load_errors())
    assert p.index("app 3933") < p.index("app 4061") < p.index("app 3977")
    assert p.index("app 3977") < p.index("offline")
    assert p.count("app 4061") == 1
    assert "not independent failures" in p
    assert "Before" not in p
    assert "Check power" in p
    assert "Next read-only check" in p


def test_generic_errors_without_explicit_app_load_do_not_become_limit_exceeded():
    p = render_audit_priorities(
        snapshot(), [error_row(5864, "Meter", 3933, 4, "responded slowly")]
    )
    assert "explicit excessive-hub-load" not in p
    assert "offline" in p


def test_pcttotal_gt_one_hundred_is_reported_with_unknown_denominator():
    p = render_comprehensive_system_audit(
        snapshot(),
        {"appStats": [{
            "id": "4216", "name": "00 Energy Usage",
            "pctTotal": 109.418, "pctBusy": 15.5, "averageMs": 6849.2,
        }], "deviceStats": []},
    )
    assert "pctTotal=109.418%" in p
    assert "Unverified percentage denominator" in p
    assert "not percentage of whole-hub CPU" in p


class FakeAudit:
    sensecap_d1_intentionally_powered_off = False

    async def run(self, *, reason):
        return snapshot()


class FakeMCP:
    async def list_tools(self):
        return []

    async def call_tool(self, *args, **kwargs):
        raise AssertionError("No gateway available")


def test_saved_opt_out_is_visible_as_an_explicit_model_status():
    result = asyncio.run(run_comprehensive_chat_audit(
        FakeAudit(), FakeMCP(), ai_disabled_by_configuration=True,
    ))
    assert result.ai_analysis_status == "disabled_by_configuration"
    assert "comprehensive_audit_ai_analysis_enabled=false" in result.message
    assert not any(e.get("tool") == "optional_ai_advisory" for e in result.evidence)
    api = build_agent_response(result, model="gemma4:31b",
                               elapsed_ms=30, version="0.18.80")
    assert api["model"] is None
    assert api["ai_analysis"] == {
        "status": "disabled_by_configuration",
        "read_only": True, "tool_calls_allowed": False,
    }


def test_successful_no_tools_model_response_has_completion_status():
    calls = []

    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"content": (
            "Explicit load exceptions are confirmed in the log sample; "
            "compare actual app execution cadence before changing settings."
        )}

    result = asyncio.run(run_comprehensive_chat_audit(
        FakeAudit(), FakeMCP(), analysis_chat=chat,
        analysis_focus="Why is my hub busy?",
    ))
    assert result.ai_analysis_status == "completed"
    assert "Reasoned answer" in result.message
    assert len(calls) == 1 and calls[0][1] == []
    assert any(e.get("tool") == "optional_ai_advisory"
               and e.get("success") is True for e in result.evidence)


def test_no_tools_failure_preserves_deterministic_audit_and_clearly_reports_it():
    async def failing_chat(messages, tools):
        raise asyncio.TimeoutError("bounded model response timed out")

    result = asyncio.run(run_comprehensive_chat_audit(
        FakeAudit(), FakeMCP(), analysis_chat=failing_chat,
    ))
    assert result.ai_analysis_status == "timed_out"
    assert "did not complete (time limit reached)" in result.message
    assert "Comprehensive Hubitat audit" in result.message
    assert any(e.get("tool") == "optional_ai_advisory"
               and e.get("success") is False for e in result.evidence)


def test_empty_model_reply_is_not_called_a_successful_reasoned_answer():
    async def no_answer(messages, tools):
        return {"content": ""}

    result = asyncio.run(run_comprehensive_chat_audit(
        FakeAudit(), FakeMCP(), analysis_chat=no_answer,
    ))
    assert result.ai_analysis_status == "empty_response"
    assert "did not complete (empty reply)" in result.message
    assert "Reasoned answer" not in result.message
