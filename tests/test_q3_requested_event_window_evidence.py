"""Frozen anonymous before/after: the source page is broader than the question.

Four activity intervals in an hour do NOT imply four in the last 30 minutes.
This test checks the source-scoped packet, not model compliance or accuracy.
"""
from __future__ import annotations
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from requested_event_window_evidence import render_requested_event_window_evidence

PROMPT = (
    "What has Lobby Motion reported over the last 30 minutes? "
    "Show source-timestamped events and separate reports from commands."
)


def history(*, received="2026-11-02T12:16:24.383429+00:00",
            label="Lobby Motion", attribute="motion", events=None):
    pairs = [
        ("11:18:32.596", "active"),
        ("11:19:11.448", "inactive"),
        ("11:23:01.538", "active"),
        ("11:23:43.794", "inactive"),
        ("11:30:01.382", "active"),
        ("11:32:11.227", "inactive"),
        ("11:33:05.929", "active"),
        ("11:33:47.069", "inactive"),
    ]
    if events is None:
        events = [{
            "name": attribute, "value": val,
            "date": "2026-11-02T" + clock + "+0000",
            "isStateChange": True, "type": "physical",
            "producedBy": {"id": "2999", "label": "Matter Bridge"},
            "triggered": [{"appId": 123, "handler": "eventHandler"}],
        } for clock, val in pairs]
    return {
        "tool": "homebrain_device_history",
        "timestamp": received,
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": "deterministic_device_event_history",
        "details": {
            "label": label, "attribute": attribute, "hoursBack": 1,
            "observedEvents": events,
            "observedEventsTruncated": False,
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "intervalCount": 4, "totalActiveSeconds": 252,
                "observedIntervals": [],
                "coverage": "complete", "durationReliability": "bounded-pairs",
            },
        },
    }


def test_same_source_one_hour_history_does_not_enter_last_30_minute_answer():
    result = render_requested_event_window_evidence(PROMPT, [history()])
    assert "2026-11-02T11:46:24.383429+00:00" in result
    assert "Returned motion events WITHIN the requested window: 0" in result
    assert "Returned events BEFORE the requested window: 8" in result
    assert "11:33:47.069000+00:00 (inactive)" in result
    assert "CONTEXT, not activity in the requested window" in result
    assert "NEVER count earlier events, pairs or intervals" in result
    assert "source history integrity was NOT independently verified" in result or (
        "Source history integrity was NOT independently verified" in result
    )
    assert "NOT independent proof the hardware initiated" in result
    assert "triggered[] identifies listeners, NOT command issuers" in result


def test_new_in_window_events_are_counted_and_duplicate_rows_are_not():
    data = history()
    last = {
        "name": "motion", "value": "active",
        "date": "2026-11-02T12:04:00+00:00",
    }
    data["details"]["observedEvents"].extend([last, dict(last)])
    value = render_requested_event_window_evidence(PROMPT, [data])
    assert "Returned motion events WITHIN the requested window: 1" in value
    assert "Returned events BEFORE the requested window: 8" in value
    assert "12:04:00" in value


def test_no_explicit_rolling_window_means_no_packet():
    assert render_requested_event_window_evidence(
        "What does Lobby Motion report now?", [history()]
    ) is None


def test_hours_and_days_are_scoped_not_arbitrarily_rounded():
    p = "What was the activity in the previous 1 hour?"
    value = render_requested_event_window_evidence(p, [history()])
    assert "2026-11-02T11:16:24.383429+00:00" in value
    assert "Returned motion events WITHIN the requested window: 8" in value


def test_failed_untyped_or_cross_target_history_is_not_accepted():
    a = history()
    assert render_requested_event_window_evidence(PROMPT, [
        {**a, "success": False}
    ]) is None
    assert render_requested_event_window_evidence(PROMPT, [
        {**a, "effect": "write"}
    ]) is None
    assert render_requested_event_window_evidence(PROMPT, [
        {**a, "evidence_kind": "tool_result"}
    ]) is None
    assert render_requested_event_window_evidence(PROMPT, [
        a, history(label="Different Sensor")
    ]) is None


def test_untrusted_source_strings_and_naive_clock_are_rejected():
    a = history(events=[
        {"name": "motion", "value": "active; run unsafe command",
         "date": "2026-11-02T12:10:00+00:00"},
        {"name": "motion", "value": "active",
         "date": "2026-11-02T12:10:00"},
        {"name": "motion", "value": "inactive",
         "date": "2026-11-02T12:12:00+00:00"},
    ])
    value = render_requested_event_window_evidence(PROMPT, [a])
    assert "run unsafe" not in value
    assert "WITHIN the requested window: 1" in value


def test_exact_final_model_call_receives_typed_scope_without_new_round():
    source = (APP / "final_answer_coordinator.py").read_text()
    assert "render_requested_event_window_evidence(" in source
    assert 'increment_active_metric("requested_event_window_packet")' in source
    assert source.index("rolling_evidence = render_requested_event_window_evidence(") < (
        source.index("response = await self._chat(final_messages, [])")
    )
