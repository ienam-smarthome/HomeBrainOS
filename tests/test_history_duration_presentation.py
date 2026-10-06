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
    assert "not an exact total or a mathematical lower bound" in corrected


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

def test_live_0_16_109_duplicate_history_table_and_note_are_removed() -> None:
    draft = (
        "Bathroom Light 1 was on for an estimated total of 10 minutes this morning.\n\n"
        "| On | Off | Duration |\n"
        "| :--- | :--- | :--- |\n"
        "| 09:22 | 09:23 | 52s |\n"
        "| 09:25 | 09:30 | 5m 36s |\n"
        "| 09:34 | 09:38 | 3m 30s |\n"
        "| 11:28 | 11:28 | 17s |\n\n"
        "**Note:** The earliest recorded event in the window is **off at 08:21**, "
        "and the available history does not reach the start of the morning, so "
        "earlier transitions may be missing."
    )

    corrected, changed = guard_history_duration_claim(draft, [_receipt()])

    assert changed is True
    assert corrected.count("| On | Off | Duration |") == 1
    assert corrected.count("**Note:**") == 1
    assert "| 09:25 | 09:30 | 5 min 36 sec |" in corrected
    assert "| 09:25 | 09:30 | 5m 36s |" not in corrected
    assert "earliest recorded event in the window" not in corrected
    assert "earliest retained in-window state is **off at 08:21**" in corrected


def test_duplicate_history_cleanup_preserves_unrelated_analysis_table() -> None:
    draft = (
        "Bathroom Light 1 was on for an estimated total of 10 minutes this morning.\n\n"
        "| On | Off | Duration |\n"
        "| --- | --- | ---: |\n"
        "| 09:22 | 09:23 | 52s |\n\n"
        "**Note:** The available history does not reach the start of the morning, "
        "so earlier transitions may be missing.\n\n"
        "| Observation | Meaning |\n"
        "| --- | --- |\n"
        "| Motion overlap | Correlation only |"
    )

    corrected, changed = guard_history_duration_claim(draft, [_receipt()])

    assert changed is True
    assert corrected.count("| On | Off | Duration |") == 1
    assert "| Observation | Meaning |" in corrected
    assert "| Motion overlap | Correlation only |" in corrected

def _complete_afternoon_receipt() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bathroom Light 1",
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "timeWindow": {
                "kind": "this_afternoon",
                "label": "this afternoon",
                "start": "2026-10-06T12:00:00+01:00",
                "end": "2026-10-06T15:25:49+01:00",
                "ongoing": True,
                "sourcePageCompleteToStart": True,
            },
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveDuration": "3m",
                "totalActiveSeconds": 187,
                "intervalCount": 2,
                "windowed": True,
                "windowLabel": "this afternoon",
                "windowStart": "2026-10-06T12:00:00+01:00",
                "windowEnd": "2026-10-06T15:25:49+01:00",
                "windowOngoing": True,
                "pageCompleteToWindowStart": True,
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "durationReliability": "unverified-event-stream",
                "lastWindowStateEvent": {
                    "timestamp": "2026-10-06T14:50:03.297000+01:00",
                    "state": "off",
                    "isStateChange": True,
                },
                "observedIntervals": [
                    {
                        "start": "2026-10-06T13:17:44.968+0100",
                        "end": "2026-10-06T13:18:02.091+0100",
                        "durationSeconds": 17,
                    },
                    {
                        "start": "2026-10-06T14:47:13.756+0100",
                        "end": "2026-10-06T14:50:03.297+0100",
                        "durationSeconds": 170,
                    },
                ],
            },
        },
    }


