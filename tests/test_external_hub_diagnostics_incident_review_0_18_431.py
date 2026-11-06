"""Bounded local-only incident drilldown contract, HomeBrainOS v0.18.431."""
from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from external_hub_diagnostics import ExternalHubDiagnostics  # noqa: E402
from historical_evidence_journal import HistoricalEvidenceJournal  # noqa: E402
from webui import render_page  # noqa: E402


def _ms(time: datetime) -> str:
    return time.isoformat(timespec="milliseconds")


def _us(time: datetime) -> str:
    return time.isoformat(timespec="microseconds")


def _rec(tmp_path: Path) -> ExternalHubDiagnostics:
    rec = ExternalHubDiagnostics(enabled=True, hub_url="http://192.168.1.239",
                                 path=tmp_path / "rec.sqlite3", probe_seconds=30,
                                 retention_days=30, cpu_cores=4)
    rec._initialize()
    return rec


def _journal(tmp_path: Path, log_retention_hours: int = 48) -> HistoricalEvidenceJournal:
    j = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "journal.sqlite3", retention_days=30,
        capture_logs=True, log_app_ids="3919,4151",
        log_retention_hours=log_retention_hours,
    )
    j._initialize()
    return j


def _write_journal(db_path: Path, *,
                   stream: str, at: datetime, idx: int,
                   message: str = "", app_id: str = "") -> None:
    stamp = _us(at)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO journal_events "
            "(stream,device_id,app_id,attribute,value,display_name,source,"
            "source_time,observed_at,received_at,timestamp_basis,message,signature) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stream, "7828" if stream == "events" else "", app_id,
             "switch" if stream == "events" else "error",
             "off" if stream == "events" else "",
             "Livingroom Light 2" if stream == "events" else "Hub Inspector",
             "hubitat-eventsocket" if stream == "events" else "hubitat-logsocket",
             "" if stream == "logs" else stamp,
             stamp, stamp, "source" if stream == "events" else "collector-received",
             message, f"unique-sig-{stream}-{idx}"),
        )


def test_recorder_probe_evidence_keeps_distinct_clocks_and_the_incident_sequence(tmp_path):
    rec = _rec(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=40)
    # Example: low memory before loss, startup after recovery, load peak after startup.
    rows = [
        (0, 935.0, "native-1", 0.8, True),
        (4, 221.0, "native-1", 0.8, True),
        (6, None, None, None, False),
        (7, None, None, None, False),
        (12, 960.0, "native-2", 0.8, True),
        (13, 965.0, "native-2", 0.8, True),
        (17, 925.0, "native-3", 3.58, True),
    ]
    startup_time = _ms(base + timedelta(minutes=14))
    for i, (m, memory, label, load, reachable) in enumerate(rows):
        row = {
            "recorded_at": _ms(base + timedelta(minutes=m)),
            "reachable": int(reachable), "latency_ms": 35 if reachable else None,
            "free_os_mb": memory, "native_sample_label": label,
            "native_load5": load,
            "java_free_mb": 100.0 if label == "native-3" else 145.0 if label else None,
        }
        rec._save(
            row,
            opened=_ms(base + timedelta(minutes=6)) if m == 7 else None,
            recovered=m == 12,
            startups=({
                "occurred_at": startup_time, "firmware": "2.5.3.118",
                "source": "hub_events_json_systemStart",
            },) if m == 17 else (),
        )
    focus = base + timedelta(minutes=10)
    result = rec.incident_evidence(base, base + timedelta(minutes=20), focus)
    assert result["causal_status"] == "unverified"
    assert result["status"] == "partial_observations_not_proof_of_cause"
    assert result["sample_count"] == 7
    assert result["failed_samples"] == 2
    assert result["memory_min"] == {"value": 221.0, "recorded_at": _ms(base + timedelta(minutes=4)),
                                    "basis": "external_probe"}
    assert result["cpu_load_max"]["value"] == 89.5
    assert result["cpu_load_max"]["native_sample_label"] == "native-3"
    assert result["cpu_load_max"]["recorded_at"] > startup_time
    assert result["java_free_min"]["value"] == 100.0
    assert result["last_success_before"]["recorded_at"] == _ms(base + timedelta(minutes=4))
    assert result["first_success_after"]["recorded_at"] == _ms(base + timedelta(minutes=12))
    assert result["startups"][0]["occurred_at"] == startup_time
    assert result["incidents"][0]["started_at"] == _ms(base + timedelta(minutes=6))
    assert result["incidents"][0]["recovered_at"] == _ms(base + timedelta(minutes=12))
    assert all(row["free_os_mb"] is None for row in result["samples"] if row["reachable"] == 0)


