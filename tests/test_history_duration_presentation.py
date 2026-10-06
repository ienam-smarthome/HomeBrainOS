from __future__ import annotations

from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from history_temporal_analysis import guard_history_duration_claim  # noqa: E402


def _receipt() -> dict:
    return {
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
                "totalActiveDuration": "10m",
                "totalActiveSeconds": 615,
                "intervalCount": 4,
                "windowed": True,
                "windowLabel": "this morning",
                "pageCompleteToWindowStart": False,
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "durationReliability": "unverified-event-stream",
                "firstWindowStateEvent": {
                    "timestamp": "2026-10-06T08:21:08.986000+01:00",
                    "state": "off",
                    "isStateChange": True,
                },
                "predecessorStateEvent": None,
                "observedIntervals": [
                    {
                        "start": "2026-10-06T09:22:20.463+0100",
                        "end": "2026-10-06T09:23:12.638+0100",
                        "durationSeconds": 52,
                    },
                    {
                        "start": "2026-10-06T09:25:06.587+0100",
                        "end": "2026-10-06T09:30:42.698+0100",
                        "durationSeconds": 336,
                    },
                    {
                        "start": "2026-10-06T09:34:44.883+0100",
                        "end": "2026-10-06T09:38:15.294+0100",
                        "durationSeconds": 210,
                    },
                    {
                        "start": "2026-10-06T11:28:31.407+0100",
                        "end": "2026-10-06T11:28:48.174+0100",
                        "durationSeconds": 17,
                    },
                ],
            },
        },
    }


def test_incomplete_duration_repair_uses_readable_summary_table_and_note() -> None:
    draft = (
        "Bathroom Light 1 was on for an estimated total of 10 minutes this morning, "
        "based on recorded events."
    )

    corrected, changed = guard_history_duration_claim(draft, [_receipt()])

    assert changed is True
    assert corrected.startswith(
        "**Bathroom Light 1 was on for about 10 minutes in total this morning, "
        "across 4 recorded intervals.**"
    )
    assert "| On | Off | Duration |" in corrected
    assert "| 09:22 | 09:23 | 52 sec |" in corrected
    assert "| 09:25 | 09:30 | 5 min 36 sec |" in corrected
    assert "| 09:34 | 09:38 | 3 min 30 sec |" in corrected
    assert "| 11:28 | 11:28 | 17 sec |" in corrected
    assert "**Note:**" in corrected
    assert "off at 08:21" in corrected
    assert "does not reach the start of this morning" in corrected
    assert "estimate from the recorded state pairs" in corrected


def test_interval_table_is_derived_only_from_deterministic_observed_intervals() -> None:
    receipt = _receipt()
    receipt["details"]["temporalAnalysis"]["observedIntervals"] = [
        {
            "start": "2026-10-06T10:01:02+0100",
            "end": "2026-10-06T10:02:05+0100",
            "durationSeconds": 63,
        }
    ]
    receipt["details"]["temporalAnalysis"]["intervalCount"] = 1
    receipt["details"]["temporalAnalysis"]["totalActiveDuration"] = "1m"
    receipt["details"]["temporalAnalysis"]["totalActiveSeconds"] = 63

    corrected, changed = guard_history_duration_claim(
        "Bathroom Light 1 was on for an exact total of 1 minute this morning.",
        [receipt],
    )

    assert changed is True
    assert "| 10:01 | 10:02 | 1 min 3 sec |" in corrected
    assert "09:22" not in corrected

def test_live_duplicate_unverified_caveat_is_removed_after_duration_repair() -> None:
    draft = (
        "Bathroom Light 1 was on for an estimated total of 10 minutes this morning, "
        "based on recorded events. "
        "This is an estimate based on an unverified event stream, and because the "
        "available history is partial and does not reach the start of the morning, "
        "earlier transitions may be missing."
    )

    corrected, changed = guard_history_duration_claim(draft, [_receipt()])

    assert changed is True
    assert "about 10 minutes in total this morning" in corrected
    assert "This is an estimate based on an unverified event stream" not in corrected
    assert corrected.count("earlier in-window transitions may be missing") == 1
    assert corrected.count("not an exact total or a mathematical lower bound") == 1

