"""Stage 8.4 regression: delayed historical source events cannot prove new contact."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(ROOT))
from live_shadow_journal import project_shadow_history  # noqa: E402
from webui import render_page  # noqa: E402


def _row(at, received, state, *, dev="123"):
    return {
        "device_id": dev, "stream": "events", "attribute": "switch",
        "value": state, "source_time": at, "observed_at": at,
        "received_at": received, "timestamp_basis": "source",
        "display_name": "VERY PRIVATE NAME", "message": "SECRET",
    }


def test_real_report_shape_distinguishes_delayed_collection_from_device_time():
    # Synthetic six-event clock/arrival pattern, without live device details
    # or actual household activity being committed to the repository.
    pairs = [
        ("2026-02-11T00:30:01.905+00:00",
         "2026-03-01T19:28:11.846421+00:00", "off"),
        ("2026-02-11T00:30:01.910+00:00",
         "2026-03-01T19:28:11.846493+00:00", "off"),
        ("2026-02-11T01:22:05.308+00:00",
         "2026-03-01T19:28:11.846342+00:00", "on"),
        ("2026-02-11T01:30:01.690+00:00",
         "2026-03-01T19:28:11.846235+00:00", "off"),
        ("2026-02-11T22:22:29.246+00:00",
         "2026-03-01T17:39:28.351828+00:00", "on"),
        ("2026-02-12T00:30:01.914+00:00",
         "2026-02-27T11:44:28.151100+00:00", "off"),
    ]
    archive = {
        "events": [_row(*pair) for pair in pairs],
        "gaps": [
            {"stream": "events", "started_at": "2026-03-04T10:00:00+00:00",
             "ended_at": "2026-03-04T10:00:10+00:00", "reason": "secret"}
        ],
        "has_more": False, "offset": 0, "coverage_complete": False,
    }
    result = project_shadow_history(
        "123", archive,
        window_start="2026-02-02T12:17:05+00:00",
        window_end="2026-03-04T12:17:05+00:00",
        read_at="2026-03-04T12:17:05+00:00",
    )
    temporal = result["temporal_integrity"]
    assert result["returned_event_count"] == 6
    assert temporal["source_timestamps_present"] == 6
    assert temporal["events_with_source_older_than_receipt_by_over_one_day"] == 6
    assert temporal["large_timestamp_discrepancy"] is True
    assert temporal["minimum_apparent_separation_days"] > 15
    assert temporal["maximum_apparent_separation_days"] > 18
    assert temporal["adjacent_receipt_order_inversions"] >= 1
    assert temporal["latest_declared_source_utc"].startswith("2026-02-12T00:30:01")
    assert temporal["latest_collector_receipt_utc"].startswith("2026-03-01")
    assert temporal["independently_authenticated_source_clock"] is False
    assert temporal["receipt_time_proves_device_was_online"] is False
    assert temporal["source_arrival_gap_proves_device_disconnection"] is False
    assert result["history_complete"] is False
    assert result["causal_attribution_verified"] is False
    assert result["publisher_approval"] is False
    assert "VERY PRIVATE NAME" not in str(result)
    assert "secret" not in str(result).lower()


def test_no_source_time_is_not_fabricated_or_normalized_as_device_clock():
    a = {
        "events": [{
            "stream": "events", "device_id": "123",
            "attribute": "switch", "value": "off",
            "source_time": "", "observed_at": "2026-03-04T11:15:00+00:00",
            "received_at": "2026-03-04T11:15:01+00:00",
        }], "gaps": [], "offset": 0,
    }
    r=project_shadow_history(
        "123", a, window_start="2026-02-02T11:00:00+00:00",
        window_end="2026-03-04T12:00:00+00:00",
        read_at="2026-03-04T12:00:00+00:00",
    )
    t=r["temporal_integrity"]
    assert t["source_timestamps_present"] == 0
    assert t["minimum_apparent_separation_days"] is None
    assert t["earliest_declared_source_utc"] is None
    assert t["earliest_collector_receipt_utc"] is not None
    assert r["events"][0]["timestamp_basis"] == "collector_only"


def test_zero_events_or_broken_archive_never_suggests_coverage():
    base = {"events": [], "gaps": [], "offset": 0}
    a=project_shadow_history(
        "123", base, window_start="2026-02-02T11:00:00+00:00",
        window_end="2026-03-04T12:00:00+00:00",
        read_at="2026-03-04T12:00:00+00:00",
    )
    assert a["temporal_integrity"]["source_timestamps_present"] == 0
    assert not a["history_complete"]
    assert not a["missing_events_prove_inactivity"]


def test_phone_reports_apparent_not_authenticated_source_time():
    ui=render_page("HomeBrainOS","0.18.319")
    for expected in (
        "Temporal integrity", "Apparent source-to-receipt gap",
        "This could be replay, delayed ingestion or clock error",
        "do not call it fresh device contact",
        "source time is NOT independently authenticated",
    ):
        assert expected in ui