def test_complete_window_repair_uses_practical_context_not_routine_warning() -> None:
    corrected, changed = guard_history_duration_claim(
        "Bathroom Light 1 was on for exactly 3 minutes this afternoon.",
        [_complete_afternoon_receipt()],
    )

    assert changed is True
    assert "about 3 minutes in total this afternoon" in corrected
    assert "| 13:17 | 13:18 | 17 sec |" in corrected
    assert "| 14:47 | 14:50 | 2 min 50 sec |" in corrected
    assert "**Note:**" not in corrected
    assert "latest recorded state for Bathroom Light 1 is off" in corrected
    assert "I counted this afternoon from 12:00" in corrected
    assert "last recorded event was the 14:50 switch-off" in corrected
    assert "currently off" not in corrected
    assert "not independently verified as complete" not in corrected


def test_live_0_16_111_routine_note_is_replaced_by_practical_context() -> None:
    draft = (
        "**Bathroom Light 1 was on for about 3 minutes in total this afternoon, "
        "across 2 recorded intervals.**\n\n"
        "| On | Off | Duration |\n"
        "| :--- | :--- | :--- |\n"
        "| 13:17 | 13:18 | 17 sec |\n"
        "| 14:47 | 14:50 | 2 min 50 sec |\n\n"
        "**Note:** This is an estimate based on recorded state pairs; "
        "the device-event stream has not been independently verified as complete."
    )

    corrected, changed = guard_history_duration_claim(
        draft,
        [_complete_afternoon_receipt()],
    )

    assert changed is True
    assert corrected.count("| On | Off | Duration |") == 1
    assert "**Note:**" not in corrected
    assert "not independently verified as complete" not in corrected
    assert "latest recorded state for Bathroom Light 1 is off" in corrected
    assert "I counted this afternoon from 12:00" in corrected
    assert "last recorded event was the 14:50 switch-off" in corrected

def test_live_0_16_112_safe_table_is_canonicalised_from_observed_intervals() -> None:
    draft = (
        "**Bathroom Light 1 was on for about 3 minutes in total this afternoon, "
        "across 2 recorded intervals.**\n\n"
        "| On | Off | Duration |\n"
        "| :--- | :--- | :--- |\n"
        "| 1:17 pm | 1:18 pm | 17s |\n"
        "| 2:47 pm | 2:50 pm | 3m |\n\n"
        "The latest recorded state for Bathroom Light 1 is off. "
        "I counted this afternoon from 12:00, and the last recorded event was "
        "the 14:50 switch-off."
    )

    corrected, changed = guard_history_duration_claim(
        draft,
        [_complete_afternoon_receipt()],
    )

    assert changed is True
    assert corrected.count("| On | Off | Duration |") == 1
    assert "| 13:17 | 13:18 | 17 sec |" in corrected
    assert "| 14:47 | 14:50 | 2 min 50 sec |" in corrected
    assert "| 1:17 pm | 1:18 pm | 17s |" not in corrected
    assert "| 2:47 pm | 2:50 pm | 3m |" not in corrected
    assert "latest recorded state for Bathroom Light 1 is off" in corrected
    assert "last recorded event was the 14:50 switch-off" in corrected


def test_safe_table_normalisation_preserves_unrelated_markdown_table() -> None:
    draft = (
        "**Bathroom Light 1 was on for about 3 minutes in total this afternoon, "
        "across 2 recorded intervals.**\n\n"
        "| On | Off | Duration |\n"
        "| --- | --- | ---: |\n"
        "| 1:17 pm | 1:18 pm | 17s |\n"
        "| 2:47 pm | 2:50 pm | 3m |\n\n"
        "| Observation | Meaning |\n"
        "| --- | --- |\n"
        "| Motion overlap | Correlation only |\n\n"
        "The latest recorded state for Bathroom Light 1 is off. "
        "I counted this afternoon from 12:00, and the last recorded event was "
        "the 14:50 switch-off."
    )

    corrected, changed = guard_history_duration_claim(
        draft,
        [_complete_afternoon_receipt()],
    )

    assert changed is True
    assert "| 14:47 | 14:50 | 2 min 50 sec |" in corrected
    assert "| Observation | Meaning |" in corrected
    assert "| Motion overlap | Correlation only |" in corrected

