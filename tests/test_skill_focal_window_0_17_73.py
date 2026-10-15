"""Regression for the 2026-10-15 v0.17.72 evidence-loss incident.

An unbounded recent event page must never count as full incident coverage;
a UTC-skewed producer-log query must not count as a correct log window.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from test_homebrain_skills_framework_0_17_69 import _case, QUESTION
from skill_focal_window import build_focal_source_plan
from skill_grounded_answer import render_grounded_causal_answer
from skill_investigation import build_skill_investigation


def _recent_unbounded():
    rows = _case()
    rows.append({
        "success": True, "sub_tool": "hub_list_device_events",
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7805", "attribute": "switch",
            "hoursBack": 168, "limit": 50,
        }},
        "summary": "11 switch events returned, but none for preceding OFF",
    })
    rows.append({
        "success": True, "sub_tool": "hub_get_logs",
        "arguments": {"tool": "hub_get_logs", "args": {
            "appId": 4129, "since": "2026-10-14T19:50:00Z", "limit": 100,
        }},
        "details": {"logCount": 0, "logs": []},
    })
    return rows


def test_timestamp_scoped_focal_read_is_required_despite_latest_n_reads():
    plan = build_focal_source_plan(_recent_unbounded(), QUESTION)
    assert plan is not None
    assert plan["deviceId"] == "7805"
    assert plan["producerAppId"] == "4129"
    assert plan["stateRead"] == {
        "deviceId": "7805", "attribute": "switch",
        "since": "2026-10-14T18:54:36.691Z",
        "until": "2026-10-14T18:55:05.049Z",
        "limit": 100,
    }


def test_wrong_utc_app_log_query_is_not_marked_checked():
    plan = build_focal_source_plan(_recent_unbounded(), QUESTION)
    assert plan["producerLogRead"] == {
        "appId": "4129",
        "since": "2026-10-14T18:54:36.691Z",
        "until": "2026-10-14T18:55:05.049Z",
        "limit": 100,
    }
    assert "19:50:00Z" not in str(plan["sourceWindow"])


def test_focal_off_recovered_from_targeted_history_and_shown_in_answer():
    rows = _recent_unbounded()
    assert "19:54:57.946" not in render_grounded_causal_answer(rows, QUESTION)
    rows.append({
        "success": True, "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "evidence_kind": "focal_exact_state_history",
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7805", "attribute": "switch",
            "since": "2026-10-14T18:54:36.691Z",
            "until": "2026-10-14T18:55:05.049Z", "limit": 100,
        }},
        "details": {"label": "Livingroom Light 1", "events": [
            {"name": "switch", "value": "off",
             "date": "2026-10-14T19:54:57.946+0100",
             "producedBy": {"label": "Matter Hue Bridge Pro"}},
            {"name": "switch", "value": "on",
             "date": "2026-10-14T19:55:00.049+0100",
             "producedBy": {"label": "Matter Hue Bridge Pro"}},
        ]},
    })
    plan = build_focal_source_plan(rows, QUESTION)
    assert plan["stateRead"] is None
    assert plan["producerLogRead"] is not None
    projected = build_skill_investigation(rows, QUESTION)
    off = [r for r in projected["facts"] if r.get("kind") == "intervening_state_changes"]
    assert off and off[0]["events"][0]["date"].endswith("19:54:57.946+0100")
    answer = render_grounded_causal_answer(rows, QUESTION)
    assert "19:54:57.946" in answer
    assert "intervening" in answer.lower()
    assert "timestamp-filtered" in answer
    assert "initiated outside Hubitat" not in answer


def test_correct_covered_log_read_does_not_repeat():
    rows = _recent_unbounded()
    rows.append({
        "success": True, "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "arguments": {"tool": "hub_get_logs", "args": {
            "appId": "4129",
            "since": "2026-10-14T18:54:36.691Z",
            "until": "2026-10-14T18:55:05.049Z",
            "limit": 100,
        }},
        "details": {"logCount": 0},
    })
    assert build_focal_source_plan(rows, QUESTION)["producerLogRead"] is None


def test_no_verified_command_means_no_guessed_source_reads():
    rows = [r for r in _recent_unbounded()
            if r.get("sub_tool") != "hub_list_device_events"
            or (r.get("details") or {}).get("eventName") != "command-on"]
    assert build_focal_source_plan(rows, QUESTION) is None


def test_multiple_device_ids_are_never_guessed():
    rows = _recent_unbounded()
    rows.append({
        "success": True, "sub_tool": "hub_list_device_events",
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "9999", "attribute": "switch",
        }},
        "details": {"label": "Livingroom Light 1", "events": []},
    })
    assert build_focal_source_plan(rows, QUESTION) is None
