"""Live v0.17.75 regression: a command survives after its focal ON is evicted.

Restoring exact-window state history must not require an existing history
interval, and a mere ON command must never be upgraded to proven causation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from test_homebrain_skills_framework_0_17_69 import _case, QUESTION
from causal_evidence_graph import build_causal_evidence_graph
from skill_focal_window import build_focal_source_plan, project_focal_state_result, render_unverified_focal_outcome
from skill_grounded_answer import render_grounded_causal_answer


def _evicted():
    rows = _case()
    rows[0]["details"]["temporalAnalysis"]["observedIntervals"] = [{
        "start": "2026-10-14T22:45:47.671+0100",
        "end": "2026-10-14T22:49:43.442+0100",
        "durationSeconds": 236,
    }]
    rows[0]["details"]["correlationEvents"] = []
    assert build_causal_evidence_graph(rows, QUESTION)["scope"] == "ambiguous-or-unobserved-event"
    return rows


def _response(plan, events):
    projected = project_focal_state_result({"events": events}, plan)
    return {
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "evidence_kind": "focal_exact_state_history",
        "arguments": {"tool": "hub_list_device_events", "args": plan["stateRead"]},
        "details": projected,
    }


def test_plan_exact_incident_when_focal_on_evicted_from_recent_history():
    plan = build_focal_source_plan(_evicted(), QUESTION)
    assert plan is not None
    assert plan["subject"] == "Livingroom Light 1"
    assert plan["deviceId"] == "7805"
    assert plan["producerAppId"] == "4129"
    assert plan["requestedMinuteOnly"] is True
    assert plan["observedBoundaryVerified"] is False
    assert plan["stateRead"]["since"] == "2026-10-14T18:54:36.691Z"
    assert plan["stateRead"]["until"] == "2026-10-14T18:56:00.000Z"
    assert plan["producerLogRead"]["appId"] == 4129


def test_scoped_read_recovers_off_and_on_and_becomes_graph_focal_event():
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    scoped = _response(plan, [
        {"name": "switch", "value": "off",
         "date": "2026-10-14T19:54:57.946+0100",
         "producedBy": {"label": "Matter Hue Bridge Pro", "type": "device"}},
        {"name": "switch", "value": "on",
         "date": "2026-10-14T19:55:00.049+0100",
         "producedBy": {"label": "Matter Hue Bridge Pro", "type": "device"}},
    ])
    assert scoped["details"]["sourceVerifiedOn"] is True
    combined = rows + [scoped]
    graph = build_causal_evidence_graph(combined, QUESTION)
    assert graph["scope"] == "single-observed-event"
    assert graph["focus"]["on"].endswith("19:55:00.049+0100")
    answer = render_grounded_causal_answer(combined, QUESTION)
    assert answer is not None
    assert "SenseCap D1 Settings" in answer
    assert "19:54:57.946" in answer
    assert "13.358" in answer
    assert "not a confirmed cause" in answer
    assert "Matter Hue Bridge Pro" in answer


def test_empty_historical_page_does_not_fabricate_on_or_cause():
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    combined = rows + [_response(plan, [])]
    assert combined[-1]["details"]["sourceVerifiedOn"] is False
    assert build_causal_evidence_graph(combined, QUESTION)["scope"] == "ambiguous-or-unobserved-event"
    assert render_grounded_causal_answer(combined, QUESTION) is None


def test_two_on_events_in_requested_minute_remain_ambiguous():
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    combined = rows + [_response(plan, [
        {"name": "switch", "value": "on",
         "date": "2026-10-14T19:55:00.049+0100"},
        {"name": "switch", "value": "on",
         "date": "2026-10-14T19:55:25.000+0100"},
    ])]
    assert combined[-1]["details"]["sourceVerifiedOn"] is False
    assert build_causal_evidence_graph(combined, QUESTION)["scope"] == "ambiguous-or-unobserved-event"
    assert render_grounded_causal_answer(combined, QUESTION) is None


def test_ambiguous_device_or_missing_historical_date_cannot_trigger_reads():
    rows = _evicted()
    rows.append({
        "success": True, "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "arguments": {"tool": "hub_list_device_events", "args": {"deviceId": "9999"}},
        "details": {"label": "Livingroom Light 1", "events": []},
    })
    assert build_focal_source_plan(rows, QUESTION) is None
    assert build_focal_source_plan(_evicted(), "Why did Livingroom Light 1 turn ON?") is None


def test_correct_native_utc_interval_is_not_requeried():
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    rows.append(_response(plan, [
        {"name": "switch", "value": "on",
         "date": "2026-10-14T19:55:00.049+0100"},
    ]))
    rows.append({
        "success": True, "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "arguments": {"tool": "hub_get_logs", "args": plan["producerLogRead"]},
        "details": {"logCount": 0},
    })
    final = build_focal_source_plan(rows, QUESTION)
    assert final["stateRead"] is None
    assert final["producerLogRead"] is None


def test_unverified_history_yields_safe_answer_without_claiming_automation_cause():
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    rows.append(_response(plan, []))
    result = render_unverified_focal_outcome(plan, rows, QUESTION)
    assert result is not None
    assert "Historical ON not independently verified" in result
    assert "SenseCap D1 Settings" in result
    assert "19:54:46.691" in result
    assert "not proof" in result
    assert "did not establish exactly one ON" in result
    assert "Next read-only checks" in result
    assert "direct cause" not in result
    assert render_unverified_focal_outcome(
        build_focal_source_plan(_case(), QUESTION), _case(), QUESTION,
    ) is None


def test_recovered_actual_focal_on_disables_fail_closed_stop():
    rows = _evicted()
    plan = build_focal_source_plan(rows, QUESTION)
    rows.append(_response(plan, [
        {"name": "switch", "value": "on",
         "date": "2026-10-14T19:55:00.049+0100"},
    ]))
    assert render_unverified_focal_outcome(plan, rows, QUESTION) is None


def test_wrong_calendar_date_and_unrelated_older_command_do_not_seed_history():
    rows = _evicted()
    assert build_focal_source_plan(
        rows, "Why did Livingroom Light 1 turn ON at 19:55 on 13 October 2026?"
    ) is None
    assert build_focal_source_plan(
        rows, "Why did Livingroom Light 1 turn ON at 12:00 on 14 October 2026?"
    ) is None
