"""Regression gates for aligned external Hubitat diagnostic evidence (0.18.430)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from external_hub_diagnostics import ExternalHubDiagnostics  # noqa: E402
from webui import render_page  # noqa: E402


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds")


def _recorder(tmp_path: Path, **kwargs) -> ExternalHubDiagnostics:
    rec = ExternalHubDiagnostics(
        enabled=True,
        hub_url="http://192.168.1.239",
        path=tmp_path / "unified.sqlite3",
        probe_seconds=30,
        cpu_cores=4,
        retention_days=30,
        **kwargs,
    )
    rec._initialize()
    return rec


def test_timeline_aligns_real_memory_cpu_outage_startup_without_filling_gaps(tmp_path):
    rec = _recorder(tmp_path)
    anchor = datetime.now(timezone.utc) - timedelta(minutes=9)
    occurred = _iso(anchor + timedelta(seconds=100))
    rows = [
        # Duplicate native label: only first source sample must count as fresh.
        (0, True, 900.0, "native-A", 0.76),
        (30, True, 500.0, "native-A", 0.76),
        (60, False, None, None, None),
        (90, True, 221.0, "native-B", 2.4),
        (120, True, 890.0, "native-B", 2.4),
    ]
    for i, (sec, reachable, memory, label, cpu) in enumerate(rows):
        row = {
            "recorded_at": _iso(anchor + timedelta(seconds=sec)),
            "reachable": int(reachable),
            "free_os_mb": memory,
            "native_sample_label": label,
            "native_load5": cpu,
            "latency_ms": 32 if reachable else None,
        }
        rec._save(
            row,
            opened=row["recorded_at"] if i == 2 else None,
            recovered=i == 3,
            startups=({
                "occurred_at": occurred,
                "firmware": "2.5.3.118",
                "source": "hub_events_json_systemStart",
            },) if i == 3 else (),
        )
    with sqlite3.connect(rec.path) as db:
        before = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    data = rec.timeline(hours=24)
    assert data["hours"] == 24
    assert data["coverage"] == "partial_observations_not_proof_of_cause"
    assert data["timestamp_basis"]["reboots"] == "hub_events_json_systemStart_offset_aware"
    assert data["timestamp_basis"]["native_load_pct"] == "collector_recorded_at_with_native_sample_label"
    assert data["metrics"]["free_os_mb"]["observed_metric_points"] == 4
    assert data["metrics"]["native_load_pct"]["observed_metric_points"] == 2
    mem = data["metrics"]["free_os_mb"]["samples"]
    cpu = data["metrics"]["native_load_pct"]["samples"]
    assert len(mem) == 5  # The stored failed probe is retained but not a zero.
    assert mem[2]["reachable"] == 0 and mem[2]["free_os_mb"] is None
    assert min(p["free_os_mb"] for p in mem if p["free_os_mb"] is not None) == 221
    assert [p["native_load5"] for p in cpu if p["native_sample_label"] in ("native-A", "native-B")][:2] == [0.76, 0.76]
    assert {p["native_sample_label"] for p in cpu if p["native_sample_label"]} == {"native-A", "native-B"}
    assert {p["native_load_pct"] for p in cpu if p["native_load_pct"] is not None} == {19.0, 60.0}
    assert data["reboots"] == [{
        "occurred_at": occurred,
        "firmware": "2.5.3.118",
        "observed_at": _iso(anchor + timedelta(seconds=90)),
        "source": "hub_events_json_systemStart",
    }]
    assert len(data["incidents"]) == 1
    assert data["incidents"][0]["kind"] == "hub-unreachable"
    assert data["incidents"][0]["recovered_at"] == _iso(anchor + timedelta(seconds=90))
    with sqlite3.connect(rec.path) as db:
        assert db.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == before


def test_timeline_long_range_preserves_true_extrema_and_bounds_response(tmp_path):
    rec = _recorder(tmp_path)
    first = datetime.now(timezone.utc) - timedelta(hours=35)
    rows = []
    for i in range(3500):
        t = _iso(first + timedelta(seconds=30 * i))
        memory = 221.0 if i == 1800 else float(860 + i % 20)
        load = 2.8 if i == 1800 else float(0.8 + (i % 3) * 0.1)
        rows.append((t, 1, memory, f"source-{i // 10:04d}", load))
    with sqlite3.connect(rec.path) as db:
        db.executemany(
            "INSERT INTO samples (recorded_at,reachable,free_os_mb,native_sample_label,native_load5) "
            "VALUES (?,?,?,?,?)", rows,
        )
    result = rec.timeline(hours=72)
    mem = result["metrics"]["free_os_mb"]
    cpu = result["metrics"]["native_load_pct"]
    assert mem["source_sample_count"] == 3500
    assert mem["downsampled"] is True
    assert cpu["observed_metric_points"] == 350
    assert min(p["free_os_mb"] for p in mem["samples"]) == 221.0
    assert max(p["native_load_pct"] for p in cpu["samples"]
               if p["native_load_pct"] is not None) == 70.0
    assert len(mem["samples"]) < 3000
    assert len(cpu["samples"]) < 3000
    assert rec.timeline(hours=7200)["hours"] == 720
    assert rec.timeline(hours=-10)["hours"] == 1


def test_timeline_absent_recorder_does_not_fabricate_events(tmp_path):
    rec = _recorder(tmp_path)
    rec.enabled = False
    result = rec.timeline(hours=7)
    assert result["coverage"] == "not_recorded"
    assert not result["metrics"]["free_os_mb"]["samples"]
    assert not result["metrics"]["native_load_pct"]["samples"]
    assert result["incidents"] == [] and result["reboots"] == []


def test_timeline_route_returns_same_local_snapshot_without_hub_io(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "absent-options.json"))
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")
    rec = _recorder(tmp_path)
    monkeypatch.setattr(app_module, "external_hub_diagnostics", rec)
    expected = rec.timeline(hours=1)
    actual = asyncio.run(app_module.hub_diagnostics_timeline(hours=1))
    assert actual["hours"] == expected["hours"] == 1
    assert actual["coverage"] == expected["coverage"]
    assert actual["metrics"] == expected["metrics"]
    assert "/api/hub-diagnostics/timeline" in app_module.app.openapi()["paths"]


def test_mobile_ui_unified_timeline_keeps_existing_diagnostics_and_evidence_boundaries():
    ui = render_page("HomeBrain", "0.18.430")
    for snippet in (
        'id="diagTimelineDetails"',
        'id="diagTimelineChart"',
        'id="diagTimelineEvents"',
        'id="diagTimelineReadout"',
        'id="diagTimelineJournal"',
        'id="diagTimelineEvidence"',
        "api/hub-diagnostics/timeline?hours=",
        "function timelineSelectAt(t)",
        "function drawIncidentTimeline(data)",
        "readings are native five-minute",
        "time proximity is not proof of cause",
        'id="diagChart"',
        'id="diagReboots"',
        'id="diagIncidents"',
        'id="journalCard"',
        'id="journalDetails"',
    ):
        # Strong static regressions also cover the old detailed chart.
        assert snippet in ui, snippet
    assert 'id="oneTimeCleanupCard"' not in ui
    assert 'id="advancedDiagnosticsCard"' not in ui
    assert 'id="shortcuts"' not in ui
