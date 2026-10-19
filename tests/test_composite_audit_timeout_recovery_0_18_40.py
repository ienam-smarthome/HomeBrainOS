"""v0.18.40: cross-domain audits and source-only timeout recovery."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from composite_system_audit_policy import is_cross_domain_hub_audit_request
from performance_timeout_digest import render_performance_timeout_digest
from performance_api_finalizer import finalize_performance_api_outcome
import performance_api_finalizer as finalizer


MULTIDOMAIN = (
    "Review all devices, hub rules, apps, automations and all logs/events and "
    "suggest how to optimize and make the hub more efficient"
)


@pytest.mark.parametrize("question,expected", [
    (MULTIDOMAIN, True),
    ("Audit the entire hub including health, app failures, offline devices, "
     "Rule Machine, scheduled jobs and warning logs.", True),
    ("Check my Hubitat apps, drivers, errors, warnings, scheduled jobs, "
     "devices and rules and list repair priorities. Read-only.", True),
    ("Analyse all scheduled jobs, group by handler and reduce unnecessary work.", False),
    ("Review my hub performance and reduce overhead, read-only.", False),
    ("Why did Bedroom 3 Mesh turn OFF at 01:30 BST on 12 October 2026?", False),
    ("Diagnose offline Livingroom TRV only.", False),
    ("Turn off all devices and apps.", False),
    ("Review Hubitat logs for yesterday.", False),
])
def test_cross_domain_routing_boundary(question, expected):
    assert is_cross_domain_hub_audit_request(question) is expected


def sample_evidence():
    return [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_metrics",
         "success": True, "effect": "read", "mutates": False},
        {"tool": "hub_manage_logs", "sub_tool": "hub_get_performance_stats",
         "success": True, "effect": "read", "mutates": False},
        {"tool": "hub_manage_logs", "sub_tool": "hub_get_jobs",
         "success": True, "effect": "read", "mutates": False},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
         "success": True, "effect": "read", "mutates": False,
         "details": {"logs": [
             {"level": "WARN", "message": "dev|7103|Bedroom 3 Mesh|Watchdog fired after 172202s"},
             {"level": "WARN", "message": "dev|7103|Bedroom 3 Mesh|Watchdog fired after 171900s"},
             {"level": "ERROR", "message": "dev|7675|OpenWeatherMap Multi-API|API read timed out at https://private.example/api?token=SECRET"},
             {"level": "INFO", "message": "app|4129|SenseCap D1 Settings|Routine activity"},
         ]}},
    ]


def data_packet():
    return {
        "hub_get_metrics": json.dumps({
            "result": {"current": {
                "freeMemoryMB": 800.91, "temperatureC": 41.8,
                "databaseSizeMB": 129, "healthAlerts": [],
            }}
        }),
        "hub_get_performance_stats": json.dumps({
            "result": {"appStats": [
                {"name": "SenseCap D1 Settings", "pctBusy": 21.0,
                 "pctTotal": 2.825, "averageMs": 201.1},
                {"name": "MCP Rule Server", "pctBusy": 9, "pctTotal": 1.215},
            ], "deviceStats": []}
        }),
        "hub_get_jobs": (
            'HOST_JOB_DIGEST:{"status":"parsed","reportedJobs":273,'
            '"rowsExamined":273}'
        ),
        "hub_get_logs": '{"result":{"logs":[]}}',
    }


def test_deterministic_timeout_digest_has_facts_and_inspection_not_model_draft():
    text = render_performance_timeout_digest(
        captured=data_packet(),
        evidence=sample_evidence(),
        job_digest={"status": "parsed", "reportedJobs": 273, "rowsExamined": 273},
        timeout_seconds=30,
    )
    for token in (
        "800.91 MB", "41.8 °C", "129 MB", "2.83%",
        "SenseCap D1 Settings", "273 reported jobs",
        "Bedroom 3 Mesh", "OpenWeatherMap Multi-API",
        "verified partial report", "not a completed whole-hub diagnosis",
        "before retiring or changing schedules",
    ):
        assert token in text
    assert "SECRET" not in text
    assert "private.example" not in text
    assert "Turn off" not in text
    assert "repair completed" not in text


def test_missing_and_failed_sources_do_not_leak_nonexistent_metrics_or_claim_complete():
    rows = sample_evidence()
    rows[0]["success"] = False
    rows[2]["success"] = False
    msg = render_performance_timeout_digest(
        captured=data_packet(), evidence=rows, job_digest={"reportedJobs": 273},
    )
    assert "800.91 MB" not in msg
    assert "273 reported jobs" not in msg
    assert "not a completed" in msg
    assert "hub_get_logs" in msg


@pytest.mark.asyncio
async def test_finalizer_timeout_uses_verified_packet_without_second_ai_call(monkeypatch):
    packet = data_packet()
    monkeypatch.setattr(finalizer, "_consume_packet", lambda: list(packet.items()))
    called = []
    async def fail_synthesis(self, messages):
        called.append("synthesis")
        raise asyncio.TimeoutError
    monkeypatch.setattr(finalizer.FinalAnswerCoordinator, "answer", fail_synthesis)
    async def no_mcp(*args, **kwargs):
        raise AssertionError("The successful source packet must be reused.")
    mcp = SimpleNamespace(call_tool=no_mcp)
    agent = SimpleNamespace(performance_synthesis_timeout_seconds=30)
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="DRAFT: disabling apps saves 60% CPU.",
        evidence=sample_evidence(), metrics={"counters": {}, "timings_ms": {}},
        choices=[], confirmation_required=False,
    )
    result = await finalize_performance_api_outcome(
        agent, mcp, outcome, MULTIDOMAIN,
    )
    assert called == ["synthesis"]
    assert result.route == "investigation-timeout"
    assert "DRAFT" not in result.message
    assert "800.91 MB" in result.message
    assert "273 reported jobs" in result.message
    assert "SenseCap D1 Settings" in result.message
    assert len(result.evidence) == len(sample_evidence())
    assert result.confirmation_required is False
    assert result.metrics["counters"]["performance_api_synthesis_timeout"] == 1
    assert result.metrics["counters"]["performance_api_timeout_evidence_digest"] == 1
