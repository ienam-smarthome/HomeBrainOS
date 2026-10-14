"""v0.17.58 regressions from live Bedroom 3 Mesh and Livingroom light investigations."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from recorded_telemetry_freshness import (  # noqa: E402
    reconcile_telemetry_answer,
)
from causal_fail_closed_summary import (  # noqa: E402
    _focal_sensor_correlations,
    render_failed_causal_synthesis,
)
import causal_fail_closed_summary  # noqa: E402


TELEMETRY_ASSESSMENT = {
    "device": "Bedroom 3 Mesh",
    "latestReturnedDeviceAttributedEventAt": "2026-10-13T22:35:38.773+01:00",
    "latestReturnedEventAttribute": "mqttStatus",
    "eventWithinPast24hOfRead": True,
    "physicalTelemetryVerified": False,
    "storedDataAgeSeconds": {
        "value": "162325",
        "recordedAt": "2026-10-13T22:35:27.310+01:00",
        "isCurrentRecalculatedValue": False,
    },
}


def test_telemetry_answer_reconciles_current_age_and_no_event_claims():
    message = (
        "### Investigation Results: Bedroom 3 Mesh\n\n"
        "**Reported State**\n*   **Health Status:** Offline.\n\n"
        "**Telemetry Activity**\n"
        "*   **Last Seen:** Monday Oct 12, 01:30 BST.\n"
        "*   **Data Age:** 162,325 seconds (~45 hours).\n"
        "*   **Recent Events:** MQTT changed on Oct 13. No telemetry has been "
        "received since.\n\n"
        "**Conclusions**\n"
        "*   **Telemetry is stale:** The device has not provided a fresh update "
        "in over 45 hours.\n"
        "*   **Command Reachability:** Unverified.\n"
    )
    fixed, changed = reconcile_telemetry_answer(message, TELEMETRY_ASSESSMENT)
    assert changed
    assert "Data Age:** 162,325 seconds" not in fixed
    assert "in over 45 hours" not in fixed
    assert "No telemetry has been received since" not in fixed
    assert "Stored dataAgeSeconds=162325 was recorded" in fixed
    assert "latest returned device-attributed state event" in fixed
    assert "**Health Status:** Offline." in fixed
    assert "**Command Reachability:** Unverified." in fixed


def test_scoped_historical_age_is_preserved():
    message = (
        "The stored dataAgeSeconds=162325 was recorded on Oct 13 "
        "and must not be read as a current age."
    )
    assert reconcile_telemetry_answer(
        message, TELEMETRY_ASSESSMENT,
    ) == (message, False)


def test_focal_sensor_fallback_preserves_signed_order_and_repeats():
    evidence = [{
        "tool": "homebrain_causal_secondary_correlation", "success": True,
        "details": {
            "subject": "Livingroom Light 1",
            "sensors": [{
                "label": "FP400 motion sensor",
                "relevantCorrelations": [
                    {
                        "boundaryRole": "start",
                        "subjectTransition":
                        "2026-10-14T19:55:00.049000+01:00",
                        "sensorEvent":
                        "2026-10-14T19:54:59.961000+01:00",
                        "eventValue": "active",
                    },
                    {
                        "boundaryRole": "start",
                        "subjectTransition":
                        "2026-10-14T17:24:02.221000+01:00",
                        "sensorEvent":
                        "2026-10-14T17:24:02.142000+01:00",
                        "eventValue": "active",
                    },
                ],
            }],
        },
    }]
    result = _focal_sensor_correlations(
        evidence, "Livingroom Light 1",
        "2026-10-14T19:55:00.049+0100", "start",
    )
    assert len(result) == 1
    assert "FP400 motion sensor reported active" in result[0]
    assert "0.088 seconds before" in result[0]
    assert "not a confirmed command" in result[0]
    assert "17:24" not in result[0]

    original = causal_fail_closed_summary.build_causal_evidence_graph
    try:
        causal_fail_closed_summary.build_causal_evidence_graph = lambda *_: {
            "scope": "single-observed-event",
            "focus": {
                "subject": "Livingroom Light 1",
                "on": "2026-10-14T19:55:00.049+0100",
            },
            "physicalStateBoundary": {
                "reporter": {"label": "Matter Hue Bridge Pro"},
                "listenersNotified": [
                    {"label": "Livingroom Light 1 automation",
                     "appId": "4019"},
                ],
            },
            "directCommand": None,
        }
        answer = render_failed_causal_synthesis(
            evidence, "Why did Livingroom Light 1 turn on at 19:55?"
        )
        assert "FP400 motion sensor" in answer
        assert "0.088 seconds before" in answer
        assert "Downstream listeners" in answer
        assert "not prove command initiation" in answer
        assert "initiating cause unresolved" in answer
    finally:
        causal_fail_closed_summary.build_causal_evidence_graph = original


def test_incomplete_or_unscoped_sensor_evidence_cannot_be_promoted():
    rows = [{
        "tool": "homebrain_causal_secondary_correlation", "success": True,
        "details": {
            "subject": "Another Light",
            "sensors": [{
                "label": "Unrelated motion",
                "relevantCorrelations": [{
                    "boundaryRole": "start",
                    "subjectTransition": "2026-10-14T19:55:00.049+0100",
                    "sensorEvent": "2026-10-14T19:54:59.990+0100",
                    "eventValue": "active",
                }],
            }],
        },
    }]
    assert _focal_sensor_correlations(
        rows, "Livingroom Light 1",
        "2026-10-14T19:55:00.049+0100", "start",
    ) == []
