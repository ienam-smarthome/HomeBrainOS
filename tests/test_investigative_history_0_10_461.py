from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from device_history_service import DeviceHistoryService  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import HubitatMCPClient, MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


class StructuralContextMCP(HubitatMCPClient):
    def __init__(self) -> None:
        super().__init__("http://hubitat.invalid/mcp")
        self.remote_calls: list[tuple[str, dict]] = []

    async def get_live_context(self):
        return {
            "devices": [
                {
                    "id": "7841",
                    "name": "Bedroom 3 Light",
                    "label": "Bedroom 3 Light",
                    "room": "Bedroom 3",
                    "capabilities": ["Switch", "Light"],
                    "attributes": {"switch": "off"},
                },
                {
                    "id": "7767",
                    "name": "Bedroom 3 Soft Sensor",
                    "label": "Bedroom 3 Soft Sensor",
                    "room": "Bedroom 3",
                    "capabilities": ["MotionSensor", "TemperatureMeasurement"],
                    "attributes": {"motion": "inactive", "temperature": 22.0},
                },
                {
                    "id": "9999",
                    "name": "Kitchen Motion",
                    "label": "Kitchen Motion",
                    "room": "Kitchen",
                    "capabilities": ["MotionSensor"],
                    "attributes": {"motion": "inactive"},
                },
            ],
            "totalDevices": 3,
            "idsComplete": True,
            "truncated": False,
            "partial": False,
        }

    async def call_tool(self, name: str, arguments: dict):
        self.remote_calls.append((name, arguments))
        operation = arguments.get("tool")
        if name == "hub_read_devices" and operation == "hub_list_device_events":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "motion",
                            "value": "inactive",
                            "date": "2026-09-18T01:32:50+01:00",
                            "isStateChange": True,
                        },
                        {
                            "name": "motion",
                            "value": "active",
                            "date": "2026-09-18T01:32:42+01:00",
                            "isStateChange": True,
                        },
                    ]
                },
            )
        raise AssertionError(
            f"structural room filtering must not call full hub_list_devices: "
            f"{name} {arguments}"
        )


@pytest.mark.asyncio
async def test_room_filter_uses_bulk_context_and_seeds_history_resolution_cache() -> None:
    mcp = StructuralContextMCP()
    metrics = RequestMetrics()
    token = metrics.begin()
    receipts = []
    try:
        query = DeviceQueryService(
            mcp, lambda *args, **kwargs: receipts.append((args, kwargs))
        )
        filtered = await query.filter_devices(
            {"attribute": "room", "operator": "contains", "value": "Bedroom 3"}
        )

        assert filtered.is_error is False
        assert [item["label"] for item in filtered.data["matches"]] == [
            "Bedroom 3 Light",
            "Bedroom 3 Soft Sensor",
        ]
        soft = filtered.data["matches"][1]
        assert "motionsensor" in {str(value).casefold() for value in soft["capabilities"]}
        assert any(
            args[1].get("resource") == "hubitat://context"
            for args, _kwargs in receipts
        )

        history = DeviceHistoryService(mcp, lambda *_a, **_k: None)
        result = await history.history(
            {
                "name": "Bedroom 3 Soft Sensor",
                "attribute": "motion",
                "hours_back": 24,
            }
        )

        assert result.is_error is False
        assert metrics.snapshot()["counters"]["resolution_cache_hit"] == 1
        assert not any(
            arguments.get("tool") == "hub_list_devices"
            for _name, arguments in mcp.remote_calls
        )
        assert sum(
            1
            for _name, arguments in mcp.remote_calls
            if arguments.get("tool") == "hub_list_device_events"
        ) == 1
    finally:
        metrics.reset(token)
        await mcp.close()


@dataclass
class FakeOutcome:
    message: str
    evidence: list[dict[str, Any]]
    request_class: str = "live-read"
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    automation_items: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "outcome": "success",
            "counters": {"model_rounds": 2},
            "timings_ms": {},
        }
    )


