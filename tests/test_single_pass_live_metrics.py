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
        self.calls.append(
            {
                "name": name,
                "arguments": dict(arguments),
            }
        )
        raise AssertionError(
            "Direct broker call should not be needed when "
            "the shared capability snapshot contains live values"
        )


class SnapshotIndex:
    def __init__(self, devices):
        self.devices = devices
        self.calls = []
        self.client = RejectingClient()

    async def capability_result(
        self,
        capability,
        *,
        detailed=False,
        force=False,
    ):
        self.calls.append(
            {
                "capability": capability,
                "detailed": detailed,
                "force": force,
            }
        )
        return tool_result(self.devices)


def router_for(index):
    return SimpleNamespace(
        device_index=index,
        client=index.client,
        _device_rows=lambda data: data.get("devices", []),
    )


def test_live_metric_uses_one_shared_capability_snapshot():
    index = SnapshotIndex(
        [
            {
                "id": "1",
                "label": "Freezer",
                "currentStates": {
                    "power": {
                        "value": 76,
                        "unit": "W",
                    }
                },
            },
            {
                "id": "2",
                "label": "Computer",
                "currentStates": {
                    "power": {
                        "value": 28,
                        "unit": "W",
                    }
                },
            },
        ]
    )

    executor = LiveStateSemanticMetricComparisonExecutor(
        router_for(index)
    )

    result = asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )

    assert result.is_error is False
    assert index.calls == [
        {
            "capability": "Power Meter",
            "detailed": False,
            "force": False,
        }
    ]
    assert index.client.calls == []
    assert result.data["evidenceSources"] == [
        "capability-snapshot-currentStates"
    ]
    assert len(result.data["devices"]) == 2


def test_repeated_live_metric_reads_stay_on_snapshot_path():
    index = SnapshotIndex(
        [
            {
                "id": "1",
                "label": "Power Device",
                "currentStates": {
                    "power": {
                        "value": 12.5,
                        "unit": "W",
                    }
                },
            }
        ]
    )

    executor = LiveStateSemanticMetricComparisonExecutor(
        router_for(index)
    )

    asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )
    asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )

    assert len(index.calls) == 2
    assert all(
        call == {
            "capability": "Power Meter",
            "detailed": False,
            "force": False,
        }
        for call in index.calls
    )
    assert index.client.calls == []


def test_snapshot_path_precedes_direct_capability_fallback():
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

    snapshot_position = method.find(
        "await index.capability_result("
    )
    direct_position = method.find(
        "await self._collect_capability("
    )

    assert snapshot_position >= 0
    assert direct_position > snapshot_position
    assert "detailed=False" in method
    assert "force=False" in method
