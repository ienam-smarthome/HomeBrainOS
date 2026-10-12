"""Persistence, privacy, gap and bounded retrieval contracts for opt-in journal.

These tests use SQLite in tmp_path and never contact a real Hubitat hub.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from historical_evidence_journal import (
    HistoricalEvidenceJournal, _hub_base_url, _aware_iso,
)


def make_journal(tmp_path, **kwargs):
    journal = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "journal.sqlite3", **kwargs,
    )
    journal._initialize()
    return journal


def test_websocket_destination_is_local_and_cannot_accept_credentials_or_paths():
    assert _hub_base_url("http://192.168.1.239") == "ws://192.168.1.239"
    assert _hub_base_url("http://hubitat.local") == "ws://hubitat.local"
    for invalid in (
        "https://example.com", "http://user:pass@192.168.1.239",
        "http://192.168.1.239/installedapp", "http://8.8.8.8",
        "http://192.168.1.239/?access_token=abc",
    ):
        with pytest.raises(ValueError):
            _hub_base_url(invalid)


def test_event_and_app_log_allowlist_redaction_and_timestamp_basis(tmp_path):
    journal = make_journal(tmp_path, capture_logs=True, log_app_ids="4015")
    now = "2026-10-12T07:18:23.830000+00:00"
    row = journal._row("events", {
        "source": "DEVICE", "deviceId": 7774, "name": "motion",
        "value": "inactive", "displayName": "Bedroom 1 FP300",
    }, now, journal.log_app_ids)
    assert row is not None
    assert row["observed_at"] == now
    assert row["timestamp_basis"] == "collector-received"
    assert journal._row("events", {
        "source": "DEVICE", "deviceId": 7774, "name": "battery", "value": "27"
    }, now, journal.log_app_ids) is None
    assert journal._row("logs", {
        "type": "app", "id": "9999", "msg": "off()"
    }, now, journal.log_app_ids) is None
    log = journal._row("logs", {
        "type": "app", "id": 4015, "level": "debug",
        "name": "Bedroom 1", "msg": "motion inactive; token=abc123 password=12345",
    }, now, journal.log_app_ids)
    assert log is not None and "abc123" not in log["message"]
    assert "12345" not in log["message"]


def test_journal_persists_and_deduplicates_source_timestamps(tmp_path):
    journal = make_journal(tmp_path)
    received = "2026-10-12T07:18:23.830000+00:00"
    packet = {
        "source": "DEVICE", "deviceId": 7774, "name": "motion",
        "value": "inactive", "date": received,
        "displayName": "Bedroom 1 FP300",
    }
    one = journal._row("events", packet, received, journal.log_app_ids)
    two = journal._row(
        "events", packet, "2026-10-12T07:18:29.830000+00:00", journal.log_app_ids
    )
    assert one is not None and two is not None
    assert one["timestamp_basis"] == "source"
    assert journal._write_batch([one, two]) == 1
    restored = make_journal(tmp_path)
    reply = restored.query(
        device_id="7774", attribute="motion",
        since="2026-10-12T07:18:00+00:00",
        until="2026-10-12T07:19:00+00:00",
    )
    assert reply["count"] == 1
    assert reply["coverage_complete"] is False
    assert reply["empty_means_inactivity"] is False


def test_capture_without_source_time_never_invents_exact_event_time(tmp_path):
    journal = make_journal(tmp_path)
    packet = {
        "source": "DEVICE", "deviceId": 7774, "name": "motion", "value": "inactive",
    }
    first = journal._row(
        "events", packet, "2026-10-12T07:18:23.830000+00:00", journal.log_app_ids,
    )
    second = journal._row(
        "events", packet, "2026-10-12T07:18:24.830000+00:00", journal.log_app_ids,
    )
    assert first is not None and second is not None
    assert journal._write_batch([first, second]) == 2
    assert first["timestamp_basis"] == "collector-received"


def test_connection_outage_is_persistent_and_overlaps_queries(tmp_path):
    journal = make_journal(tmp_path)
    journal._mark_disconnected("events", "collector-start")
    # Repeat disconnect is idempotent, does not create many false gaps.
    journal._mark_disconnected("events", "collector-start")
    journal._mark_connected("events")
    with journal._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM journal_gaps").fetchone()[0] == 1
    now = datetime.now(timezone.utc)
    result = journal.query(
        device_id="7774",
        since=(now - timedelta(minutes=1)).isoformat(),
        until=(now + timedelta(minutes=1)).isoformat(),
    )
    assert result["count"] == 0
    assert len(result["gaps"]) == 1
    assert result["coverage_complete"] is False


def test_queries_require_exact_scope_and_ordered_offset_time(tmp_path):
    journal = make_journal(tmp_path)
    with pytest.raises(ValueError):
        journal.query(since="2026-10-12T08:00:00+01:00",
                      until="2026-10-12T09:00:00+01:00")
    with pytest.raises(ValueError):
        journal.query(device_id="7774", since="2026-10-12T09:00:00+01:00",
                      until="2026-10-12T08:00:00+01:00")
    with pytest.raises(ValueError):
        journal.query(device_id="7774", since="2026-10-12T08:00:00",
                      until="2026-10-12T09:00:00")


def test_retention_prunes_old_rows_and_preserves_recent(tmp_path):
    journal = make_journal(tmp_path, retention_days=7)
    current = datetime.now(timezone.utc)
    old = (current - timedelta(days=9)).isoformat(timespec="microseconds")
    recent = current.isoformat(timespec="microseconds")
    packet = {"source": "DEVICE", "deviceId": 7774, "name": "switch", "value": "off"}
    past = journal._row("events", packet, old, journal.log_app_ids)
    latest = journal._row("events", packet, recent, journal.log_app_ids)
    assert past and latest
    journal._write_batch([past, latest], prune=True)
    with journal._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM journal_events").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_writer_flushes_bounded_queue_on_shutdown_without_sockets(tmp_path):
    journal = make_journal(tmp_path)
    # Testing queue/writer only: do not connect to the hub.
    import asyncio
    journal._started = True
    journal._tasks = [asyncio.create_task(journal._writer())]
    assert await journal.ingest("events", {
        "source": "DEVICE", "deviceId": 7774, "name": "motion",
        "value": "active",
    })
    await journal.close()
    with journal._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM journal_events").fetchone()[0] == 1
