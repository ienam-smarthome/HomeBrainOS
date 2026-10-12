"""Regression for model-led 0.17.7 Bathroom investigation: cross-domain validator
leakage, app-owned commands vs upstream manual triggers, and exact elapsed time.
All tests are device-agnostic; no installed Hubitat connection is required.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_timeline import guard_focal_interval_duration  # noqa: E402
from evidence_source_guard import guard_checked_source_absence_claim  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


QUESTION = (
    "Investigate thoroughly why Example Light turned on at 07:53:36 "
    "on 12 October. Check its automation, sensor and logs. Read-only."
)


def _evidence() -> list[dict]:
    return [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": {
                "label": "Example Light",
                "attribute": "switch",
                "temporalAnalysis": {
                    "intervalCount": 1,
                    "observedIntervals": [{
                        "start": "2026-10-12T07:53:36.721+0100",
                        "end": "2026-10-12T08:10:58.185+0100",
                        "durationSeconds": 1041,
                        "duration": "17m",
                    }],
                    "durationReliability": "bounded-pairs",
                },
                "commandEvents": [{
                    "name": "command-setLevel",
                    "date": "2026-10-12T07:53:36.621+0100",
                    "description": "Command called: setLevel(50)",
                    "producedBy": {
                        "label": "Example Lighting Automation",
                        "id": "1234",
                        "type": "app",
                    },
                }],
                "boundaryEvents": [{
                    "name": "switch",
                    "value": "on",
                    "date": "2026-10-12T07:53:36.721+0100",
                    "producedBy": {
                        "label": "Matter Bridge",
                        "id": "5555",
                        "type": "device",
                    },
                }],
            },
        },
        {
            "tool": "hub_read_diagnostics",
            "sub_tool": "hub_get_logs",
            "success": True,
            "evidence_kind": "native_log_history",
            "arguments": {
                "tool": "hub_get_logs",
                "args": {
                    "appId": "1234",
                    "since": "2026-10-12T06:53:24Z",
                    "until": "2026-10-12T06:53:42Z",
                    "limit": 60,
                },
            },
            "details": {
                "logCount": 0,
                "logs": [],
            },
        },
    ]


def test_empty_app_log_result_is_not_a_missing_performance_source():
    line = (
        "The app execution log search returned no entries in the event window."
    )
    fixed, changed = guard_checked_source_absence_claim(
        line, _evidence(), performance_request=False
    )
    assert fixed == line
    assert not changed
    assert "performance analysis" not in fixed


def test_causal_validation_does_not_insert_performance_advice_into_empty_log_result():
    draft = (
        "The controlling app issued the ON command. "
        "The targeted app log search returned no entries."
    )
    fixed, issues = validate_synthesis(
        draft, _evidence(), original_user=QUESTION, causal=True
    )
    assert "requested performance analysis" not in fixed
    assert "performance_" not in ",".join(issues)
    assert "returned no entries" in fixed


def test_performance_refusal_guard_still_corrects_real_unchecked_claims():
    line = "No logs were provided for the performance analysis."
    fixed, changed = guard_checked_source_absence_claim(
        line, _evidence(), performance_request=True
    )
    assert changed
    assert "Current-turn evidence did include" in fixed


def test_manual_upstream_exclusion_calibrated_without_losing_proven_app_command():
    draft = (
        "App 1234 issued setLevel(50) to turn the light on. \n"
        "* **Manual Control:** Ruled out; the final command came from the "
        "automation app and not a physical switch."
    )
    fixed, issues = validate_synthesis(
        draft, _evidence(), original_user=QUESTION, causal=True
    )
    assert "upstream_manual_exclusion" in issues
    assert "Ruled out" not in fixed
    assert "automation issued the device command" in fixed
    assert "manual input upstream" in fixed
    assert "App 1234" in fixed


def test_focal_duration_uses_observed_integer_seconds_not_model_rounding():
    draft = "The light switched off at 08:10:58 (recorded duration: ~17m 22s)."
    fixed, changed = guard_focal_interval_duration(draft, _evidence(), QUESTION)
    assert changed
    assert "17m 21s" in fixed
    assert "17m 22s" not in fixed

    through_validator, issues = validate_synthesis(
        draft, _evidence(), original_user=QUESTION, causal=True
    )
    assert "focal_interval_duration" in issues
    assert "17m 21s" in through_validator


def test_absent_or_multi_event_focus_does_not_rewrite_unrelated_durations():
    draft = "During yesterday's test the device remained on for 17m 22s."
    fixed, changed = guard_focal_interval_duration(
        draft, _evidence(), "Review the entire history of Example Light"
    )
    assert fixed == draft
    assert not changed
    multiple, changed = guard_focal_interval_duration(
        "An earlier interval was 10m 22s; this one was 17m 22s.",
        _evidence(), QUESTION
    )
    assert not changed
    assert "10m 22s" in multiple



def test_api_response_serializer_preserves_empty_logs_without_performance_leak():
    from types import SimpleNamespace
    from api_response_builder import build_agent_response

    outcome = SimpleNamespace(
        message=(
            "The lighting automation produced the ON command. "
            "A targeted app log search returned no entries."
        ),
        evidence=_evidence(),
        metrics={"outcome": "success", "counters": {"model_rounds": 3}},
        route="unified-mcp-agent",
        request_class="live-read",
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=500, version="0.17.8"
    )
    assert "targeted app log search returned no entries" in response["message"]
    assert "requested performance analysis" not in response["message"]
    assert "Current-turn evidence did include successful logs" not in response["message"]


def test_api_serializer_detects_performance_statistics_but_not_app_logs_as_domain():
    from evidence_source_guard import has_performance_evidence

    assert not has_performance_evidence(_evidence())
    with_statistics = _evidence() + [{
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "evidence_kind": "tool_result",
    }]
    assert has_performance_evidence(with_statistics)
    with_diagnostics = _evidence() + [{
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "evidence_kind": "host_planned_performance_diagnostic",
    }]
    assert has_performance_evidence(with_diagnostics)
