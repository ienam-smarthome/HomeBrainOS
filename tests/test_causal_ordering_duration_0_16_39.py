from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_command_provenance import _duration_text  # noqa: E402
from causal_evidence_planner import (  # noqa: E402
    render_reporting_source_secondary_summary,
)


def _correlation(subject_time: str, delta: float) -> dict:
    return {
        "boundaryRole": "start",
        "subjectTransition": subject_time,
        "signedDeltaSeconds": delta,
        "deltaSeconds": abs(delta),
        "producedBy": {
            "label": "Matter Aqara M3",
            "id": "7718",
            "type": "device",
        },
    }


def test_causal_run_duration_keeps_seconds_and_correct_plural() -> None:
    assert _duration_text(
        "2026-09-25T14:35:45.734+01:00",
        "2026-09-25T14:36:52.449+01:00",
    ) == "1 minute 7 seconds"
    assert _duration_text(
        "2026-09-25T14:35:45+01:00",
        "2026-09-25T14:36:45+01:00",
    ) == "1 minute"
    assert _duration_text(
        "2026-09-25T14:35:45+01:00",
        "2026-09-25T14:35:46+01:00",
    ) == "1 second"


def test_all_requested_sensor_reports_after_subject_get_ordering_explanation() -> None:
    requested = "2026-09-25T14:35:45.734000+01:00"
    message = render_reporting_source_secondary_summary({
        "subject": "Hallway Light 1",
        "transition": "on",
        "requestedBoundary": requested,
        "transitionCount": 5,
        "controllers": [],
        "sensors": [
            {
                "label": "Hallway FP300 sensor",
                "relevantCorrelations": [
                    _correlation(requested, 0.953),
                ],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            },
            {
                "label": "Hallway Soft Sensor",
                "relevantCorrelations": [
                    _correlation(requested, 0.933),
                ],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            },
        ],
    })

    assert message is not None
    assert (
        "- **Recorded order:** The requested motion/presence reports were recorded "
        "after Hallway Light 1 changed ON, so those recorded sensor edges cannot "
        "be the Hubitat-side trigger for this transition."
    ) in message
    assert (
        "An upstream system may still have detected motion/presence earlier and "
        "reported the states to Hubitat in a different order."
    ) in message


def test_mixed_requested_sensor_order_does_not_overstate_ordering() -> None:
    requested = "2026-09-25T14:10:21.102000+01:00"
    message = render_reporting_source_secondary_summary({
        "subject": "Hallway Light 1",
        "transition": "on",
        "requestedBoundary": requested,
        "transitionCount": 2,
        "controllers": [],
        "sensors": [
            {
                "label": "Hallway FP300 sensor",
                "relevantCorrelations": [_correlation(requested, -0.105)],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            },
            {
                "label": "Hallway Soft Sensor",
                "relevantCorrelations": [_correlation(requested, 0.453)],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            },
        ],
    })

    assert message is not None
    assert "**Recorded order:**" not in message
