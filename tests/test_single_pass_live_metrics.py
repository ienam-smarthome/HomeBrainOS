from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult
from semantic_metric_comparison import _SPECS
from semantic_metric_comparison_live import (
    LiveStateSemanticMetricComparisonExecutor,
)


def tool_result(devices):
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={},
        text="",
        data={"devices": devices},
        is_error=False,
    )


class RejectingClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        raise AssertionError(
            "Direct MCP calls must not run when the shared summary "
            "contains valid metric readings"
        )


class SummaryIndex:
    def __init__(self, devices):
        self.devices = devices
        self.summary_calls = []
        self.capability_calls = []
        self.client = RejectingClient()

    async def summary_result(self, *, force=False):
        self.summary_calls.append({"force": force})
        return tool_result(self.devices)

    async def capability_result(
        self,
        capability,
        *,
        detailed=False,
        force=False,
    ):
        self.capability_calls.append(
            {
                "capability": capability,
                "detailed": detailed,
                "force": force,
            }
        )
        raise AssertionError(
            "Capability fallback must not run when summary values exist"
        )


def router_for(index):
    return SimpleNamespace(
        device_index=index,
        client=index.client,
        _device_rows=lambda data: data.get("devices", []),
    )


def test_humidity_read_uses_one_shared_summary_snapshot():
    index = SummaryIndex(
        [
            {
                "id": "1",
                "label": "Bathroom Meter",
                "currentStates": {
                    "humidity": {"value": 76, "unit": "%"}
                },
            },
            {
                "id": "2",
                "label": "Hallway Meter",
                "currentStates": {
                    "humidity": {"value": 58, "unit": "%"}
                },
            },
            {
                "id": "3",
                "label": "Motion Sensor",
                "currentStates": {"motion": "inactive"},
            },
        ]
    )

    executor = LiveStateSemanticMetricComparisonExecutor(
        router_for(index)
    )

    result = asyncio.run(
        executor._fresh_capability_result(_SPECS["humidity"])
    )

    assert result.is_error is False
    assert index.summary_calls == [{"force": False}]
    assert index.capability_calls == []
    assert index.client.calls == []
    assert result.data["evidenceSources"] == [
        "shared-summary-currentStates"
    ]


def test_repeated_humidity_reads_remain_on_shared_summary_path():
    index = SummaryIndex(
        [
            {
                "id": "1",
                "label": "Humidity Device",
                "currentStates": {
                    "humidity": {"value": 62.5, "unit": "%"}
                },
            }
        ]
    )

    executor = LiveStateSemanticMetricComparisonExecutor(
        router_for(index)
    )

    asyncio.run(
        executor._fresh_capability_result(_SPECS["humidity"])
    )
    asyncio.run(
        executor._fresh_capability_result(_SPECS["humidity"])
    )

    assert index.summary_calls == [
        {"force": False},
        {"force": False},
    ]
    assert index.capability_calls == []
    assert index.client.calls == []


def test_shared_summary_precedes_all_fallback_reads():
    source = (
        APP_DIR / "semantic_metric_comparison_live.py"
    ).read_text(encoding="utf-8")

    method = source.split(
        "async def _fresh_capability_result",
        1,
    )[1].split(
        "async def _fallback_detailed_result",
        1,
    )[0]

    summary_position = method.find(
        "await index.summary_result(force=False)"
    )
    fallback_position = method.find(
        "await self._collect_capability("
    )

    assert summary_position >= 0
    assert fallback_position > summary_position
    assert "shared-summary-currentStates" in method
