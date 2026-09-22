from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from history_result_enrichment import (  # noqa: E402
    enrich_history_result,
    inferred_state_retry_arguments,
)
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


class NoisyDehumidifierMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.device = {
            "id": "4222",
            "name": "Dehumidifier 2",
            "label": "Dehumidifier 2",
            "room": "Dehumidifier",
            "capabilities": ["Switch", "PowerMeter", "EnergyMeter"],
            "attributes": {"switch": "off", "power": 0},
            "commands": ["on", "off"],
        }

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        args = arguments.get("args") or {}

        if operation == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"devices": [dict(self.device)]},
            )

        if operation == "hub_list_device_events":
            if args.get("attribute") == "switch":
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
                                "description": "switch attribute updated",
                                "date": "2026-09-22T22:38:13.489+0100",
                                "isStateChange": True,
                            },
                            {
                                "name": "switch",
                                "value": "on",
                                "description": "switch attribute updated",
                                "date": "2026-09-22T22:07:37.107+0100",
                                "isStateChange": True,
                            },
                        ],
                        "count": 2,
                    },
                )

            noisy = [
                {
                    "name": "rtt",
                    "value": str(70 + index),
                    "date": f"2026-09-22T23:{23-index:02d}:33.093+0100",
                    "isStateChange": True,
                }
                for index in range(12)
            ]
            noisy.extend([
                {
                    "name": "power",
                    "value": "0",
                    "date": "2026-09-22T22:38:15.689+0100",
                    "isStateChange": True,
                },
                {
                    "name": "energy",
                    "value": "443.33",
                    "date": "2026-09-22T22:38:16.095+0100",
                    "isStateChange": True,
                },
                {
                    "name": "switch",
                    "value": "off",
                    "description": "switch attribute updated",
                    "date": "2026-09-22T22:38:13.489+0100",
                    "isStateChange": True,
                },
            ])
            while len(noisy) < 20:
                index = len(noisy)
                noisy.append({
                    "name": "powerFactor",
                    "value": "0.0",
                    "date": f"2026-09-22T22:37:{59-index:02d}.000+0100",
                    "isStateChange": True,
                })
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"events": noisy[:20], "count": 20},
            )

        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_causal_retry_recovers_switch_interval_from_noisy_full_page() -> None:
    mcp = NoisyDehumidifierMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    original_arguments = {"name": "dehumidifier 2"}
    first = await service.history(original_arguments)
    first = enrich_history_result("homebrain_device_history", first)

    assert first.is_error is False
    assert first.data["attribute"] == "switch"
    assert first.data["attributeInferred"] is True
    assert first.data["temporalAnalysis"]["intervalCount"] == 0
    assert first.data["sourceEventCount"] == 20

    retry_arguments = inferred_state_retry_arguments(
        "homebrain_device_history",
        original_arguments,
        first,
    )

    assert retry_arguments == {
        "name": "Dehumidifier 2",
        "attribute": "switch",
        "limit": 50,
        "hours_back": 24,
    }

    second = await service.history(retry_arguments)
    second = enrich_history_result("homebrain_device_history", second)

    assert second.is_error is False
    assert second.data["attribute"] == "switch"
    assert second.data["temporalAnalysis"]["intervalCount"] == 1
    interval = second.data["temporalAnalysis"]["intervals"][0]
    assert interval["start"] == "2026-09-22T22:07:37.107+0100"
    assert interval["end"] == "2026-09-22T22:38:13.489+0100"

    event_calls = [
        arguments
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_device_events"
    ]
    assert len(event_calls) == 2
    assert "attribute" not in event_calls[0]["args"]
    assert event_calls[1]["args"]["attribute"] == "switch"
    assert event_calls[1]["args"]["limit"] == 50


def test_inferred_retry_is_not_generated_when_interval_already_exists() -> None:
    result = MCPToolResult(
        "homebrain_device_history",
        {},
        {},
        "ok",
        {
            "label": "Dehumidifier 2",
            "attribute": "switch",
            "attributeInferred": True,
            "hoursBack": 24,
            "sourceEventCount": 20,
            "temporalAnalysis": {
                "intervalCount": 1,
                "intervals": [{
                    "start": "2026-09-22T22:07:37.107+0100",
                    "end": "2026-09-22T22:38:13.489+0100",
                }],
            },
        },
    )

    assert inferred_state_retry_arguments(
        "homebrain_device_history",
        {"name": "dehumidifier 2"},
        result,
    ) is None


def test_inferred_retry_requires_a_full_source_page() -> None:
    result = MCPToolResult(
        "homebrain_device_history",
        {},
        {},
        "ok",
        {
            "label": "Dehumidifier 2",
            "attribute": "switch",
            "attributeInferred": True,
            "hoursBack": 24,
            "sourceEventCount": 4,
            "temporalAnalysis": {"intervalCount": 0, "intervals": []},
        },
    )

    assert inferred_state_retry_arguments(
        "homebrain_device_history",
        {"name": "dehumidifier 2"},
        result,
    ) is None


def test_causal_inferred_retry_metric_is_supported_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_inferred_attribute_retry")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["causal_inferred_attribute_retry"] == 1
    assert {
        "label": "Causal inferred-state retries",
        "value": "1",
    } in present_request_metrics(snapshot)
