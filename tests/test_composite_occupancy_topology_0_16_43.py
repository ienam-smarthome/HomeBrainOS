from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    build_reporting_source_secondary_analysis,
    render_reporting_source_secondary_summary,
)
from known_automation_topology import parse_known_automations  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


KNOWN = [
    {
        "name": "Hallway Lights ON",
        "platform": "Aqara M3",
        "triggerMode": "any",
        "triggers": [
            {
                "device": "Hallway FP300",
                "aliases": ["Hallway FP300 sensor"],
            },
            {"device": "Hallway Aqara P1"},
        ],
        "derivedSensors": [
            {
                "device": "Hallway Soft Sensor",
                "kind": "occupancy",
                "sourceMode": "combined",
                "sources": [
                    {
                        "device": "Hallway FP300",
                        "aliases": ["Hallway FP300 sensor"],
                    },
                    {"device": "Hallway Aqara P1"},
                ],
            }
        ],
        "actions": [
            {"device": "Hallway Light 1", "transition": "on"},
            {"device": "Hallway Light 2", "transition": "on"},
        ],
    }
]


def _subject(requested: str) -> dict:
    return {
        "label": "Hallway Light 1",
        "room": "Hallway",
        "correlationEvents": [
            {
                "name": "switch",
                "value": "on",
                "date": requested,
            }
        ],
    }


def _sensor(label: str, event_time: str) -> dict:
    return {
        "label": label,
        "room": "Hallway",
        "attribute": "motion",
        "events": [
            {
                "name": "motion",
                "value": "active",
                "date": event_time,
                "producedBy": {
                    "label": "Matter Aqara M3",
                    "id": "7718",
                    "type": "device",
                },
            }
        ],
    }


def test_composite_sensor_is_dependency_not_second_independent_trigger() -> None:
    requested = "2026-09-25T17:37:53.911+01:00"
    analysis = build_reporting_source_secondary_analysis(
        _subject(requested),
        transition="on",
        requested_boundary=requested,
        sensor_histories=[
            _sensor("Hallway FP300 sensor", "2026-09-25T17:37:52.845+01:00"),
            _sensor("Hallway Soft Sensor", "2026-09-25T17:37:53.861+01:00"),
        ],
        known_automations=KNOWN,
    )

    match = analysis["knownAutomationMatches"][0]
    assert match["timingStatus"] == "timing-consistent"
    assert len(match["matchedTriggers"]) == 1
    assert match["matchedTriggers"][0]["configuredTrigger"] == "Hallway FP300"
    assert len(match["matchedDerivedSensors"]) == 1
    assert match["matchedDerivedSensors"][0]["derivedSensor"] == "Hallway Soft Sensor"
    assert match["matchedDerivedSensors"][0]["sourceTriggers"] == [
        "Hallway FP300",
        "Hallway Aqara P1",
    ]

    message = render_reporting_source_secondary_summary(analysis)
    assert message is not None
    assert "**Composite signal:** Hallway Soft Sensor" in message
    assert "derived occupancy signal from Hallway FP300/Hallway Aqara P1" in message
    assert "not an independent confirmation" in message
    assert "does not identify which source sensor fired" in message
    assert "**Shared path:**" not in message


def test_composite_only_supports_route_without_claiming_source_trigger() -> None:
    requested = "2026-09-25T17:37:53.911+01:00"
    analysis = build_reporting_source_secondary_analysis(
        _subject(requested),
        transition="on",
        requested_boundary=requested,
        sensor_history=_sensor(
            "Hallway Soft Sensor",
            "2026-09-25T17:37:53.861+01:00",
        ),
        known_automations=KNOWN,
    )

    match = analysis["knownAutomationMatches"][0]
    assert match["timingStatus"] == "derived-signal-consistent"
    assert match["matchedTriggers"] == []
    assert len(match["matchedDerivedSensors"]) == 1

    message = render_reporting_source_secondary_summary(analysis)
    assert message is not None
    assert (
        '**Known automation:** Aqara M3 “Hallway Lights ON” is configured to turn '
        "Hallway Light 1 ON"
    ) in message
    assert "A configured composite sensor aligned with this transition" in message
    assert "does not identify which source sensor fired" in message
    assert (
        '**Conclusion:** Aqara M3 “Hallway Lights ON” is the configured external '
        "route consistent with this light and composite-sensor timing"
    ) in message


def test_composite_before_direct_after_uses_derived_signal_status() -> None:
    requested = "2026-09-25T17:15:31.387+01:00"
    analysis = build_reporting_source_secondary_analysis(
        _subject(requested),
        transition="on",
        requested_boundary=requested,
        sensor_histories=[
            _sensor("Hallway FP300 sensor", "2026-09-25T17:15:32.333+01:00"),
            _sensor("Hallway Soft Sensor", "2026-09-25T17:15:31.337+01:00"),
        ],
        known_automations=KNOWN,
    )

    match = analysis["knownAutomationMatches"][0]
    assert match["matchedTriggers"][0]["signedDeltaSeconds"] == 0.946
    assert match["matchedDerivedSensors"][0]["signedDeltaSeconds"] == -0.05
    assert match["timingStatus"] == "derived-signal-consistent"


def test_parser_retains_composite_sources_and_rejects_source_less_rows() -> None:
    encoded = """[{
      "name":"Hallway Lights ON",
      "platform":"Aqara M3",
      "triggers":[{"device":"Hallway FP300"}],
      "derivedSensors":[
        {
          "device":"Hallway Soft Sensor",
          "kind":"occupancy",
          "sourceMode":"combined",
          "sources":["Hallway FP300","Hallway Aqara P1"]
        },
        {"device":"Unknown Derived Sensor","sources":[]}
      ],
      "actions":[{"device":"Hallway Light 1","transition":"on"}]
    }]"""

    parsed = parse_known_automations(encoded)
    assert len(parsed) == 1
    assert len(parsed[0]["derivedSensors"]) == 1
    derived = parsed[0]["derivedSensors"][0]
    assert derived["device"] == "Hallway Soft Sensor"
    assert derived["sourceMode"] == "combined"
    assert [row["device"] for row in derived["sources"]] == [
        "Hallway FP300",
        "Hallway Aqara P1",
    ]


def test_known_automation_metrics_are_registered_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_known_automation_match")
        metrics.increment("causal_composite_sensor_match")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["causal_known_automation_match"] == 1
    assert snapshot["counters"]["causal_composite_sensor_match"] == 1
    rows = present_request_metrics(snapshot)
    assert {"label": "Known external automation matches", "value": "1"} in rows
    assert {"label": "Composite sensor topology matches", "value": "1"} in rows
