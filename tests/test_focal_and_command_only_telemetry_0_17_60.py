"""Historical focal time and command-only telemetry boundary regressions."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from causal_command_provenance import (
    focal_transition_boundary, prompt_focal_transition_boundary,
)
from causal_timeline import explicitly_focused_event_rows
from recorded_telemetry_freshness import (
    assess_recorded_telemetry_freshness, reconcile_telemetry_answer,
    render_temporal_qualification,
)


def _light_history():
    return [{
        "tool": "homebrain_device_history", "success": True,
        "arguments": {"name": "Livingroom Light 1", "attribute": "switch"},
        "details": {
            "label": "Livingroom Light 1",
            "attribute": "switch",
            "temporalAnalysis": {
                "observedIntervals": [
                    {"start": "2026-10-14T19:55:00.049+0100",
                     "end": "2026-10-14T22:45:40.112+0100",
                     "durationSeconds": 10240},
                    {"start": "2026-10-14T22:45:47.671+0100",
                     "end": "2026-10-14T22:49:43.442+0100",
                     "durationSeconds": 236},
                ],
            },
        },
    }]


def _command_only():
    return [{
        "tool": "homebrain_device_history",
        "timestamp": "2026-10-14T21:49:23.387428+00:00",
        "success": True,
        "details": {
            "label": "Bedroom 3 Mesh", "attribute": None,
            "hoursBack": 24,
            "observedEventsTruncated": False,
            "historySourceIntegrityVerified": False,
            "observedEvents": [
                {"name": "command-refresh", "type": "command",
                 "date": "2026-10-14T18:00:04.909+0100",
                 "producedBy": {
                     "id": "4072", "label": "Device Health Monitor", "type": "app",
                 }},
                {"name": "command-on", "type": "command",
                 "date": "2026-10-14T03:42:21.477+0100",
                 "producedBy": {
                     "id": "3103", "label": "Ikea Rodret Dimmer", "type": "app",
                 }},
            ],
        },
    }]


def test_explicit_1955_on_does_not_switch_to_latest_2245_on():
    evidence = _light_history()
    assert "22:45:47.671" in focal_transition_boundary(evidence, "on")
    requested = (
        "Investigate why Livingroom Light 1 turned on at 19:55 "
        "on 14 October 2026. Read-only."
    )
    selected = prompt_focal_transition_boundary(evidence, "on", requested)
    assert selected == "2026-10-14T19:55:00.049+0100"
    assert len(explicitly_focused_event_rows(
        evidence, requested, transition="on",
    )) == 1
    assert prompt_focal_transition_boundary(
        evidence, "off", requested,
    ) is None


def test_missing_explicit_time_never_falls_back_to_newest():
    evidence = _light_history()
    assert prompt_focal_transition_boundary(
        evidence, "on",
        "Why did Livingroom Light 1 turn on at 19:56 on 14 October 2026?",
    ) is None
    assert "22:45:47.671" in prompt_focal_transition_boundary(
        evidence, "on",
        "Why did Livingroom Light 1 turn on recently?",
    )


def test_command_only_history_still_gets_timestamp_evidence_assessment():
    observed = assess_recorded_telemetry_freshness(_command_only())
    assert observed is not None
    assert observed["device"] == "Bedroom 3 Mesh"
    assert observed["onlyCommandEventsInReturnedWindow"] is True
    assert observed["sourceWindowHours"] == 24
    assert observed["observedCommandEvents"] == 2
    assert observed["latestReturnedDeviceAttributedEventAt"] is None
    assert observed["physicalTelemetryVerified"] is False
    assert "command invocations only" in render_temporal_qualification(
        observed, "",
    )


def test_command_only_history_reconciles_unproven_physical_silence_and_age():
    assessment = assess_recorded_telemetry_freshness(_command_only())
    text = (
        "**Telemetry Activity**\n"
        "*   **Data Age:** Approximately 45 hours (162,325 seconds).\n"
        "*   **Recent Activity (Last 24h):** No telemetry or state changes "
        "were received from the device.\n"
        "*   **Health Conflict:** There is a discrepancy between the "
        "connected MQTT status and the offline health status.\n"
        "*   **Communication is one-way:** The hub is actively sending "
        "commands but the device is not responding with state updates.\n"
        "*   **Telemetry is stale:** The device has not reported a state "
        "change or telemetry update in over 45 hours.\n"
    )
    corrected, changed = reconcile_telemetry_answer(text, assessment)
    assert changed
    assert "Approximately 45 hours" not in corrected
    assert "communication is one-way" not in corrected.lower()
    assert "No telemetry or state changes were received" not in corrected
    assert "stored mqttStatus and health attributes" in corrected
    assert "physical command delivery" in corrected or (
        "physical telemetry or command delivery" in corrected
    )
    assert "command invocations" in corrected