def test_journal_report_is_partial_capped_and_never_includes_private_log_messages(tmp_path):
    j = _journal(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=20)
    for i in range(53):
        _write_journal(j.path, stream="events", at=base + timedelta(seconds=i),
                       idx=i)
    secret="Bearer PRIVATE-USER-KEY token=password-value"
    _write_journal(j.path, stream="logs", app_id="3919",
                   at=base + timedelta(seconds=90), idx=100, message=secret)
    _write_journal(j.path, stream="logs", app_id="3919",
                   at=base + timedelta(seconds=100), idx=101, message=secret)
    with sqlite3.connect(j.path) as conn:
        conn.execute("INSERT INTO journal_gaps (stream,started_at,ended_at,reason) "
                     "VALUES (?,?,?,?)",
                     ("events", _us(base + timedelta(seconds=30)),
                      _us(base + timedelta(seconds=45)), "stream-disconnected"))
    result = j.incident_evidence(base - timedelta(minutes=1),
                                 base + timedelta(minutes=4))
    assert result["event_count"] == 53
    assert len(result["events"]) == 40
    assert result["events_truncated"] is True
    assert result["app_log_count"] == 2
    assert result["app_log_apps"][0]["app_id"] == "3919"
    assert result["app_log_apps"][0]["count"] == 2
    assert result["app_log_messages_included"] is False
    assert secret not in json.dumps(result)
    assert "message" not in json.dumps(result)
    assert len(result["gaps"]) == 1
    assert result["coverage_complete"] is False
    assert result["empty_means_inactivity"] is False


def test_app_logs_expired_at_read_time_even_before_pruning(tmp_path):
    j = _journal(tmp_path, log_retention_hours=1)
    then = datetime.now(timezone.utc) - timedelta(hours=2)
    _write_journal(j.path, stream="logs", app_id="4151", at=then, idx=42,
                   message="PRIVATE HISTORICAL LOG")
    output = j.incident_evidence(then - timedelta(minutes=1),
                                 then + timedelta(minutes=1))
    assert output["app_log_count"] == 0
    assert output["app_log_apps"] == []
    assert output["coverage_complete"] is False


def test_missing_archive_is_explicitly_unavailable_not_proof_of_no_activity(tmp_path):
    rec = _rec(tmp_path)
    j = _journal(tmp_path)
    rec.enabled = False
    j.enabled = False
    now = datetime.now(timezone.utc)
    assert rec.incident_evidence(now - timedelta(minutes=5), now, now)["status"] == "not_recorded"
    actual = j.incident_evidence(now - timedelta(minutes=5), now)
    assert actual["status"] == "disabled"
    assert not actual["events"]
    assert actual["coverage_complete"] is False


def test_incident_api_rejects_naive_stale_future_or_unbounded_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    recorder, journal = _rec(tmp_path), _journal(tmp_path)
    monkeypatch.setattr(module, "external_hub_diagnostics", recorder)
    monkeypatch.setattr(module, "historical_journal", journal)
    client = TestClient(module.app)
    focus = datetime.now(timezone.utc) - timedelta(minutes=10)
    good = client.get("/api/hub-diagnostics/incident", params={
        "at": _ms(focus), "window_minutes": 15,
    })
    assert good.status_code == 200, good.text
    body = good.json()
    assert body["read_only"] is True
    assert body["live_hubitat_requests"] == 0
    assert body["causal_verdict"] == "unverified"
    assert body["window_minutes_each_side"] == 15
    assert "no-store" in good.headers.get("cache-control", "")
    for at, minutes in (
        ("2026-11-05T22:25:00", 15),
        (_ms(focus), 120),
        (_ms(datetime.now(timezone.utc) + timedelta(hours=2)), 15),
        (_ms(datetime.now(timezone.utc) - timedelta(days=31)), 15),
    ):
        response = client.get("/api/hub-diagnostics/incident",
                              params={"at": at, "window_minutes": minutes})
        assert response.status_code == 422
    assert "/api/hub-diagnostics/incident" in module.app.openapi()["paths"]


def test_incident_ui_is_explicit_on_demand_and_retains_existing_charts():
    html = render_page("HomeBrain", "0.18.431")
    for required in (
        'id="diagReviewSelected" disabled', 'id="diagReviewDetails" hidden',
        'id="diagReviewMinutes"', 'id="diagReviewCopy"',
        'id="diagReviewReload"', 'id="diagReviewJson"',
        'id="diagReviewJournal"', 'id="diagReviewAppCounts"',
        'id="diagReviewGaps"', 'id="diagReviewRecorder"',
        'api/hub-diagnostics/incident?at=',
        "function inspectIncidentAt(timestamp)",
        "function loadIncidentReview()",
        "App-log bodies are deliberately excluded",
        "causal conclusions UNVERIFIED",
        'id="diagTimelineChart"',
        'id="diagChart"',
        'id="journalCard"',
        'id="systemHealthCard"',
    ):
        assert required in html, required
    assert 'id="oneTimeCleanupCard"' not in html
    assert 'id="advancedDiagnosticsCard"' not in html
