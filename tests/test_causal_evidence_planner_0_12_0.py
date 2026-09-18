from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    controller_history_arguments,
    controller_transition_alignments,
    render_controller_alignment_instruction,
    subject_room_filter_arguments,
)
from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def _subject_history() -> dict[str, Any]:
    return {
        "success": True,
        "label": "Bedroom 3 Light",
        "room": "Bedroom 3",
        "attribute": "switch",
        "temporalAnalysis": {
            "activeState": "on",
            "intervals": [
                {
                    "start": "2026-09-18T00:02:53.713+01:00",
                    "end": "2026-09-18T01:30:07.971+01:00",
                },
                {
                    "start": "2026-09-18T01:32:51.716+01:00",
                    "end": "2026-09-18T01:45:02.397+01:00",
                },
            ],
        },
    }


def test_subject_room_plan_uses_exact_resolved_room_not_model_filter_syntax() -> None:
    assert subject_room_filter_arguments(_subject_history()) == {
        "attribute": "room",
        "operator": "eq",
        "value": "Bedroom 3",
    }


def test_controller_plan_chooses_highest_ranked_provenance_candidate() -> None:
    room_filter = {
        "eventSourceHints": {
            "controllerCandidates": [
                {
                    "label": "Bedroom 3 dimmer - 1",
                    "suggestedHistoryAttributes": ["pushed", "held"],
                },
                {
                    "label": "Bedroom 3 dimmer - 2",
                    "suggestedHistoryAttributes": ["pushed"],
                },
            ]
        }
    }

    assert controller_history_arguments(room_filter) == {
        "name": "Bedroom 3 dimmer - 1",
        "attribute": "pushed",
    }


def test_controller_alignment_prioritizes_provenance_over_weaker_sensor_correlation() -> None:
    controller = {
        "events": [
            {
                "name": "pushed",
                "value": "1",
                "description": "button 1 pushed [physical]",
                "date": "2026-09-18T00:02:53.800+01:00",
            },
            {
                "name": "pushed",
                "value": "1",
                "description": "button 1 pushed [physical]",
                "date": "2026-09-18T01:32:51.800+01:00",
            },
        ]
    }

    alignments = controller_transition_alignments(_subject_history(), controller)

    assert len(alignments) == 2
    assert alignments[0]["deltaSeconds"] < 0.1
    instruction = render_controller_alignment_instruction(alignments)
    assert instruction is not None
    assert "stronger provenance evidence than environmental motion/illuminance" in instruction
    assert "button 1 pushed [physical]" in instruction


class _RoomFilterService(DeviceQueryService):
    def __init__(self, devices: list[dict[str, Any]]) -> None:
        super().__init__(object(), lambda *args, **kwargs: None)
        self._devices = devices

    async def _bulk_live_devices(self, required_attributes, *, enrich_fallback_identity=False):
        return (
            MCPToolResult(
                "hub_read_devices",
                {},
                {},
                "{}",
                {"success": True},
            ),
            list(self._devices),
        )


@pytest.mark.asyncio
async def test_contains_room_filter_still_exposes_controller_evidence_hints() -> None:
    service = _RoomFilterService([
        {
            "id": "100",
            "label": "Bedroom 3 Light",
            "room": "Bedroom 3",
            "capabilities": ["Switch", "Light"],
        },
        {
            "id": "200",
            "label": "Bedroom 3 dimmer - 1",
            "room": "Bedroom 3",
            "capabilities": ["PushableButton", "HoldableButton"],
        },
    ])

    result = await service.filter_devices({
        "attribute": "room",
        "operator": "contains",
        "value": "Bedroom 3",
    })

    assert result.is_error is False
    hints = result.data["eventSourceHints"]["controllerCandidates"]
    assert hints[0]["label"] == "Bedroom 3 dimmer - 1"
    assert hints[0]["suggestedHistoryAttributes"][:2] == ["pushed", "held"]


def test_sparse_request_cache_is_not_reused_when_history_needs_attributes() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        sparse = {
            "id": "7745",
            "label": "Bedroom 3 Sensor T1",
            "room": "Bedroom 3",
            "capabilities": ["IlluminanceMeasurement", "TemperatureMeasurement"],
        }
        DeviceQueryService._cache_resolution_target("Bedroom 3 Sensor T1", sparse)

        assert DeviceQueryService._cached_resolution_target(
            "Bedroom 3 Sensor T1",
            required_fields={"attributes", "capabilities"},
        ) is None
        assert metrics.snapshot()["counters"]["resolution_cache_metadata_miss"] == 1

        complete = {
            **sparse,
            "attributes": {"illuminance": 22, "temperature": 21.0},
        }
        DeviceQueryService._cache_resolution_target("Bedroom 3 Sensor T1", complete)
        resolved = DeviceQueryService._cached_resolution_target(
            "Bedroom 3 Sensor T1",
            required_fields={"attributes", "capabilities"},
        )
        assert resolved is not None
        assert "illuminance" in resolved["attributes"]
    finally:
        metrics.reset(token)