def _unverified_history_receipt() -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bedroom 3 Light",
            "attribute": "switch",
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveDuration": "1h 44m",
                "totalActiveSeconds": 6237,
                "intervalCount": 5,
                "longestActiveDuration": "1h 27m",
                "longestActiveSeconds": 5234,
                "coverage": "partial",
                "totalIsLowerBound": False,
                "durationReliability": "unverified-event-stream",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "windowed": True,
                "windowLabel": "last night",
                "boundaryStateKnown": False,
            },
        },
    }


def test_unverified_duration_guard_preserves_non_duration_investigative_analysis() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "Several rapid toggles stand out in the recorded event pattern. "
                "Bedroom 3 Light was genuinely on for about 1h 43m last night. "
                "The timing overlaps with motion, but that does not prove the cause."
            ),
            evidence=[_unverified_history_receipt()],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.461",
    )

    assert response["message"].startswith(
        "Several rapid toggles stand out in the recorded event pattern."
    )
    assert "estimate of 1h 44m" in response["message"]
    assert response["message"].endswith(
        "The timing overlaps with motion, but that does not prove the cause."
    )
    assert "genuinely on for about 1h 43m" not in response["message"]
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_correct_qualified_unverified_estimate_does_not_erase_analysis() -> None:
    message = (
        "Several rapid toggles stand out in the recorded event pattern. "
        "The recorded rows give an estimated total of 1h 44m last night. "
        "That pattern alone does not establish whether it is normal for this device."
    )
    response = build_agent_response(
        FakeOutcome(message=message, evidence=[_unverified_history_receipt()]),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.461",
    )

    assert response["message"] == message
    assert "finalAnswerCorrectionApplied" not in response["evidence"][0]["details"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return FakeResponse(next(self.responses))

    async def aclose(self):
        return None


class NormalityMCP:
    def __init__(self) -> None:
        self.devices = [
            {
                "id": "42",
                "name": "Lounge Lamp",
                "label": "Lounge Lamp",
                "room": "Lounge",
                "capabilities": ["Switch", "Light"],
                "attributes": {"switch": "off"},
                "commands": ["on", "off"],
            }
        ]

    async def list_tools(self):
        return []

    async def get_cached_devices(self):
        return list(self.devices)

    def peek_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, name, arguments):
        operation = arguments.get("tool")
        if name == "hub_read_devices" and operation == "hub_list_devices":
            return MCPToolResult(name, arguments, {}, "ok", {"devices": self.devices})
        if name == "hub_read_devices" and operation == "hub_list_device_events":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "switch",
                            "value": "off",
                            "date": "2026-09-18T01:45:00+01:00",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-09-18T01:30:00+01:00",
                            "isStateChange": True,
                        },
                    ]
                },
            )
        raise AssertionError((name, arguments))


def _call(name: str, arguments: dict | None = None) -> dict:
    return {"function": {"name": name, "arguments": arguments or {}}}


@pytest.mark.asyncio
async def test_normality_history_turn_receives_investigative_evidence_contract() -> None:
    mcp = NormalityMCP()
    ai = FakeAI(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        _call(
                            "homebrain_device_history",
                            {
                                "name": "Lounge Lamp",
                                "attribute": "switch",
                                "hours_back": 24,
                            },
                        )
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "The recorded rows show a switch interval, but a single "
                        "night does not establish what is normal for this device."
                    ),
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "The recorded rows show a switch interval, but a single "
                        "night does not establish what is normal for this device."
                    ),
                }
            },
        ]
    )
    agent = UnifiedMCPAgent(mcp, "key", "gemma4:31b", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "Was Lounge Lamp behaving normally last night?"
    )

    assert len(ai.requests) == 3
    second_payload = ai.requests[1][1]["json"]
    assert second_payload.get("tools")
    rendered = "\n".join(
        str(message.get("content") or "")
        for message in second_payload["messages"]
    )
    assert "HOST INVESTIGATIVE-HISTORY REQUIREMENT" in rendered
    assert "direct provenance/log evidence" in rendered
    assert "Prefer a stronger source over several weaker correlations" in rendered
    assert "do not invent a generic notion of normality" in rendered
    assert "baseline or explicit expected rule" in rendered
    assert outcome.metrics["counters"].get("evidence_sufficiency_stop", 0) == 0
    assert outcome.metrics["counters"].get("investigative_finalization", 0) == 1
    assert ai.requests[2][1]["json"].get("tools") in (None, [])
