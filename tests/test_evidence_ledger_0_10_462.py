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
from evidence_ledger import build_current_turn_evidence_ledger  # noqa: E402
from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from reasoning_policy import FINAL_SYNTHESIS_INSTRUCTION  # noqa: E402


def _history_receipt(label: str, attribute: str = "switch") -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "sub_tool": None,
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "arguments": {"name": label},
        "summary": "temporal history: intervals=2, total=10m",
        "details": {
            "label": label,
            "attribute": attribute,
            "temporalAnalysis": {
                "intervalCount": 2,
                "totalActiveDuration": "10m",
                "durationReliability": "unverified-event-stream",
            },
        },
    }


def _location_receipt() -> dict[str, Any]:
    return {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "success": True,
        "evidence_kind": "authoritative_location_event_history",
        "arguments": {
            "tool": "hub_list_device_events",
            "args": {"hoursBack": 24, "limit": 20},
        },
        "summary": "2 location events",
        "details": {
            "count": 2,
            "events": [
                {
                    "name": "mode",
                    "value": "Late Night",
                    "date": "2026-09-18T01:30:02+01:00",
                },
                {
                    "name": "mode",
                    "value": "Bedtime",
                    "date": "2026-09-17T21:30:00+01:00",
                },
            ],
        },
    }


def test_evidence_ledger_records_checked_sources_and_salient_mode_event() -> None:
    ledger = build_current_turn_evidence_ledger(
        [
            _history_receipt("Bedroom 3 Light"),
            _location_receipt(),
            _history_receipt("Bedroom 3 Soft Sensor", "motion"),
        ]
    )

    assert ledger is not None
    assert "HOST CURRENT-TURN EVIDENCE LEDGER" in ledger
    assert "CHECKED device history: Bedroom 3 Light (switch)" in ledger
    assert "CHECKED device history: Bedroom 3 Soft Sensor (motion)" in ledger
    assert "CHECKED location/mode history: 2 events" in ledger
    assert "mode=Late Night @ 2026-09-18T01:30:02+01:00" in ledger
    assert "does not mean the source proved causation" in ledger


@pytest.mark.asyncio
async def test_final_answer_coordinator_injects_ledger_before_no_tools_instruction() -> None:
    calls: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"content": "bounded answer"}

    receipts = [
        _history_receipt("Bedroom 3 Light"),
        _location_receipt(),
    ]
    coordinator = FinalAnswerCoordinator(chat, evidence_supplier=lambda: receipts)

    answer = await coordinator.answer(
        [{"role": "user", "content": "Why was Bedroom 3 Light on?"}]
    )

    assert answer == "bounded answer"
    assert len(calls) == 1
    messages, tools = calls[0]
    assert tools == []
    assert "HOST CURRENT-TURN EVIDENCE LEDGER" in messages[-2]["content"]
    assert messages[-1]["content"] == FINAL_SYNTHESIS_INSTRUCTION


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
            "counters": {"model_rounds": 3},
            "timings_ms": {},
        }
    )


def test_api_guard_corrects_claim_that_checked_sensor_and_location_sources_were_missing() -> None:
    evidence = [
        _history_receipt("Bedroom 3 Light"),
        _location_receipt(),
        _history_receipt("Bedroom 3 Soft Sensor", "motion"),
    ]
    response = build_agent_response(
        FakeOutcome(
            message=(
                "The light was recorded on overnight. "
                "No corresponding sensor or location data was provided. "
                "The specific trigger therefore remains unproven."
            ),
            evidence=evidence,
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.462",
    )

    assert "No corresponding sensor or location data was provided" not in response["message"]
    assert "checked related-device/sensor history and location/mode history" in response["message"]
    assert response["message"].startswith("The light was recorded on overnight.")
    assert response["message"].endswith(
        "The specific trigger therefore remains unproven."
    )


def test_api_guard_corrects_motion_absence_when_motion_temporal_proof_is_nonzero() -> None:
    message = (
        "Related sensor history was checked. "
        "No motion events were recorded during the light's longest interval."
    )
    response = build_agent_response(
        FakeOutcome(
            message=message,
            evidence=[
                _history_receipt("Bedroom 3 Light"),
                _history_receipt("Bedroom 3 Soft Sensor", "motion"),
            ],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert "No motion events were recorded" not in response["message"]
    assert "motion history was checked and contains 2 observed bounded intervals" in response["message"]


class LocationMCP:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        assert name == "hub_read_devices"
        assert arguments["tool"] == "hub_list_device_events"
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {
                "events": [
                    {
                        "name": "mode",
                        "value": "Late Night",
                        "description": "Mode changed to Late Night",
                        "date": "2026-09-18T01:30:02+01:00",
                        "isStateChange": True,
                    }
                ]
            },
        )


@pytest.mark.asyncio
async def test_location_history_receipt_exposes_bounded_event_details_for_audit() -> None:
    receipts: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def record(*args, **kwargs):
        receipts.append((args, kwargs))

    service = DeviceHistoryService(LocationMCP(), record)
    result = await service.location_events({"hours_back": 24, "limit": 20})

    assert result.is_error is False
    raw = next(
        kwargs
        for args, kwargs in receipts
        if kwargs.get("evidence_kind") == "authoritative_location_event_history"
        and kwargs.get("success") is True
    )
    assert raw["details"]["count"] == 1
    assert raw["details"]["events"][0]["value"] == "Late Night"
