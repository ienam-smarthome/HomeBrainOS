"""0.18.99: short factual usage answers and explicit midnight carry-over estimate.

Replay the observed TV switch intervals and predecessor/first OFF evidence
without converting an unverified event stream into an exact physical total.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from history_temporal_analysis import direct_recorded_duration_answer
from shared_investigation_completion import apply_shared_investigation_completion

QUESTION = "how long has the TV been on today?"


def tv_history():
    return {
        "tool": "homebrain_device_history", "success": True,
        "mutates": False, "effect": "read",
        "details": {
            "label": "TV", "attribute": "switch", "timeWindow": {"kind": "today"},
            "temporalAnalysis": {
                "activeState": "on", "inactiveState": "off",
                "windowed": True, "windowLabel": "today",
                "windowOngoing": True, "windowStart": "2026-10-24T00:00:00+01:00",
                "windowEnd": "2026-10-24T16:19:27+01:00",
                "pageCompleteToWindowStart": True,
                "sourceCompleteToWindowStart": True,
                "sourceIntegrityVerified": False,
                "sourceIntegrity": "unverified",
                "totalActiveSeconds": 6349,
                "completedActiveSeconds": 6349,
                "completedIntervalCount": 3,
                "intervalCount": 3,
                "openActiveInterval": False,
                "unboundedActiveInterval": False,
                "predecessorStateEvent": {
                    "timestamp": "2026-10-23T22:27:37.873+01:00",
                    "state": "on", "isStateChange": True,
                },
                "firstWindowStateEvent": {
                    "timestamp": "2026-10-24T00:12:54.553+01:00",
                    "state": "off", "isStateChange": True,
                },
                "lastWindowStateEvent": {
                    "timestamp": "2026-10-24T13:59:51.930+01:00",
                    "state": "off", "isStateChange": True,
                },
            },
        },
    }


def test_short_tv_answer_includes_midnight_estimate_without_physical_exactness():
    result = direct_recorded_duration_answer(QUESTION, [tv_history()])
    assert result is not None
    message, coverage = result
    assert "1 hour 59 minutes" in message
    assert "13 minutes" in message
    assert "1 hour 46 minutes" in message
    assert "3 recorded daytime periods" in message
    assert "latest recorded state is **off**" in message
    assert "inferred" in message
    assert "missing transitions cannot be ruled out" in message
    assert coverage["observedCompletedSeconds"] == 6349
    assert coverage["estimatedCarryoverSeconds"] == 775
    assert coverage["estimatedCombinedSeconds"] == 7124
    assert coverage["eventStreamIntegrityVerified"] is False
    assert coverage["causalAttributionAttempted"] is False


def test_plain_duration_request_does_not_get_competing_explanations_or_causal_gaps():
    outcome = SimpleNamespace(
        message="The TV has been on 1h46m.",
        route="unified-mcp-agent", request_class="live-read",
        metrics={"outcome": "unresolved", "counters": {}},
        evidence=[tv_history()],
        investigation_coverage={
            "hypothesisComparisons": [
                {"candidate": "single continuous session"},
                {"candidate": "multiple sessions"},
            ],
        },
    )
    answer = apply_shared_investigation_completion(outcome, QUESTION)
    assert "1 hour 59 minutes" in answer.message
    assert "Competing explanations" not in answer.message
    assert "unchecked source classes" not in answer.message
    assert answer.investigation_coverage["domain"] == "temporal_duration"


def test_inferred_carryover_not_added_without_midnight_reaching_history():
    receipt = tv_history()
    receipt["details"]["temporalAnalysis"]["pageCompleteToWindowStart"] = False
    result = direct_recorded_duration_answer(QUESTION, [receipt])
    assert result is not None
    message, coverage = result
    assert "1 hour 46 minutes" in message
    assert "1 hour 59 minutes" not in message
    assert coverage["estimatedCarryoverSeconds"] == 0


def test_causal_question_and_multiple_history_targets_are_not_overridden():
    assert direct_recorded_duration_answer(
        "Why did the TV turn off at 13:59?", [tv_history()],
    ) is None
    assert direct_recorded_duration_answer(
        "Investigate the TV usage automation", [tv_history()],
    ) is None
    assert direct_recorded_duration_answer(
        QUESTION, [tv_history(), tv_history()],
    ) is None


def test_missing_valid_predecessor_does_not_create_carryover():
    receipt = tv_history()
    receipt["details"]["temporalAnalysis"]["predecessorStateEvent"] = None
    result = direct_recorded_duration_answer(QUESTION, [receipt])
    assert result is not None
    message, meta = result
    assert meta["estimatedCarryoverSeconds"] == 0
    assert "about 1 hour 46 minutes today" in message


def test_internal_hypotheses_remain_hidden_unless_the_user_requests_them():
    src = (APP / "shared_investigation_completion.py").read_text(encoding="utf-8")
    assert "requested_hypotheses" in src
    assert "if isinstance(proposed, list) and proposed and requested_hypotheses" in src
