from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from history_temporal_analysis import guard_history_duration_claim  # noqa: E402


WINDOW_START = datetime.fromisoformat("2026-10-06T00:00:00+01:00")


def _event(value: str, timestamp: str) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": True,
    }


def test_short_retained_page_does_not_prove_semantic_window_start_coverage() -> None:
    # Live Bathroom Light 1 shape: HomeBrain requested 50 rows, but Hubitat's
    # retained native history returned only 11. The oldest retained row was
    # 07:53, well after the requested midnight boundary.
    events = [
        _event("off", "2026-10-06T11:28:48.174+0100"),
        _event("on", "2026-10-06T11:28:31.407+0100"),
        _event("off", "2026-10-06T09:38:15.294+0100"),
        _event("on", "2026-10-06T09:34:44.883+0100"),
        _event("off", "2026-10-06T09:30:42.698+0100"),
        _event("on", "2026-10-06T09:25:06.587+0100"),
        _event("off", "2026-10-06T09:23:12.638+0100"),
        _event("on", "2026-10-06T09:22:20.463+0100"),
        _event("off", "2026-10-06T08:21:08.986+0100"),
        _event("on", "2026-10-06T08:20:33.060+0100"),
        _event("off", "2026-10-06T07:53:08.880+0100"),
    ]

    assert DeviceHistoryService._source_complete_to_window_start(
        events,
        fetch_limit=50,
        window_start=WINDOW_START,
    ) is False


def test_timestamp_at_or_before_boundary_proves_page_reaches_window_start() -> None:
    events = [
        _event("off", "2026-10-06T08:00:00+0100"),
        _event("on", "2026-10-05T23:58:00+0100"),
    ]

    assert DeviceHistoryService._source_complete_to_window_start(
        events,
        fetch_limit=50,
        window_start=WINDOW_START,
    ) is True


def test_duration_guard_discloses_retained_page_gap_for_live_morning_shape() -> None:
    receipt = {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bathroom Light 1",
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "timeWindow": {
                "kind": "this_morning",
                "label": "this morning",
                "sourcePageCompleteToStart": False,
            },
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveDuration": "11m",
                "totalActiveSeconds": 651,
                "intervalCount": 5,
                "windowed": True,
                "windowLabel": "this morning",
                "pageCompleteToWindowStart": False,
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "durationReliability": "unverified-event-stream",
            },
        },
    }
    draft = (
        "Bathroom Light 1 was on for an estimated total of 11 minutes this morning, "
        "based on recorded events. This is an estimate as the event stream integrity "
        "is unverified."
    )

    corrected, changed = guard_history_duration_claim(draft, [receipt])

    assert changed is True
    assert "estimate of 11m" in corrected
    assert "does not reach the start of this morning" in corrected
    assert "earlier in-window transitions may be missing" in corrected
    assert "not an exact total or a mathematical lower bound" in corrected
