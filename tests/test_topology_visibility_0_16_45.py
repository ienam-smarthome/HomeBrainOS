from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from known_automation_topology import (  # noqa: E402
    known_automation_sensor_candidate_visibility,
    parse_known_automations,
    prioritize_known_automation_sensor_candidates,
    render_known_automation_sensor_visibility,
)
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


KNOWN = parse_known_automations([
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
])


def _candidate(device_id: str, label: str) -> dict:
    return {
        "name": label,
        "attribute": "motion",
        "candidate": {
            "id": device_id,
            "label": label,
            "room": "Hallway",
            "capabilities": ["MotionSensor"],
            "suggestedHistoryAttributes": ["motion"],
            "exposedOccupancyAttribute": "motion",
        },
    }


def _visibility(*labels: str) -> list[dict]:
    pool = [
        _candidate(str(index + 1), label)
        for index, label in enumerate(labels)
    ]
    selected, _used = prioritize_known_automation_sensor_candidates(
        pool,
        KNOWN,
        subject="Hallway Light 1",
        transition="on",
        limit=2,
    )
    return known_automation_sensor_candidate_visibility(
        pool,
        selected,
        KNOWN,
        subject="Hallway Light 1",
        transition="on",
    )


def test_visibility_reports_both_configured_sources_when_available() -> None:
    rows = _visibility(
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
        "Hallway Aqara P1",
    )

    assert rows == [{
        "name": "Hallway Lights ON",
        "platform": "Aqara M3",
        "configuredSourceSensors": ["Hallway FP300", "Hallway Aqara P1"],
        "availableSourceSensors": ["Hallway FP300", "Hallway Aqara P1"],
        "unavailableSourceSensors": [],
        "selectedSourceSensors": ["Hallway FP300", "Hallway Aqara P1"],
        "selectedSensors": ["Hallway FP300 sensor", "Hallway Aqara P1"],
        "fallbackDerivedSensors": [],
        "evidenceSource": "safe_hubitat_occupancy_candidate_pool",
    }]


def test_visibility_explains_derived_fallback_when_p1_is_not_in_safe_pool() -> None:
    rows = _visibility(
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
    )

    row = rows[0]
    assert row["availableSourceSensors"] == ["Hallway FP300"]
    assert row["unavailableSourceSensors"] == ["Hallway Aqara P1"]
    assert row["selectedSensors"] == [
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
    ]
    assert row["fallbackDerivedSensors"] == ["Hallway Soft Sensor"]

    summary = render_known_automation_sensor_visibility(rows)
    assert summary is not None
    assert "Hallway Aqara P1" in summary
    assert "safe Hubitat motion/presence candidate pool" in summary
    assert "Hallway Soft Sensor" in summary
    assert "does not mean the source sensor is absent from Aqara M3" in summary


def test_visibility_target_mismatch_returns_no_rows() -> None:
    pool = [
        _candidate("1", "Hallway FP300 sensor"),
        _candidate("2", "Hallway Soft Sensor"),
    ]
    rows = known_automation_sensor_candidate_visibility(
        pool,
        pool,
        KNOWN,
        subject="Kitchen Light",
        transition="on",
    )
    assert rows == []


def test_topology_fallback_metric_is_registered_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_topology_sensor_fallback")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["causal_topology_sensor_fallback"] == 1
    rows = present_request_metrics(snapshot)
    assert {"label": "Topology sensor fallbacks", "value": "1"} in rows
