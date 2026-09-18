from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from causal_evidence_planner import (  # noqa: E402
    controller_history_arguments,
    controller_transition_alignments,
    render_controller_alignment_instruction,
    subject_room_filter_arguments,
)
from device_history_service import DeviceHistoryService  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
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



def test_evidence_brief_preserves_subject_commands_near_interval_boundaries() -> None:
    receipt = {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bedroom 3 Light",
            "attribute": "switch",
            "temporalAnalysis": {
                "intervalCount": 1,
                "totalActiveDuration": "1h 27m",
                "durationReliability": "unverified-event-stream",
                "observedIntervals": [{
                    "start": "2026-09-18T00:02:53.713+01:00",
                    "end": "2026-09-18T01:30:07.971+01:00",
                    "duration": "1h 27m",
                }],
            },
            "observedEvents": [
                {
                    "name": "command-setLevel",
                    "value": None,
                    "description": "Command called: setLevel(15)",
                    "date": "2026-09-18T01:30:04.695+01:00",
                },
                {
                    "name": "command-off",
                    "value": None,
                    "description": "Command called: off()",
                    "date": "2026-09-18T01:30:07.775+01:00",
                },
                {
                    "name": "level",
                    "value": "80",
                    "description": "Unrelated daytime change",
                    "date": "2026-09-18T19:41:48.300+01:00",
                },
            ],
        },
    }
    other = {
        "tool": "homebrain_location_events",
        "success": True,
        "details": {"events": [{"name": "mode", "value": "Late Night", "date": "2026-09-18T01:30:02+01:00"}]},
    }

    brief = build_current_turn_evidence_ledger([receipt, other])

    assert brief is not None
    assert "command-setLevel" in brief
    assert "Command called: setLevel(15)" in brief
    assert "command-off" in brief
    assert "Command called: off()" in brief
    assert "Unrelated daytime change" not in brief



class _DetailedHistoryMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name != "hub_read_devices":
            raise AssertionError(f"unexpected tool: {name}")
        target = {
            "id": "7745",
            "name": "Bedroom 3 Sensor T1",
            "label": "Bedroom 3 Sensor T1",
            "room": "Bedroom 3",
            "capabilities": [
                "IlluminanceMeasurement",
                "TemperatureMeasurement",
            ],
            "attributes": {
                "illuminance": 22,
                "temperature": 21.0,
            },
            "commands": [],
        }
        data = {"devices": [target]}
        return MCPToolResult(name, arguments, {}, json.dumps(data), data)


@pytest.mark.asyncio
async def test_typed_history_rehydrates_sparse_cache_before_capability_validation() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        DeviceQueryService._cache_resolution_target(
            "Bedroom 3 Sensor T1",
            {
                "id": "7745",
                "label": "Bedroom 3 Sensor T1",
                "room": "Bedroom 3",
                "capabilities": [
                    "IlluminanceMeasurement",
                    "TemperatureMeasurement",
                ],
            },
        )
        mcp = _DetailedHistoryMCP()
        service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

        result = await service.history({
            "name": "Bedroom 3 Sensor T1",
            "attribute": "motion",
        })

        assert result.is_error is True
        assert result.data["unsupportedAttribute"] == "motion"
        assert result.data["availableAttributes"] == ["illuminance", "temperature"]
        assert len(mcp.calls) == 1
        assert mcp.calls[0][0] == "hub_read_devices"
        assert metrics.snapshot()["counters"]["resolution_cache_metadata_miss"] == 1
    finally:
        metrics.reset(token)


def test_generic_no_motion_recorded_wording_is_hedged_for_unverified_zero() -> None:
    receipt = {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bedroom 3 Soft Sensor",
            "attribute": "motion",
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "activeState": "active",
                "inactiveState": "inactive",
                "intervalCount": 0,
                "totalActiveDuration": "0s",
                "totalActiveSeconds": 0,
                "coverage": "partial",
                "durationReliability": "unverified-event-stream",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "windowLabel": "last night",
            },
        },
    }
    outcome = SimpleNamespace(
        message=(
            "No motion was recorded by either the Bedroom 3 Soft Sensor "
            "during these transitions."
        ),
        evidence=[receipt],
        metrics={"outcome": "success", "counters": {"model_rounds": 2}, "timings_ms": {}},
        request_class="live-read",
        choices=[],
        confirmation_required=False,
        confirmation_count=0,
        automation_items=[],
    )

    response = build_agent_response(
        outcome,
        model="gemma4:31b",
        elapsed_ms=1,
        version="0.12.0",
    )

    assert "No bounded active interval was established for Bedroom 3 Soft Sensor" in response["message"]
    assert "does not prove it stayed inactive" in response["message"]
    assert "No motion was recorded" not in response["message"]
