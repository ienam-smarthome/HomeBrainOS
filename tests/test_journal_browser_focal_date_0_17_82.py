"""0.17.82: browser, paging and same-day causal evidence regression."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from historical_evidence_journal import HistoricalEvidenceJournal
from skill_focal_window import _requested_clock, build_focal_source_plan
from test_skill_missing_focal_0_17_76 import _evicted
from webui import render_page


def _journal(tmp_path):
    j = HistoricalEvidenceJournal(
        enabled=True, hub_url="http://192.168.1.239",
        path=tmp_path / "history.sqlite3",
    )
    j._initialize()
    return j


def test_browser_paging_preserves_order_and_explicit_partial_coverage(tmp_path):
    j = _journal(tmp_path)
    records = []
    for seconds in range(5):
        stamp = f"2026-10-15T18:55:0{seconds}+00:00"
        event = j._row("events", {
            "source": "DEVICE", "deviceId": 7805,
            "name": "switch", "value": "on" if seconds % 2 else "off",
            "date": stamp,
        }, stamp, j.log_app_ids)
        assert event is not None
        records.append(event)
    assert j._write_batch(records) == 5
    scope = {
        "device_id": "7805", "attribute": "switch",
        "since": "2026-10-15T18:55:00+00:00",
        "until": "2026-10-15T18:56:00+00:00", "limit": 2,
    }
    p0 = j.query(**scope, offset=0)
    p1 = j.query(**scope, offset=2)
    p2 = j.query(**scope, offset=4)
    assert [p["count"] for p in (p0,p1,p2)] == [2,2,1]
    assert [p["has_more"] for p in (p0,p1,p2)] == [True,True,False]
    assert [p["next_offset"] for p in (p0,p1,p2)] == [2,4,None]
    times = [row["observed_at"] for p in (p0,p1,p2) for row in p["events"]]
    assert times == sorted(times) and len(set(times)) == 5
    assert all(p["coverage_complete"] is False for p in (p0,p1,p2))
    assert j.query(**scope, offset=5)["count"] == 0
    with pytest.raises(ValueError):
        j.query(**scope, offset=-1)
    with pytest.raises(ValueError):
        j.query(**scope, offset=j.max_rows + 1)


def test_browser_markup_is_read_only_and_renders_event_values_as_text():
    page = render_page("HomeBrain", "0.17.82")
    assert 'id="journalBrowser"' in page
    assert 'id="journalBrowseDevice"' in page
    assert 'id="journalBrowseDay"' in page
    assert 'id="journalBrowseRows"' in page
    assert "api/evidence-journal/events?" in page
    assert "td.textContent=val" in page
    assert "data.message" not in page[page.index("async function browseJournal"):page.index("document.getElementById('journalBrowseDay')")]
    assert "timestamp_basis==='source'" in page


def test_day_before_command_cannot_anchor_requested_date_or_time():
    prior_day = datetime(2026, 10, 14, 19, 54, 46, tzinfo=timezone(timedelta(hours=1)))
    request_15 = "Why did Livingroom Light 1 turn ON at 19:55 on 15 October 2026?"
    request_14 = "Why did Livingroom Light 1 turn ON at 19:55 on 14 October 2026?"
    assert _requested_clock(request_15, prior_day) is None
    assert _requested_clock(request_14, prior_day).date().isoformat() == "2026-10-14"
    assert build_focal_source_plan(_evicted(), request_15) is None
    matched = build_focal_source_plan(_evicted(), request_14)
    assert matched is not None
    assert matched["sourceWindow"]["since"].startswith("2026-10-14T")
    assert matched["producerAppId"] == "4129"
