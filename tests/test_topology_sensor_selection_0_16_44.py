from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import trigger_sensor_history_candidates  # noqa: E402
from known_automation_topology import (  # noqa: E402
    parse_known_automations,
    prioritize_known_automation_sensor_candidates,
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
        "id": device_id,
        "label": label,
        "room": "Hallway",
        "matchBasis": "room",
        "capabilities": ["MotionSensor"],
        "suggestedHistoryAttributes": ["motion"],
        "exposedOccupancyAttribute": "motion",
    }


def _filter_data(*labels: str) -> dict:
    return {
        "eventSourceHints": {
            "triggerSensorCandidates": [
                _candidate(str(index + 1), label)
                for index, label in enumerate(labels)
            ]
        }
    }


def _selected(filter_data: dict) -> tuple[list[dict], bool]:
    pool = trigger_sensor_history_candidates(filter_data, limit=8)
    return prioritize_known_automation_sensor_candidates(
        pool,
        KNOWN,
        subject="Hallway Light 1",
        transition="on",
        limit=2,
    )


def test_configured_source_sensors_displace_derived_sensor_from_two_slots() -> None:
    selected, used = _selected(_filter_data(
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
        "Hallway Aqara P1",
        "Hallway Other Motion",
    ))

    assert used is True
    assert [row["name"] for row in selected] == [
        "Hallway FP300 sensor",
        "Hallway Aqara P1",
    ]


def test_derived_sensor_backfills_when_second_configured_source_is_unavailable() -> None:
    selected, used = _selected(_filter_data(
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
        "Hallway Other Motion",
    ))

    assert used is True
    assert [row["name"] for row in selected] == [
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
    ]


def test_target_mismatch_preserves_generic_candidate_order() -> None:
    pool = trigger_sensor_history_candidates(
        _filter_data(
            "Hallway FP300 sensor",
            "Hallway Soft Sensor",
            "Hallway Aqara P1",
        ),
        limit=8,
    )
    selected, used = prioritize_known_automation_sensor_candidates(
        pool,
        KNOWN,
        subject="Kitchen Light",
        transition="on",
        limit=2,
    )

    assert used is False
    assert [row["name"] for row in selected] == [
        "Hallway FP300 sensor",
        "Hallway Soft Sensor",
    ]


def test_topology_sensor_plan_metric_is_registered_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_topology_sensor_plan")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["causal_topology_sensor_plan"] == 1
    rows = present_request_metrics(snapshot)
    assert {"label": "Topology-aware sensor plans", "value": "1"} in rows
