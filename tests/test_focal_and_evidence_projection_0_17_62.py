"""v0.17.62 regression for target-boundary provenance and typed diagnostics."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from causal_transition_provenance import focal_closed_transition
from causal_command_provenance import (
    prompt_focal_transition_boundary, boundary_producer_transition_match,
)
from recorded_telemetry_freshness import (
    assess_recorded_telemetry_freshness, render_command_only_evidence_answer,
)
from shared_investigation_completion import apply_shared_investigation_completion
from mcp_agent_orchestrator import AgentOutcome


def light_history():
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "arguments": {"name": "Livingroom Light 1", "attribute": "switch"},
        "details": {
            "label": "Livingroom Light 1",
            "temporalAnalysis": {
                "observedIntervals": [
                    {"start": "2026-10-14T19:54:46.871+0100",
                     "end": "2026-10-14T19:54:57.946+0100",
                     "durationSeconds": 11},
                    {"start": "2026-10-14T19:55:00.049+0100",
                     "end": "2026-10-14T22:45:40.112+0100",
                     "durationSeconds": 10240},
                    {"start": "2026-10-14T22:45:47.671+0100",
                     "end": "2026-10-14T22:49:43.442+0100",
                     "durationSeconds": 236},
                ],
            },
            "boundaryEvents": [
                {"name": "switch", "value": "off",
                 "date": "2026-10-14T19:54:57.946+0100",
                 "producedBy": {"label": "Matter Hue Bridge Pro", "type": "device"}},
                {"name": "switch", "value": "off",
                 "date": "2026-10-14T22:45:40.112+0100",
                 "producedBy": {"label": "Matter Hue Bridge Pro", "type": "device"}},
            ],
        },
    }]


QUESTION = (
    "Investigate why Livingroom Light 1 turned on at 19:55 "
    "on 14 October 2026. Read-only."
)


def test_explicit_on_previous_off_is_not_later_closing_off():
    rows = light_history()
    focus = focal_closed_transition(
        rows, QUESTION, requested_transition="on",
        resolved_device_id="7805",
    )
    assert focus is not None
    assert focus["deviceId"] == "7805"
    assert focus["end"] == "2026-10-14T19:54:57.946+0100"
    assert focus["start"] == "2026-10-14T19:54:46.871+0100"
    assert focus["offStateEvent"]["date"] == focus["end"]
    assert "22:45:40" not in focus["end"]


def test_off_question_remains_anchored_to_its_explicit_end():
    focus = focal_closed_transition(
        light_history(),
        "Why did Livingroom Light 1 switch off at 22:45:40 "
        "on 14 October 2026?",
        requested_transition="off", resolved_device_id="7805",
    )
    assert focus is not None
    assert focus["end"] == "2026-10-14T22:45:40.112+0100"


def test_producer_correlation_requires_matching_requested_on_boundary():
    boundary = prompt_focal_transition_boundary(
        light_history(), "on", QUESTION,
    )
    assert boundary is not None and "19:55:00" in boundary
    producers = [
        {"boundaryRole": "start", "action": "on",
         "subject": "Livingroom Light 1",
         "stateBoundary": "2026-10-14T22:45:47.671+0100",
         "producer": {"type": "device", "label": "Matter Hue Bridge Pro"}},
        {"boundaryRole": "start", "action": "on",
         "subject": "Livingroom Light 1",
         "stateBoundary": "2026-10-14T19:55:00.049+0100",
         "producer": {"type": "device", "label": "Matter Hue Bridge Pro"}},
    ]
    selected = boundary_producer_transition_match(
        producers, "on", requested_boundary=boundary,
    )
    assert selected is not None
    assert "19:55:00.049" in selected["stateBoundary"]


def command_only_history():
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "timestamp": "2026-10-14T22:57:08.273876+00:00",
        "details": {
            "label": "Bedroom 3 Mesh",
            "hoursBack": 24,
            "historySourceIntegrityVerified": False,
            "observedEvents": [
                *([{"name": "command-on", "type": "command",
                    "date": "2026-10-14T03:08:49+0100",
                    "producedBy": {"label": "Ikea Rodret Dimmer", "type": "app"}}]
                  * 11),
                *([{"name": "command-refresh", "type": "command",
                    "date": "2026-10-14T12:00:05+0100",
                    "producedBy": {"label": "Device Health Monitor", "type": "app"}}]
                  * 2),
            ],
        },
    }]


def test_evidence_projection_replaces_unsupported_telemetry_claims():
    rows = command_only_history()
    assessment = assess_recorded_telemetry_freshness(rows)
    assert assessment is not None
    draft = (
        "### Investigation Results: Bedroom 3 Mesh\n"
        "**Reported State**\n"
        "* **Health Status:** Offline.\n"
        "* **Latest Cached State:** Switch is off.\n\n"
        "**Telemetry Activity**\n"
        "* **Last Seen:** Oct 12.\n"
        "* **Recent Activity:** Zero telemetry reported by the device.\n\n"
        "### Conclusions\n"
        "**Established**\n"
        "* **Telemetry Failure:** The device has not provided a telemetry "
        "update since October 12.\n"
        "* **Command Non-Response:** Commands produced zero state changes.\n"
    )
    projected = render_command_only_evidence_answer(draft, rows, assessment)
    assert projected is not None
    assert "**Health Status:** Offline." in projected
    assert "**Latest Cached State:** Switch is off." in projected
    assert "13 command invocations" in projected
    assert "Ikea Rodret Dimmer: 11 recorded on()" in projected
    assert "Device Health Monitor: 2 recorded refresh()" in projected
    assert "last actual incoming telemetry packet" in projected
    assert "since October 12" not in projected
    assert "Telemetry Failure" not in projected
    assert "Command Non-Response" not in projected
    assert "Root cause:** Not established" in projected


def test_shared_api_investigation_uses_projection_with_partial_status():
    rows = command_only_history()
    original = AgentOutcome(
        message="**Reported State**\n* **Health Status:** Offline.\n\n"
                "**Telemetry Activity**\nNo updates since October 12.\n",
        request_class="live-read", evidence=rows, choices=[],
    )
    guarded = apply_shared_investigation_completion(
        original,
        "Investigate Bedroom 3 Mesh. Check last telemetry activity, "
        "health status and recent device logs. Read-only.",
    )
    assert "13 command invocations" in guarded.message
    assert "No updates since October 12" not in guarded.message
    assert guarded.investigation_coverage["answerProjection"] == (
        "bounded-command-only-evidence"
    )
    assert guarded.metrics["outcome"] == "unresolved"
