"""v0.18.246 all-app log collection, 48h privacy/storage, recent questions.

All tests run against a local temporary SQLite journal or in-memory fake.
No Hubitat or HA instance is contacted, and no commands are issued.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from historical_evidence_journal import HistoricalEvidenceJournal
from archived_app_decision_evidence import archived_app_decision_evidence
from group_app_decision_recovery import recover_group_app_decisions
from group_journal_recovery import journal_incident_bounds
from unified_investigation_bridge import collect_unified_evidence
from test_unified_incident_causal_consistency_0_18_243 import (
    actual_partial_receipts, QUESTION,
)


def journal(tmp_path, **kw):
    j = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "journal.sqlite3", capture_logs=True,
        log_app_ids="*", retention_days=30,
        log_retention_hours=48, **kw,
    )
    j._initialize()
    j._started = True
    return j


def app_packet(app_id, msg, level="debug"):
    return {"type": "app", "id": str(app_id), "name": "App " + str(app_id),
            "level": level, "time": "13:02:05", "msg": msg}


def test_all_app_capture_includes_unlisted_ids_and_scrubs_secret_before_disk(tmp_path):
    j = journal(tmp_path)
    assert j.log_app_ids == frozenset({"*"})
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    a = j._row("logs", app_packet(4013,
        "motion active; token=TOPSECRET password=PSW123 "
        "Authorization: Bearer TOPTOKEN url=https://example.test/?access_token=LEAK"),
        now, j.log_app_ids)
    b = j._row("logs", app_packet(4014, "shower motion active"), now, j.log_app_ids)
    c = j._row("logs", app_packet(99888, "unlisted app event"), now, j.log_app_ids)
    assert a and b and c
    assert a["timestamp_basis"] == "collector-received"
    assert "TOPSECRET" not in a["message"]
    assert "PSW123" not in a["message"]
    assert "TOPTOKEN" not in a["message"]
    assert "LEAK" not in a["message"]
    assert j._write_batch([a, b, c]) == 3
    with j._connect() as db:
        stored = [row[0] for row in db.execute(
            "SELECT message FROM journal_events WHERE stream='logs'")]
    assert len(stored) == 3
    assert all(x not in str(stored) for x in ("TOPSECRET", "PSW123", "TOPTOKEN", "LEAK"))
    assert j.status()["capture_all_app_logs"] is True
    assert j.status()["log_retention_hours"] == 48
    assert j.status()["app_log_rows"] == 3


def test_app_logs_prune_after_48h_without_deleting_older_device_history(tmp_path):
    j = journal(tmp_path)
    clock = datetime.now(timezone.utc)
    old_log_time = (clock - timedelta(hours=49)).isoformat(timespec="microseconds")
    recent_log_time = (clock - timedelta(hours=1)).isoformat(timespec="microseconds")
    old_device_time = (clock - timedelta(days=5)).isoformat(timespec="microseconds")
    old_log = j._row("logs", app_packet(4013, "old decision"), old_log_time, j.log_app_ids)
    fresh_log = j._row("logs", app_packet(1569, "fresh decision"), recent_log_time, j.log_app_ids)
    device = j._row("events", {"source":"DEVICE", "deviceId":7818,
                               "name":"switch", "value":"on"},
                    old_device_time, j.log_app_ids)
    assert old_log and fresh_log and device
    j._write_batch([old_log, fresh_log, device], prune=True)
    with j._connect() as db:
        counts = dict(db.execute("SELECT stream, COUNT(*) FROM journal_events GROUP BY stream"))
        oldest_log = db.execute(
            "SELECT app_id FROM journal_events WHERE stream='logs'").fetchone()
    assert counts == {"events": 1, "logs": 1}
    assert oldest_log[0] == "1569"
    assert j.retention_days == 30


@pytest.mark.asyncio
async def test_wildcard_app_decision_history_has_private_message_free_metadata(tmp_path):
    j = journal(tmp_path)
    now = datetime.now(timezone.utc)
    at = now.isoformat(timespec="microseconds")
    row = j._row("logs", app_packet(4013, "motion lockout engaged; token=PRIVATE"),
                 at, j.log_app_ids)
    assert row and j._write_batch([row]) == 1
    evidence = await archived_app_decision_evidence(
        j, app_id="4013",
        since=(now - timedelta(minutes=2)).isoformat(),
        until=(now + timedelta(minutes=2)).isoformat())
    assert evidence["querySucceeded"] is True
    assert evidence["configuredToCaptureApp"] is True
    assert evidence["returnedRows"] == 1
    assert evidence["collectorTimestampIsNotSourceEmissionClock"] is True
    assert evidence["historicalExecutionVerified"] is False
    assert "motion lockout engaged" not in str(evidence)
    assert "PRIVATE" not in str(evidence)


def test_relative_recent_bounds_anchored_in_utc_without_guessing_local_clock():
    before = datetime.now(timezone.utc)
    for question, seconds in (
        ("Investigate the last two hours of bathroom light activity", 7200),
        ("What happened over the past 30 minutes?", 1800),
        ("Check last 24 hours of lights", 86400),
    ):
        bounds = journal_incident_bounds(question, [])
        assert bounds is not None
        since, until, zone = bounds
        start = datetime.fromisoformat(since)
        end = datetime.fromisoformat(until)
        assert zone == "UTC"
        assert abs((end-start).total_seconds() - seconds) < 0.01
        assert before <= end <= datetime.now(timezone.utc) + timedelta(seconds=1)
    assert journal_incident_bounds("last 60 hours", []) is None
    assert journal_incident_bounds("recent activity", []) is None


class LocalDecisionJournal:
    enabled = True
    _started = True
    capture_logs = True
    log_app_ids = frozenset({"*"})
    _connected = {"logs": True, "events": True}
    def __init__(self):
        self.calls = []
    def query(self, **kw):
        self.calls.append(kw)
        when = datetime.now(timezone.utc).isoformat()
        return {"events": [{"stream":"logs", "app_id":kw["app_id"],
                            "message":"motion lockout enabled",
                            "attribute":"debug","received_at":when,
                            "timestamp_basis":"collector-received"}],
                "gaps": []}


class Recorder:
    def __init__(self): self.events = []
    def record(self, tool, args, **kwargs):
        self.events.append({"tool":tool, "arguments":args, **kwargs})
    def receipts(self): return self.events


@pytest.mark.asyncio
async def test_group_incident_uses_bounded_verified_app_issuers_not_question_invention():
    receipts = actual_partial_receipts()
    j, rec = LocalDecisionJournal(), Recorder()
    prompt = QUESTION.replace(
        "between 02:00 and 07:30 on 30 October 2026",
        "during the last two hours") + " Avoid app 999888."
    report = await recover_group_app_decisions(
        journal=j, recorder=rec, receipts=receipts, question=prompt)
    assert report["status"] == "checked"
    assert set(report["app_ids"]) == {"1568", "1569", "4013", "4014"}
    assert report["app_queries"] == 4
    assert len(j.calls) == 4
    assert all(c["app_id"] != "999888" for c in j.calls)
    assert all(0 < (datetime.fromisoformat(c["until"])-
                    datetime.fromisoformat(c["since"])).total_seconds() <= 7201
               for c in j.calls)
    assert all(x["mutates"] is False for x in rec.events)
    assert not any("motion lockout enabled" in str(x) for x in rec.events)
    facts = collect_unified_evidence(receipts + rec.receipts(), prompt)
    assert facts is not None
    assert len(facts["archived_app_checks"]) == 4
    assert all(x["historical_execution_verified"] is False
               for x in facts["archived_app_checks"])


@pytest.mark.asyncio
async def test_missing_attested_devices_does_not_authorize_log_retrieval():
    src = [r for r in actual_partial_receipts()
           if r.get("sub_tool") != "hub_list_devices"]
    j, rec = LocalDecisionJournal(), Recorder()
    result = await recover_group_app_decisions(
        journal=j, recorder=rec, receipts=src, question="during the last two hours")
    assert result["app_queries"] == 0
    assert j.calls == []
