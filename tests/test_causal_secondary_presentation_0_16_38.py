from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    render_reporting_source_secondary_summary,
)


def _correlation(
    subject_time: str,
    delta: float,
    *,
    producer: str = "Matter Aqara M3",
) -> dict:
    return {
        "boundaryRole": "start",
        "subjectTransition": subject_time,
        "signedDeltaSeconds": delta,
        "deltaSeconds": abs(delta),
        "producedBy": {
            "label": producer,
            "id": "7718",
            "type": "device",
        },
    }


def test_reporting_source_summary_exposes_requested_timing_and_negative_controller_check() -> None:
    requested = "2026-09-25T14:35:45.734000+01:00"
    analysis = {
        "subject": "Hallway Light 1",
        "transition": "on",
        "requestedBoundary": requested,
        "transitionCount": 6,
        "controllers": [
            {
                "label": "Hallway dimmer",
                "attribute": "pushed",
                "relevantAlignments": [],
                "requestedMatched": False,
            },
            {
                "label": "Hallway dimmer - 1",
                "attribute": "pushed",
                "relevantAlignments": [],
                "requestedMatched": False,
            },
        ],
        "sensors": [
            {
                "label": "Hallway FP300 sensor",
                "attribute": "motion",
                "relevantCorrelations": [
                    _correlation("2026-09-25T14:03:51.710000+01:00", 0.978),
                    _correlation("2026-09-25T14:05:57.313000+01:00", 0.939),
                    _correlation("2026-09-25T14:08:04.308000+01:00", 0.618),
                    _correlation("2026-09-25T14:10:21.102000+01:00", -0.105),
                    _correlation(requested, 0.953),
                ],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            },
            {
                "label": "Hallway Soft Sensor",
                "attribute": "motion",
                "relevantCorrelations": [
                    _correlation("2026-09-25T14:03:51.710000+01:00", 0.958),
                    _correlation("2026-09-25T14:05:57.313000+01:00", 0.916),
                    _correlation("2026-09-25T14:08:04.308000+01:00", 0.598),
                    _correlation("2026-09-25T14:10:06.279000+01:00", 0.453),
                    _correlation("2026-09-25T14:10:21.102000+01:00", -4.116),
                    _correlation(requested, 0.933),
                ],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            },
        ],
        "levelRecovery": {},
    }

    message = render_reporting_source_secondary_summary(analysis)

    assert message is not None
    assert (
        "- **Motion correlation:** Hallway FP300 sensor aligned with 5/6 including "
        "requested; Hallway Soft Sensor aligned with 6/6 including requested recent "
        "ON transition correlations."
    ) in message
    assert (
        "Hallway FP300 sensor was reported 0.95s after Hallway Light 1 changed ON"
    ) in message
    assert (
        "Hallway Soft Sensor was reported 0.93s after Hallway Light 1 changed ON"
    ) in message
    assert (
        "- **Shared path:** Hallway FP300 sensor and Hallway Soft Sensor are both "
        "reported through Matter Aqara M3, so they are not independent confirmations."
    ) in message
    assert (
        "- **Controller check:** No matching pushed event was found for Hallway "
        "dimmer or Hallway dimmer - 1 at the requested ON transition."
    ) in message
    assert (
        "- **Conclusion:** Exact initiator unresolved. Hubitat did not record a "
        "direct ON command producer for this transition."
    ) in message
    assert (
        "The timing evidence is correlation only; an automation or action outside "
        "Hubitat remains possible."
    ) in message


def test_requested_sensor_event_before_subject_is_described_as_before() -> None:
    requested = "2026-09-25T14:10:21.102000+01:00"
    message = render_reporting_source_secondary_summary({
        "subject": "Hallway Light 1",
        "transition": "on",
        "requestedBoundary": requested,
        "transitionCount": 1,
        "controllers": [],
        "sensors": [
            {
                "label": "Hallway FP300 sensor",
                "relevantCorrelations": [
                    _correlation(requested, -0.105),
                ],
                "requestedMatched": True,
                "producerLabels": ["Matter Aqara M3"],
            }
        ],
    })

    assert message is not None
    assert (
        "Hallway FP300 sensor was reported 0.1s before Hallway Light 1 changed ON"
    ) in message
