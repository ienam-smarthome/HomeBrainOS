from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_timeline import (  # noqa: E402
    build_causal_timeline_rows,
    missing_material_timeline_rows,
    render_causal_timeline,
    render_command_source_followup,
)
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


def _evidence() -> list[dict]:
    return [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "evidence_kind": "deterministic_device_event_history",
            "details": {
                "label": "Bedroom 3 Light",
                "room": "Bedroom 3",
                "attribute": "switch",
                "temporalAnalysis": {
                    "intervalCount": 4,
                    "totalActiveDuration": "1h 43m",
                    "durationReliability": "unverified-event-stream",
                    "observedIntervals": [
                        {
                            "start": "2026-09-17T23:56:17.933+01:00",
                            "end": "2026-09-17T23:59:16.581+01:00",
                            "startNatural": "11:56 pm on Thursday 17 September 2026",
                            "endNatural": "11:59 pm on Thursday 17 September 2026",
                            "duration": "3m",
                            "durationSeconds": 179,
                        },
                        {
                            "start": "2026-09-17T23:59:18.852+01:00",
                            "end": "2026-09-18T00:00:21.389+01:00",
                            "startNatural": "11:59 pm on Thursday 17 September 2026",
                            "endNatural": "12:00 am on Friday 18 September 2026",
                            "duration": "1m",
                            "durationSeconds": 63,
                        },
                        {
                            "start": "2026-09-18T00:02:53.713+01:00",
                            "end": "2026-09-18T01:30:07.971+01:00",
                            "startNatural": "12:02 am on Friday 18 September 2026",
                            "endNatural": "1:30 am on Friday 18 September 2026",
                            "duration": "1h 27m",
                            "durationSeconds": 5234,
                        },
                        {
                            "start": "2026-09-18T01:32:51.716+01:00",
                            "end": "2026-09-18T01:45:02.397+01:00",
                            "startNatural": "1:32 am on Friday 18 September 2026",
                            "endNatural": "1:45 am on Friday 18 September 2026",
                            "duration": "12m",
                            "durationSeconds": 731,
                        },
                    ],
                },
                "observedEvents": [
                    {
                        "name": "command-off",
                        "description": "Command called: off()",
                        "date": "2026-09-18T01:45:01.779+01:00",
                    },
                    {
                        "name": "command-setLevel",
                        "description": "Command called: setLevel(15)",
                        "date": "2026-09-18T01:32:51.812+01:00",
                    },
                    {
                        "name": "command-off",
                        "description": "Command called: off()",
                        "date": "2026-09-18T01:30:07.775+01:00",
                    },
                    {
                        "name": "command-setLevel",
                        "description": "Command called: setLevel(15)",
                        "date": "2026-09-18T01:30:04.695+01:00",
                    },
                    {
                        "name": "level",
                        "value": "60",
                        "description": "Bedroom 3 Light level is 60",
                        "date": "2026-09-18T00:02:57.097+01:00",
                    },
                ],
            },
        },
        {
            "tool": "homebrain_device_history",
            "success": True,
            "evidence_kind": "deterministic_device_event_history",
            "details": {
                "label": "Bedroom 3 dimmer - 1",
                "attribute": "pushed",
                "observedEvents": [
                    {
                        "name": "pushed",
                        "value": "1",
                        "description": (
                            "Bedroom 3 dimmer - 1 button 1 was pushed [physical]"
                        ),
                        "date": "2026-09-18T01:32:51.876+01:00",
                    },
                    {
                        "name": "pushed",
                        "value": "1",
                        "description": (
                            "Bedroom 3 dimmer - 1 button 1 was pushed [physical]"
                        ),
                        "date": "2026-09-18T00:02:53.840+01:00",
                    },
                ],
            },
        },
        {
            "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "success": True,
            "evidence_kind": "authoritative_location_event_history",
            "details": {
                "events": [
                    {
                        "name": "mode",
                        "value": "Late Night",
                        "description": "Hub C8 Pro is now in Late Night mode",
                        "date": "2026-09-18T01:30:02.403+01:00",
                    }
                ]
            },
        },
    ]


def test_causal_timeline_joins_both_physical_provenance_events() -> None:
    rows = build_causal_timeline_rows(_evidence())

    assert len(rows) == 4
    assert rows[2]["id"] == "T3"
    assert rows[2]["material"] is True
    assert rows[2]["triggerStatus"] == "aligned-controller-provenance"
    assert rows[2]["triggerEvidence"][0]["deltaSeconds"] < 0.2
    assert rows[2]["triggerEvidence"][0]["physicalMetadata"] is True
    assert rows[3]["triggerStatus"] == "aligned-controller-provenance"
    assert rows[3]["triggerEvidence"][0]["deltaSeconds"] < 0.2
    assert any(
        event["name"] == "command-off"
        for event in rows[2]["endCommands"]
    )


