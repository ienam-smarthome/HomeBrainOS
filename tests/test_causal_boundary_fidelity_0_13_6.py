from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    controller_boundary_alignments,
    controller_transition_alignments,
    render_controller_alignment_instruction,
)
from causal_timeline import build_causal_timeline_rows, render_causal_timeline  # noqa: E402
from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from history_temporal_analysis import (  # noqa: E402
    analyze_state_intervals_in_window,
    history_temporal_evidence_details,
)
from request_metrics import RequestMetrics  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


def _live_subject_history() -> dict:
    return {
        "label": "Bedroom 3 Light",
        "room": "Bedroom 3",
        "attribute": "switch",
        "temporalAnalysis": {
            "activeState": "on",
            "inactiveState": "off",
            "observedIntervals": [
                {
                    "start": "2026-09-18T23:10:11.047+0100",
                    "end": "2026-09-18T23:10:13.878+0100",
                    "startNatural": "11:10 pm on Friday 18 September 2026",
                    "endNatural": "11:10 pm on Friday 18 September 2026",
                    "durationSeconds": 3,
                    "duration": "3s",
                }
            ],
        },
    }


def _controller_history() -> dict:
    return {
        "label": "Bedroom 3 dimmer - 1",
        "attribute": "pushed",
        "events": [
            {
                "name": "pushed",
                "value": "1",
                "description": "Bedroom 3 dimmer - 1 button 1 was pushed [physical]",
                "date": "2026-09-18T23:10:13.932+0100",
                "isStateChange": True,
            }
        ],
    }


def _boundary_evidence() -> list[dict]:
    return [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": _live_subject_history(),
        },
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": {
                "label": "Bedroom 3 dimmer - 1",
                "attribute": "pushed",
                "observedEvents": _controller_history()["events"],
            },
        },
    ]


def test_controller_event_near_interval_end_is_not_turn_on_alignment() -> None:
    boundary = controller_boundary_alignments(
        _live_subject_history(),
        _controller_history(),
    )
    starts = controller_transition_alignments(
        _live_subject_history(),
        _controller_history(),
    )

    assert len(boundary) == 1
    assert boundary[0]["boundaryRole"] == "end"
    assert boundary[0]["deltaSeconds"] < 0.1
    assert boundary[0]["signedDeltaSeconds"] > 0
    assert starts == []

    instruction = render_controller_alignment_instruction(boundary)
    assert instruction is not None
    assert "END boundary" in instruction
    assert "must not be used as evidence that it caused the earlier turn-on" in instruction


def test_causal_timeline_keeps_end_controller_evidence_separate_from_trigger() -> None:
    rows = build_causal_timeline_rows(_boundary_evidence())

    assert len(rows) == 1
    row = rows[0]
    assert row["triggerStatus"] == "unresolved"
    assert row["triggerEvidence"] == []
    assert len(row["endControllerEvidence"]) == 1
    assert row["endControllerEvidence"][0]["boundaryRole"] == "end"

    rendered = render_causal_timeline(_boundary_evidence())
    assert rendered is not None
    assert "end-controller:" in rendered
    assert "start-provenance:" not in rendered
    assert "must never be used as the cause of the earlier turn-on" in rendered


def test_synthesis_validator_repairs_end_boundary_push_as_turn_on_provenance() -> None:
    draft = (
        "At 11:10 pm the light turned on briefly. "
        "This correlates with a physical push of Bedroom 3 dimmer - 1 at 11:10 pm."
    )

    corrected, issues = validate_synthesis(
        draft,
        _boundary_evidence(),
        causal=True,
    )

    assert "controller_boundary_direction" in issues
    assert "end/turn-off boundary, not the start" in corrected
    assert "caused that turn-on" in corrected


def test_open_active_interval_is_preserved_without_inventing_duration() -> None:
    london = ZoneInfo("Europe/London")
    temporal = analyze_state_intervals_in_window(
        "switch",
        [
            {
                "name": "switch",
                "value": "on",
                "date": "2026-09-19T00:01:59.306+0100",
                "isStateChange": True,
            },
            {
                "name": "switch",
                "value": "off",
                "date": "2026-09-19T00:00:01.762+0100",
                "isStateChange": True,
            },
        ],
        start=datetime(2026, 9, 18, 18, 0, tzinfo=london),
        end=datetime(2026, 9, 19, 0, 23, 25, tzinfo=london),
        window_label="last night",
        source_complete_to_start=True,
        window_ongoing=True,
        source_integrity_verified=False,
    )

    assert temporal is not None
    assert temporal["intervalCount"] == 0
    assert temporal["unboundedActiveInterval"] is True
    assert temporal["openActiveInterval"] is True
    assert temporal["openActiveStart"].startswith("2026-09-19T00:01:59")
    assert temporal["openActiveStartNatural"].startswith("12:01 am")

    details = history_temporal_evidence_details({
        "label": "Bedroom 3 Light",
        "attribute": "switch",
        "hoursBack": 24,
        "timeWindow": {
            "kind": "last_night",
            "label": "last night",
            "start": "2026-09-18T18:00:00+01:00",
            "end": "2026-09-19T00:23:25+01:00",
            "ongoing": True,
        },
        "temporalAnalysis": temporal,
        "events": [],
    })
    assert details is not None
    assert details["temporalAnalysis"]["openActiveInterval"] is True
    assert details["temporalAnalysis"]["openActiveStart"].startswith(
        "2026-09-19T00:01:59"
    )

    evidence = [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": details,
    }]
    timeline = build_causal_timeline_rows(evidence)
    assert len(timeline) == 1
    assert timeline[0]["open"] is True
    assert timeline[0]["material"] is True
    assert timeline[0]["duration"] is None

    rendered = render_causal_timeline(evidence)
    assert rendered is not None
    assert "[MATERIAL OPEN]" in rendered
    assert "duration=not established" in rendered

    ledger = build_current_turn_evidence_ledger(evidence)
    assert ledger is not None
    assert "ongoing-window open interval" in ledger
    assert "do not infer its duration" in ledger


def test_causal_app_navigation_metric_is_supported() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_app_navigation")
        assert metrics.snapshot()["counters"]["causal_app_navigation"] == 1
    finally:
        metrics.reset(token)
