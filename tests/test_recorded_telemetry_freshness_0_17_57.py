"""Time-scoped telemetry and safe causal fallbacks from live v0.17.56 cases."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from recorded_telemetry_freshness import (
    assess_recorded_telemetry_freshness, render_temporal_qualification,
)
from causal_fail_closed_summary import render_failed_causal_synthesis
import causal_fail_closed_summary


def _history():
    return [{
        "tool": "homebrain_device_history",
        "success": True, "mutates": False, "effect": "read",
        "timestamp": "2026-10-14T20:48:18.297292+00:00",
        "details": {
            "label": "Bedroom 3 Mesh", "historySourceIntegrityVerified": False,
            "observedEventsTruncated": True,
            "observedEvents": [
                {"name": "command-refresh",
                 "date": "2026-10-14T18:00:04.909+0100",
                 "type": "command",
                 "producedBy": {"id": "4072", "label": "Device Health Monitor", "type": "app"}},
                {"name": "mqttStatus", "value": "connected",
                 "date": "2026-10-13T22:35:38.773+0100",
                 "producedBy": {"id": "7103", "label": "Bedroom 3 Mesh", "type": "device"}},
                {"name": "dataAgeSeconds", "value": "162325",
                 "date": "2026-10-13T22:35:27.310+0100",
                 "producedBy": {"id": "7103", "label": "Bedroom 3 Mesh", "type": "device"}},
            ],
        },
    }]


def test_historical_dataage_and_device_attributed_event_within_last_24_hours():
    status = assess_recorded_telemetry_freshness(_history())
    assert status is not None
    assert status["device"] == "Bedroom 3 Mesh"
    assert status["latestReturnedEventAttribute"] == "mqttStatus"
    assert status["eventWithinPast24hOfRead"] is True
    assert 23*3600 < status["secondsSinceLatestReturnedEvent"] < 24*3600
    assert status["storedDataAgeSeconds"]["value"] == "162325"
    assert status["storedDataAgeSeconds"]["isCurrentRecalculatedValue"] is False
    assert status["physicalTelemetryVerified"] is False
    qualifier = render_temporal_qualification(
        status, "No telemetry has been received in the last 24 hours."
    )
    assert "device-attributed event is present within 24 hours" in qualifier
    assert "not a fresh elapsed-time measurement" in qualifier


def test_command_events_alone_do_not_count_as_device_origin_telemetry():
    rows = _history()
    rows[0]["details"]["observedEvents"] = [
        rows[0]["details"]["observedEvents"][0]
    ]
    snapshot = assess_recorded_telemetry_freshness(rows)
    assert snapshot is not None
    assert snapshot["onlyCommandEventsInReturnedWindow"] is True
    assert snapshot["observedCommandEvents"] == 1
    assert snapshot["latestReturnedDeviceAttributedEventAt"] is None
    assert snapshot["physicalTelemetryVerified"] is False


def test_ambiguous_causal_repair_uses_safe_graph_fallback(monkeypatch):
    def graph(_evidence, _user):
        return {
            "scope": "single-observed-event",
            "focus": {
                "subject": "Livingroom Light 1",
                "on": "2026-10-14T19:55:00.049+0100",
            },
            "physicalStateBoundary": {
                "reporter": {"label": "Matter Hue Bridge Pro",
                             "type": "device", "id": "7790"},
                "eventType": "physical",
            },
            "directCommand": None,
        }
    monkeypatch.setattr(causal_fail_closed_summary,
                        "build_causal_evidence_graph", graph)
    msg = render_failed_causal_synthesis(
        [], "Why did Livingroom Light 1 turn on?"
    )
    assert "19:55:00.049" in msg
    assert "Matter Hue Bridge Pro" in msg
    assert "initiating cause unresolved" in msg
    assert "not the upstream controller" in msg
    assert "No matching direct command producer was established" in msg
    assert "most likely" not in msg
    assert "external automation did" not in msg


def test_causal_fallback_does_not_invent_a_focal_event(monkeypatch):
    monkeypatch.setattr(
        causal_fail_closed_summary, "build_causal_evidence_graph",
        lambda *_: {"scope": "ambiguous-or-unobserved-event"},
    )
    assert render_failed_causal_synthesis([], "Why did it switch on?") is None
