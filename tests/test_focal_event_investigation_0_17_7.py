"""A one-event question must never drift to earlier recorded intervals."""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_timeline import (  # noqa: E402
    causal_log_windows,
    explicitly_focused_event_rows,
    missing_material_timeline_rows,
    render_causal_timeline,
)
from final_answer_coordinator import _synthesis_instruction  # noqa: E402
from mcp_agent_orchestrator import _normalize_causal_log_call  # noqa: E402


def observed_evidence():
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Example Light",
            "attribute": "switch",
            "temporalAnalysis": {
                "intervalCount": 2,
                "observedIntervals": [
                    {"start": "2026-10-12T07:08:06.273+0100",
                     "end": "2026-10-12T07:25:16.174+0100",
                     "durationSeconds": 1030, "duration": "17m"},
                    {"start": "2026-10-12T07:53:36.721+0100",
                     "end": "2026-10-12T08:10:58.185+0100",
                     "durationSeconds": 1041, "duration": "17m"},
                ],
            },
        },
    }]


def test_specific_event_selects_the_observed_focal_boundary_only():
    evidence = observed_evidence()
    question = "Investigate thoroughly why Example Light turned on at 07:53:36 on 12 October."
    rows = explicitly_focused_event_rows(evidence, question)
    assert len(rows) == 1
    assert rows[0]["start"].startswith("2026-10-12T07:53:36")
    rendered = render_causal_timeline(evidence, original_user=question)
    assert "07:53:36" in rendered
    assert "07:08:06" not in rendered
    assert missing_material_timeline_rows(
        "The light turned on at 07:53:36 because...", evidence,
        original_user=question,
    ) == []


def test_focal_log_read_does_not_cycle_to_other_intervals_after_prefetch():
    evidence = observed_evidence()
    question = "Why did Example Light turn on at 07:53:36?"
    evidence.append({
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "arguments": {"tool": "hub_get_logs",
            "args": {"since": "2026-10-12T06:53:24Z"}}
    })
    windows = causal_log_windows(evidence, original_user=question)
    assert len(windows) == 1
    assert windows[0]["since"].startswith("2026-10-12T06:53:26")
    amended = _normalize_causal_log_call(
        "hub_read_diagnostics",
        {"tool": "hub_get_logs", "args": {"appId": 4013, "limit": 60}},
        evidence,
        original_user=question,
    )
    assert amended["args"]["since"].startswith("2026-10-12T06:53:26")
    assert amended["args"]["until"].startswith("2026-10-12T06:53:46")
    assert amended["args"]["appId"] == 4013


def test_unfocused_broad_history_keeps_all_material_intervals():
    evidence = observed_evidence()
    assert not explicitly_focused_event_rows(
        evidence, "Why did Example Light turn on today?"
    )
    assert "07:08:06" in render_causal_timeline(evidence)
    assert "07:53:36" in render_causal_timeline(evidence)
    assert len(causal_log_windows(evidence)) == 2


def test_ambiguous_clock_does_not_silently_select_a_history_boundary():
    evidence = observed_evidence()
    assert not explicitly_focused_event_rows(
        evidence, "Compare events at 07:08:06 and 07:53:36"
    )
    assert not explicitly_focused_event_rows(
        evidence, "At 07:53:37 no event was seen"
    )


def test_single_event_synthesis_does_not_require_full_day_timeline_table():
    focal = _synthesis_instruction(
        "Why did the light turn on at 07:53:36?", focused_event=True
    )
    assert "Analyse that event only" in focal
    assert "unrelated historical intervals" not in focal or "unexplained" in focal
    assert "prefer a compact Markdown table" not in focal
    broad = _synthesis_instruction("Why did the light turn on throughout today?")
    assert "Account for every MATERIAL row" in broad
    assert "prefer a compact Markdown table" in broad
