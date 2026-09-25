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


def _sensor(event_time: str) -> dict:
    return {
        "label": "Hallway FP300 sensor",
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


def test_known_automation_before_boundary_becomes_concrete_timing_match() -> None:
    requested = "2026-09-25T17:37:53.911+01:00"
    analysis = build_reporting_source_secondary_analysis(
        _subject(requested),
        transition="on",
        requested_boundary=requested,
        sensor_history=_sensor("2026-09-25T17:37:52.845+01:00"),
        known_automations=KNOWN,
    )

    assert len(analysis["knownAutomationMatches"]) == 1
    match = analysis["knownAutomationMatches"][0]
    assert match["name"] == "Hallway Lights ON"
    assert match["platform"] == "Aqara M3"
    assert match["timingStatus"] == "timing-consistent"
    assert match["matchedTriggers"][0]["sensorLabel"] == "Hallway FP300 sensor"
    assert match["matchedTriggers"][0]["signedDeltaSeconds"] == -1.066

    message = render_reporting_source_secondary_summary(analysis)
    assert message is not None
    assert (
        '**Known automation:** Aqara M3 “Hallway Lights ON” is configured to turn '
        "Hallway Light 1 ON"
    ) in message
    assert "Hallway FP300 sensor was reported 1.07s before" in message
    assert "consistent with that configured upstream route" in message
    assert "cannot prove the external automation executed this run" in message
    assert (
        '**Conclusion:** Aqara M3 “Hallway Lights ON” is the configured external '
        "route that matches this light and trigger timing"
    ) in message
    assert "Exact initiator unresolved" not in message


def test_known_automation_after_boundary_stays_candidate_not_execution_proof() -> None:
    requested = "2026-09-25T17:50:46.926+01:00"
    analysis = build_reporting_source_secondary_analysis(
        _subject(requested),
        transition="on",
        requested_boundary=requested,
        sensor_history=_sensor("2026-09-25T17:50:47.872+01:00"),
        known_automations=KNOWN,
    )

    match = analysis["knownAutomationMatches"][0]
    assert match["timingStatus"] == "configured-candidate"

    message = render_reporting_source_secondary_summary(analysis)
    assert message is not None
    assert "**Recorded order:**" in message
    assert (
        "because the automation is upstream, it remains a concrete configured "
        "candidate"
    ) in message
    assert (
        '**Conclusion:** Aqara M3 “Hallway Lights ON” is a configured external '
        "route for this light"
    ) in message
    assert "cannot prove it executed this exact transition" in message


def test_known_automation_requires_matching_action_target() -> None:
    requested = "2026-09-25T17:37:53.911+01:00"
    analysis = build_reporting_source_secondary_analysis(
        {
            **_subject(requested),
            "label": "Kitchen Light",
        },
        transition="on",
        requested_boundary=requested,
        sensor_history=_sensor("2026-09-25T17:37:52.845+01:00"),
        known_automations=KNOWN,
    )

    assert analysis["knownAutomationMatches"] == []


def test_known_automation_json_parser_is_fail_closed() -> None:
    encoded = (
        '[{"name":"Hallway Lights ON","platform":"Aqara M3",'
        '"triggers":[{"device":"Hallway FP300"}],'
        '"actions":[{"device":"Hallway Light 1","transition":"on"}]}]'
    )

    parsed = parse_known_automations(encoded)
    assert parsed[0]["name"] == "Hallway Lights ON"
    assert parsed[0]["actions"][0]["transition"] == "on"
    assert parse_known_automations("{not valid json") == []
