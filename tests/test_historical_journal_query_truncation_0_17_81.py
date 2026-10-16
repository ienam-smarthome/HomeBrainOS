"""Regression tests for explicit journal query truncation (0.17.81)."""
from __future__ import annotations

from historical_evidence_journal import HistoricalEvidenceJournal


def test_query_reports_truncation_without_claiming_complete_coverage(tmp_path):
    journal = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "journal.sqlite3",
    )
    journal._initialize()
    rows = []
    for second in range(3):
        received = f"2026-10-12T07:18:2{second}+00:00"
        row = journal._row("events", {
            "source": "DEVICE", "deviceId": 7774, "name": "motion",
            "value": "active" if second % 2 else "inactive",
            "date": received,
        }, received, journal.log_app_ids)
        assert row is not None
        rows.append(row)
    assert journal._write_batch(rows) == 3
    args = dict(
        device_id="7774",
        since="2026-10-12T07:18:00+00:00",
        until="2026-10-12T07:19:00+00:00",
    )
    capped = journal.query(**args, limit=2)
    assert capped["count"] == 2
    assert capped["limit"] == 2
    assert capped["truncated"] is True
    assert capped["coverage_complete"] is False

    exact = journal.query(**args, limit=3)
    assert exact["count"] == 3
    assert exact["truncated"] is False
    assert exact["coverage_complete"] is False

    empty = journal.query(
        device_id="8888", since=args["since"], until=args["until"], limit=2
    )
    assert empty["truncated"] is False
    assert empty["coverage_complete"] is False
    assert empty["empty_means_inactivity"] is False
