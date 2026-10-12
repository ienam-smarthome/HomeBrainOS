"""0.17.26 journal UI contract and persisted evidence counters.

Uses a temporary SQLite journal, no Hubitat connections or mutations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from historical_evidence_journal import HistoricalEvidenceJournal
from webui import render_page


def journal(tmp_path):
    result = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "journal.sqlite3",
        capture_logs=True, log_app_ids="4015,4019",
    )
    result._initialize()
    result._started = True
    return result


def test_counts_disk_size_app_log_allowlist_and_restart(tmp_path):
    j = journal(tmp_path)
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    packets = [
        ("events", {"deviceId": 7840, "name": "switch", "value": "on",
                    "displayName": "Bedroom 1 Light", "source": "DEVICE"}),
        ("events", {"deviceId": 7840, "name": "switch", "value": "off",
                    "displayName": "Bedroom 1 Light", "source": "DEVICE"}),
        ("logs", {"type": "app", "id": "4015", "level": "debug",
                  "name": "Bedroom 1 (Lights Off)",
                  "msg": "lightSwitchHandler: motion inactive"}),
    ]
    rows = [j._row(stream, packet, now, j.log_app_ids)
            for stream, packet in packets]
    assert all(row is not None for row in rows)
    assert j._write_batch(rows) == 3

    status = j.status()
    assert status["connected"] == {"events": False, "logs": False}
    assert status["rows"] == 3
    assert status["event_rows"] == 2
    assert status["app_log_rows"] == 1
    assert status["captured_app_log_counts"] == {"4015": 1, "4019": 0}
    assert status["tracked_app_ids"] == ["4015", "4019"]
    assert status["db_bytes"] > 0
    assert status["coverage_complete"] is False

    restored = journal(tmp_path)
    again = restored.status()
    assert again["rows"] == 3
    assert again["captured_app_log_counts"] == {"4015": 1, "4019": 0}
    assert again["app_log_rows"] == 1


def test_recent_list_excludes_private_log_messages(tmp_path):
    j = journal(tmp_path)
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    device = j._row("events", {
        "deviceId": "7840", "name": "switch", "value": "off",
        "source": "DEVICE", "displayName": "Bedroom 1 Light",
    }, now, j.log_app_ids)
    secret = "private-log-not-allowed-in-dashboard"
    app = j._row("logs", {
        "type": "app", "id": "4015", "level": "info",
        "name": "Bedroom 1", "msg": secret,
    }, now, j.log_app_ids)
    assert device and app
    j._write_batch([device, app])
    payload = j.recent_events(limit=100000)
    assert payload["count"] == 1
    assert payload["events"][0]["attribute"] == "switch"
    assert payload["events"][0]["timestamp_basis"] == "collector-received"
    assert "message" not in payload["events"][0]
    assert secret not in str(payload)
    assert payload["coverage_complete"] is False
    assert payload["empty_means_inactivity"] is False


def test_recent_gaps_include_start_and_ends_without_implying_completeness(tmp_path):
    j = journal(tmp_path)
    j._mark_disconnected("events", "collector-start")
    assert j.status()["open_gaps"] == 1
    j._mark_connected("events")
    state = j.status()
    assert state["open_gaps"] == 0
    assert state["gaps"] == 1
    gap = state["recent_gaps"][0]
    assert gap["stream"] == "events"
    assert gap["reason"] == "collector-start"
    assert gap["ended_at"] is not None
    assert state["coverage_complete"] is False


def test_mobile_dashboard_renders_journal_and_fetches_safe_scope():
    html = render_page("Hubitat MCP AI", "0.17.26")
    for required in (
        'id="journalCard"', 'id="journalHealth"',
        'id="journalEventsStream"', 'id="journalLogsStream"',
        'id="journalEventRows"', 'id="journalLogRows"',
        'id="journalBytes"', 'id="journalGapCount"',
        'id="journalDetails"', 'id="journalRecentEvents"',
        'id="journalAppLogs"', 'id="journalRefresh"',
        'api/evidence-journal/status',
        'api/evidence-journal/recent?limit=12',
        "captured_app_log_counts", "timestamp_basis",
        "coverage_complete",
    ):
        # Rendered JS must never suggest continuous coverage; backend stays
        # authoritative on completeness, and no log text is included in recent.
        if required == "coverage_complete":
            assert "An empty history does not prove inactivity." in html
        else:
            assert required in html
    assert 'class="journal-grid"' in html
    assert "collector-received" in html or "Collector received" in html
