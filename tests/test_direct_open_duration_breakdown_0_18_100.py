"""0.18.100: live 16:49 TV example includes an ongoing switch-on interval.

This regression verifies both the customer-facing table and machine metrics.
All observations are synthetic copies of the user's live read-only receipt.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from history_temporal_analysis import direct_recorded_duration_answer
from shared_investigation_completion import apply_shared_investigation_completion
from test_direct_temporal_tv_answer_0_18_99 import tv_history, QUESTION


def live_1649_receipt():
    receipt = deepcopy(tv_history())
    analysis = receipt["details"]["temporalAnalysis"]
    analysis.update({
        "windowEnd": "2026-10-24T16:49:08.185147+01:00",
        "openActiveInterval": True,
        "unboundedActiveInterval": True,
        "openActiveSeconds": 709,
        "openActiveStart": "2026-10-24T16:37:19.268+0100",
        "openActiveEffectiveStart": "2026-10-24T16:37:19.268000+01:00",
        "openActiveStartedBeforeWindow": False,
        "lastWindowStateEvent": {
            "state": "on", "isStateChange": True,
            "timestamp": "2026-10-24T16:37:19.268000+01:00",
        },
        "observedIntervals": [
            {"start": "2026-10-24T11:36:24.600+0100",
             "end": "2026-10-24T11:39:57.388+0100",
             "durationSeconds": 213},
            {"start": "2026-10-24T11:41:11.694+0100",
             "end": "2026-10-24T12:14:41.563+0100",
             "durationSeconds": 2010},
            {"start": "2026-10-24T12:51:06.291+0100",
             "end": "2026-10-24T13:59:51.930+0100",
             "durationSeconds": 4126},
        ],
        "observedIntervalsTruncated": False,
    })
    return receipt


def test_1649_answer_includes_all_five_periods_and_current_on_state():
    rendered = direct_recorded_duration_answer(QUESTION, [live_1649_receipt()])
    assert rendered is not None
    message, coverage = rendered
    assert "**The TV has been on for approximately 2 hours 11 minutes today, as of 16:49.**" in message
    assert "| On | Off | Duration |" in message
    for snippet in (
        "| 00:00 (from last night) | 00:12 | ~13m |",
        "| 11:36 | 11:39 | 4m |",
        "| 11:41 | 12:14 | 34m |",
        "| 12:51 | 13:59 | 1h 9m |",
        "| 16:37 | Still on | ~12m so far |",
        "**Latest recorded state: ON** (since 16:37)",
    ):
        assert snippet in message
    assert "Competing explanations" not in message
    assert "Investigation completeness" not in message
    assert coverage["observedCompletedSeconds"] == 6349
    assert coverage["observedOpenSeconds"] == 709
    assert coverage["estimatedCarryoverSeconds"] == 775
    assert coverage["estimatedCombinedSeconds"] == 7833
    assert coverage["breakdownRowCount"] == 5
    assert coverage["breakdownCompleteForEstimatedTotal"] is True
    assert coverage["eventStreamIntegrityVerified"] is False


def test_1649_api_final_answer_removes_spurious_unresolved_tag():
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message=("The TV has been on for an estimated 1 hour and 46 minutes. "
                 "Investigation completeness: partial; unchecked command history."),
        metrics={
            "outcome": "unresolved",
            "counters": {"model_rounds": 3, "evidence_sufficiency_stop": 1},
        },
        investigation_coverage={"domain": "causal_provenance"},
        evidence=[live_1649_receipt()],
    )
    result = apply_shared_investigation_completion(outcome, QUESTION)
    assert "2 hours 11 minutes" in result.message
    assert "Still on" in result.message
    assert "Investigation completeness" not in result.message
    assert "command history" not in result.message
    assert result.metrics["outcome"] == "success"
    assert result.investigation_coverage["domain"] == "temporal_duration"
    assert result.investigation_coverage["status"] == "bounded-estimate"


def test_device_duration_works_without_tv_specific_hardcoding():
    item = live_1649_receipt()
    item["details"]["label"] = "Bedroom 2 Fan"
    result = direct_recorded_duration_answer(
        "How long has the Bedroom 2 Fan been on today?", [item],
    )
    assert result is not None
    assert "**Bedroom 2 Fan has been on" in result[0]
    assert result[1]["breakdownRowCount"] == 5


def test_open_duration_cannot_exceed_or_conflict_with_asof_clock():
    item = live_1649_receipt()
    item["details"]["temporalAnalysis"]["openActiveSeconds"] = 6000
    assert direct_recorded_duration_answer(QUESTION, [item]) is None
    item = live_1649_receipt()
    item["details"]["temporalAnalysis"]["lastWindowStateEvent"]["state"] = "off"
    assert direct_recorded_duration_answer(QUESTION, [item]) is None


def test_unverified_causal_response_cannot_be_marked_success():
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="No sufficient evidence", evidence=[live_1649_receipt()],
        metrics={"outcome": "unresolved",
                 "counters": {"task_evidence_incomplete": 1}},
        investigation_coverage=None,
    )
    result = apply_shared_investigation_completion(outcome, QUESTION)
    assert result.metrics["outcome"] == "unresolved"


def test_malformed_or_missing_interval_rows_no_fabricated_table():
    item = live_1649_receipt()
    item["details"]["temporalAnalysis"]["observedIntervals"] = [
        {"start": "2026-10-24T09:00:00+0100",
         "end": "2026-10-24T09:05:00+0100",
         "durationSeconds": 213},
    ]
    result = direct_recorded_duration_answer(QUESTION, [item])
    assert result is not None
    assert "| On | Off | Duration |" not in result[0]
    assert result[1]["breakdownCompleteForEstimatedTotal"] is False
