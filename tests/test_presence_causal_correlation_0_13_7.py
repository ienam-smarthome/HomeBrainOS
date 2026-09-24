from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    render_sensor_correlation_instruction,
    sensor_transition_correlations,
    trigger_sensor_history_arguments,
)
from device_query_service import DeviceQueryService  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def _device(
    label: str,
    room: str,
    capabilities: list[str],
    *,
    attributes: dict | None = None,
) -> dict:
    return {
        "id": label,
        "label": label,
        "room": room,
        "capabilities": capabilities,
        "attributes": dict(attributes or {}),
    }


def test_room_trigger_sensor_candidates_are_capability_grounded() -> None:
    devices = [
        _device(
            "Bedroom 3 Sensor T1",
            "Bedroom 3",
            ["IlluminanceMeasurement", "TemperatureMeasurement"],
        ),
        _device(
            "Bedroom 3 Soft Sensor",
            "Bedroom 3",
            ["MotionSensor"],
            attributes={"motion": "inactive"},
        ),
        _device(
            "Bedroom 3 Presence",
            "Bedroom 3",
            ["PresenceSensor"],
            attributes={"presence": "present"},
        ),
        _device(
            "Hallway Motion",
            "Hallway",
            ["MotionSensor"],
            attributes={"motion": "inactive"},
        ),
    ]

    candidates = DeviceQueryService._room_trigger_sensor_candidates(
        devices,
        "Bedroom 3",
    )

    labels = [row["label"] for row in candidates]
    assert set(labels) == {"Bedroom 3 Soft Sensor", "Bedroom 3 Presence"}
    assert "Bedroom 3 Sensor T1" not in labels
    assert "Hallway Motion" not in labels
    attributes = {
        row["label"]: row["suggestedHistoryAttributes"]
        for row in candidates
    }
    assert attributes["Bedroom 3 Soft Sensor"] == ["motion"]
    assert attributes["Bedroom 3 Presence"] == ["presence"]


def test_trigger_sensor_history_arguments_use_declared_capability_hint() -> None:
    room_filter = {
        "eventSourceHints": {
            "triggerSensorCandidates": [
                {
                    "label": "Bedroom 3 Soft Sensor",
                    "suggestedHistoryAttributes": ["motion"],
                }
            ]
        }
    }

    assert trigger_sensor_history_arguments(room_filter) == {
        "name": "Bedroom 3 Soft Sensor",
        "attribute": "motion",
    }


def test_repeated_presence_pattern_correlates_subject_starts_and_delayed_offs() -> None:
    subject = {
        "label": "Bedroom 3 Light",
        "temporalAnalysis": {
            "observedIntervals": [
                {
                    "start": "2026-09-18T23:55:02.214+01:00",
                    "end": "2026-09-19T00:00:01.762+01:00",
                },
                {
                    "start": "2026-09-19T00:01:59.306+01:00",
                    "end": "2026-09-19T01:23:04.996+01:00",
                },
            ]
        },
    }
    sensor = {
        "label": "Bedroom 3 Soft Sensor",
        "attribute": "motion",
        "events": [
            {
                "name": "motion",
                "value": "active",
                "date": "2026-09-18T23:55:02.284+01:00",
            },
            {
                "name": "motion",
                "value": "inactive",
                "date": "2026-09-18T23:59:51.700+01:00",
            },
            {
                "name": "motion",
                "value": "active",
                "date": "2026-09-19T00:01:59.376+01:00",
            },
            {
                "name": "motion",
                "value": "inactive",
                "date": "2026-09-19T01:22:48.000+01:00",
            },
        ],
    }

    rows = sensor_transition_correlations(subject, sensor)

    starts = [row for row in rows if row["boundaryRole"] == "start"]
    ends = [row for row in rows if row["boundaryRole"] == "end"]
    assert len(starts) == 2
    assert len(ends) == 2
    assert starts[0]["signedDeltaSeconds"] == 0.07
    assert starts[1]["signedDeltaSeconds"] == 0.07
    assert ends[0]["signedDeltaSeconds"] < -9
    assert ends[1]["signedDeltaSeconds"] < -16

    instruction = render_sensor_correlation_instruction(rows)
    assert instruction is not None
    assert "Repeated pattern: 2 start alignment(s), 2 delayed-off/end alignment(s)" in instruction
    assert "subject changed before Hubitat recorded the sensor active edge" in instruction
    assert "do not name a specific external hub" in instruction


def test_end_correlation_prefers_near_after_edge_over_stale_prior_inactive() -> None:
    subject = {
        "label": "Hallway Light 1",
        "correlationEvents": [
            {
                "name": "switch",
                "value": "off",
                "date": "2026-09-24T20:28:40.810+01:00",
            },
            {
                "name": "switch",
                "value": "on",
                "date": "2026-09-24T20:28:20.371+01:00",
            },
        ],
    }
    sensor = {
        "label": "Hallway Soft Sensor",
        "attribute": "motion",
        "events": [
            {
                "name": "motion",
                "value": "inactive",
                "date": "2026-09-24T20:28:15.306+01:00",
                "producedBy": {"label": "Matter Aqara M3", "id": "7718"},
            },
            {
                "name": "motion",
                "value": "active",
                "date": "2026-09-24T20:28:21.315+01:00",
                "producedBy": {"label": "Matter Aqara M3", "id": "7718"},
            },
            {
                "name": "motion",
                "value": "inactive",
                "date": "2026-09-24T20:28:41.694+01:00",
                "producedBy": {"label": "Matter Aqara M3", "id": "7718"},
            },
        ],
    }

    rows = sensor_transition_correlations(subject, sensor)
    end = next(row for row in rows if row["boundaryRole"] == "end")

    assert end["signedDeltaSeconds"] == 0.884
    assert end["producedBy"]["label"] == "Matter Aqara M3"


def test_lux_history_is_not_accepted_as_trigger_sensor_history() -> None:
    room_filter = {
        "eventSourceHints": {
            "triggerSensorCandidates": [
                {
                    "label": "Bedroom 3 Sensor T1",
                    "suggestedHistoryAttributes": ["illuminance"],
                }
            ]
        }
    }

    assert trigger_sensor_history_arguments(room_filter) is None


def test_causal_sensor_metrics_are_supported() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_sensor_read")
        metrics.increment("causal_sensor_aligned", 4)
        counters = metrics.snapshot()["counters"]
        assert counters["causal_sensor_read"] == 1
        assert counters["causal_sensor_aligned"] == 4
    finally:
        metrics.reset(token)
