"""HomeBrain 0.17.27 archive-first historical evidence routing.

No live Hubitat connections. Prove exact focal window routing, fallback on
unverified bounds, and no promotion of archived reception timestamps to MCP.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import mcp_agent_orchestrator as orchestration
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_metrics import RequestMetrics
from historical_evidence_journal import HistoricalEvidenceJournal
from webui import render_page


FOCAL = "2026-10-12T08:18:23.830+01:00"


class Journal:
    enabled = True
    _started = True
    def __init__(self):
        self.calls = []
    def query(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "events": [{
                "stream": "events", "attribute": "motion", "value": "inactive",
                "observed_at": "2026-10-12T07:18:20.100+00:00",
                "timestamp_basis": "collector-received", "source": "DEVICE",
            }],
            "gaps": [], "coverage_complete": False,
        }


class Mconnector:
    def __init__(self, verified):
        self.verified = verified
        self.calls = []
    async def call_tool(self, name, args):
        self.calls.append((name, args))
        inner = args["args"]
        if self.verified:
            result = {
                "success": True, "deviceId": inner["deviceId"],
                "sinceMode": "explicit", "sinceTimestamp": inner["since"],
                "untilTimestamp": inner["until"],
                "events": [{"name": "motion", "value": "inactive",
                            "date": "2026-10-12T08:18:18.000+01:00"}],
            }
        else:
            result = {"success": True, "events": [], "sinceMode": "relative"}
        return SimpleNamespace(data=result, is_error=False)


class Executor:
    def __init__(self):
        self.calls = []
    async def execute(self, name, args, **kwargs):
        self.calls.append((name, args))
        if name == "homebrain_device_history":
            if args.get("name") == "Bedroom 1 FP300":
                data = {"label": "Bedroom 1 FP300", "attribute": "motion",
                        "room": "Bedroom 1", "events": [],
                        "observedEvents": []}
            else:
                data = {"label": "Bedroom 1 Light", "attribute": "switch",
                        "room": "Bedroom 1", "events": [], "observedEvents": []}
        else:
            data = {}
        return SimpleNamespace(result=SimpleNamespace(data=data))


class Evidence:
    def __init__(self):
        self.rows = []
    def record(self, *args, **kwargs):
        self.rows.append((args, kwargs))
    def receipts(self):
        return []


class Catalog:
    def declared_tool(self, name):
        return object()
    def available_tool(self, name):
        return object()


def sensor_plan(monkeypatch):
    monkeypatch.setattr(orchestration, "subject_room_filter_arguments",
                        lambda *a, **k: {"type": "room", "value": "Bedroom 1"})
    monkeypatch.setattr(orchestration, "controller_history_candidates",
                        lambda *a, **k: [])
    monkeypatch.setattr(orchestration, "trigger_sensor_history_candidates",
                        lambda *a, **k: [{
                            "name": "Bedroom 1 FP300", "attribute": "motion",
                            "candidate": {
                                "id": "7774", "label": "Bedroom 1 FP300",
                                "room": "Bedroom 1", "matchBasis": "room",
                            },
                        }])
    monkeypatch.setattr(
        orchestration, "prioritize_known_automation_sensor_candidates",
        lambda pool, *a, **k: (pool, False),
    )
    monkeypatch.setattr(orchestration, "known_automation_sensor_candidate_visibility",
                        lambda *a, **k: [])
    monkeypatch.setattr(orchestration, "rank_causal_hypotheses",
                        lambda *a, **k: [])
    monkeypatch.setattr(orchestration, "plan_cross_integration_candidates",
                        lambda *a, **k: [])


async def investigate(monkeypatch, verified, enable_journal=True):
    sensor_plan(monkeypatch)
    mcp = Mconnector(verified)
    executor = Executor()
    evidence = Evidence()
    journal = Journal() if enable_journal else None
    host = SimpleNamespace(
        mcp=mcp, executor=executor, evidence=evidence, known_automations=[],
        historical_journal=journal,
        _tool_succeeded=lambda result: not result.is_error,
    )
    subject = {
        "label": "Bedroom 1 Light", "deviceId": "7840",
        "room": "Bedroom 1", "attribute": "switch",
        "events": [], "correlationEvents": [
            {"name": "switch", "value": "off", "date": FOCAL}
        ], "temporalAnalysis": {
            "observedIntervals": [{
                "start": "2026-10-12T08:16:10.000+01:00",
                "end": FOCAL,
            }]
        },
    }
    boundary = {"stateBoundary": FOCAL, "producer": {
        "id": "7790", "label": "Matter Hue Bridge Pro",
    }}
    token = RequestMetrics().begin()
    try:
        await UnifiedMCPAgent._collect_reporting_source_secondary_correlation(
            host, subject_history=subject, transition="off",
            boundary_match=boundary, catalog=Catalog(), completed_calls=set(),
        )
    finally:
        RequestMetrics().reset(token)
    return mcp, executor, journal, evidence


@pytest.mark.asyncio
async def test_journal_first_bounded_mcp_skips_redundant_recent_sensor_page(monkeypatch):
    mcp, exe, archive, evidence = await investigate(monkeypatch, True)
    assert archive and len(archive.calls) == 1
    assert archive.calls[0]["device_id"] == "7774"
    assert len(mcp.calls) == 1
    assert mcp.calls[0][1]["args"]["since"].startswith("2026-10-12T08:13:23")
    assert mcp.calls[0][1]["args"]["until"].startswith("2026-10-12T08:20:23")
    # Subject pattern read is separate; no newest-N sensor read remains.
    assert all(args.get("name") != "Bedroom 1 FP300"
               for name, args in exe.calls if name == "homebrain_device_history")
    analysis = next(k["details"] for a, k in evidence.rows
                    if a[0] == "homebrain_causal_secondary_correlation")
    assert analysis["journalFirstPlan"]["directWindowVerified"] == 1
    assert analysis["journalFirstPlan"]["recentPageSensorFallbacks"] == 0
    assert analysis["historicalJournal"]["historicalCompletenessVerified"] is False


@pytest.mark.asyncio
async def test_unverified_absolute_window_uses_existing_recent_page_fallback(monkeypatch):
    mcp, exe, archive, evidence = await investigate(monkeypatch, False)
    assert len(mcp.calls) == 1
    assert any(args.get("name") == "Bedroom 1 FP300"
               for name, args in exe.calls if name == "homebrain_device_history")
    analysis = next(k["details"] for a, k in evidence.rows
                    if a[0] == "homebrain_causal_secondary_correlation")
    assert analysis["journalFirstPlan"]["directWindowVerified"] == 0
    assert analysis["journalFirstPlan"]["recentPageSensorFallbacks"] == 1
    assert analysis["journalFirstPlan"]["journalEmptyDoesNotProveInactivity"] is True


@pytest.mark.asyncio
async def test_disabled_journal_keeps_legacy_path(monkeypatch):
    mcp, exe, archive, evidence = await investigate(monkeypatch, False, False)
    assert not archive
    assert any(args.get("name") == "Bedroom 1 FP300"
               for name, args in exe.calls if name == "homebrain_device_history")
    assert not any("journalFirstPlan" in k.get("details", {})
                   for a, k in evidence.rows if isinstance(k.get("details"), dict))


def test_latest_persisted_event_survives_restart_even_when_receive_marker_is_empty(tmp_path):
    def opened():
        j = HistoricalEvidenceJournal(
            enabled=True, hub_url="http://192.168.1.239",
            path=tmp_path/"evidence.sqlite3",
        )
        j._initialize()
        j._started = True
        return j
    original = opened()
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    row = original._row("events", {
        "deviceId": 7840, "name": "switch", "value": "off",
        "source": "DEVICE",
    }, now, original.log_app_ids)
    original._write_batch([row])
    restarted = opened()
    assert restarted.status()["last_received"]["events"] is None
    assert restarted.status()["last_persisted_device_event"] == now
    assert "Latest saved event:" in render_page("Hubitat MCP AI", "0.17.27")