def test_causal_timeline_marks_short_unexplained_flickers_as_minor() -> None:
    rows = build_causal_timeline_rows(_evidence())

    assert rows[0]["material"] is False
    assert rows[0]["triggerStatus"] == "unresolved"
    assert rows[1]["material"] is False
    assert rows[1]["triggerStatus"] == "unresolved"


def test_rendered_timeline_exposes_every_material_interval_and_downstream_commands() -> None:
    timeline = render_causal_timeline(_evidence())

    assert timeline is not None
    assert "T3 [MATERIAL]" in timeline
    assert "12:02 am" in timeline
    assert "button 1 was pushed [physical]" in timeline
    assert "T4 [MATERIAL]" in timeline
    assert "1:32 am" in timeline
    assert "subject-end-command" in timeline
    assert "command-off" in timeline
    assert "Late Night" in timeline


def test_coverage_validator_detects_current_live_answer_shape_missing_long_interval() -> None:
    draft = (
        "The recorded rows contain 4 observed bounded on intervals. "
        "At 1:32 am the light was turned on by a physical press of button 1. "
        "There were a few brief flickers before midnight."
    )

    missing = missing_material_timeline_rows(draft, _evidence())

    assert [row["id"] for row in missing] == ["T3"]
    _corrected, issues = validate_synthesis(draft, _evidence())
    assert any(issue.startswith("causal_timeline_coverage:T3:") for issue in issues)


def test_coverage_validator_accepts_both_material_start_anchors() -> None:
    draft = (
        "At 12:02 am button 1 aligned with the long light-on interval. "
        "At 1:32 am button 1 aligned with the second material interval. "
        "The earlier brief flickers remain unexplained."
    )

    assert missing_material_timeline_rows(draft, _evidence()) == []


def test_boundary_commands_require_one_downstream_provenance_attempt() -> None:
    followup = render_command_source_followup(_evidence())

    assert followup is not None
    assert "issuing app/rule/source has not been checked" in followup
    assert "Do not revisit controller or environmental-sensor history" in followup

    evidence_with_logs = [
        *_evidence(),
        {
            "tool": "hub_read_diagnostics",
            "sub_tool": "hub_get_logs",
            "success": True,
            "summary": "checked logs",
        },
    ]
    assert render_command_source_followup(evidence_with_logs) is None


def test_list_apps_manifest_does_not_satisfy_downstream_provenance_slot() -> None:
    evidence = [
        {
            "tool": "hub_read_apps_code",
            "sub_tool": "hub_list_apps",
            "success": True,
            "summary": "apps listed",
        },
        *_evidence(),
    ]

    assert render_command_source_followup(evidence) is not None


def test_final_coordinator_repairs_draft_that_omits_material_causal_row() -> None:
    calls: list[list[dict]] = []
    replies = iter([
        {
            "content": (
                "At 1:32 am a physical button-1 event aligned with the light-on "
                "transition. Earlier brief flickers were also recorded."
            )
        },
        {
            "content": (
                "At 12:02 am a physical button-1 event aligned with the start of "
                "the 1h27 recorded interval. At 1:32 am another physical button-1 "
                "event aligned with the second material interval. The brief "
                "pre-midnight flickers remain unexplained."
            )
        },
    ])

    async def chat(messages, tools):
        assert tools == []
        calls.append(messages)
        return next(replies)

    coordinator = FinalAnswerCoordinator(
        chat,
        evidence_supplier=lambda: _evidence(),
    )
    answer = asyncio.run(coordinator.answer([
        {
            "role": "user",
            "content": "Why was Bedroom 3 Light on during the night?",
        }
    ]))

    assert len(calls) == 2
    first_context = "\n".join(
        str(item.get("content") or "") for item in calls[0]
    )
    assert "HOST CAUSAL TIMELINE" in first_context
    assert "T3 [MATERIAL]" in first_context
    assert "T4 [MATERIAL]" in first_context
    repair_context = "\n".join(
        str(item.get("content") or "") for item in calls[1]
    )
    assert "causal_timeline_coverage:T3:" in repair_context
    assert "12:02 am" in answer
    assert "1:32 am" in answer
