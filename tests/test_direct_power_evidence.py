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


class RecordingClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "devices": [
                    {
                        "id": "1",
                        "label": "Fridge",
                        "room": "Kitchen",
                        "attributes": {
                            "power": {
                                "value": 82,
                                "unit": "W",
                            }
                        },
                    },
                    {
                        "id": "2",
                        "label": "Freezer",
                        "room": "Kitchen",
                        "attributes": {
                            "power": {
                                "value": 1,
                                "unit": "W",
                            }
                        },
                    },
                ]
            },
            is_error=False,
        )


class RejectingIndex:
    def __init__(self, client):
        self.client = client

    async def summary_result(self, *, force=False):
        raise AssertionError(
            "Power must return before summary fallback"
        )

    async def capability_result(
        self,
        capability,
        *,
        detailed=False,
        force=False,
    ):
        raise AssertionError(
            "Power must return before capability fallback"
        )


def router_for(client):
    index = RejectingIndex(client)
    return SimpleNamespace(
        device_index=index,
        client=client,
        _device_rows=lambda data: data.get("devices", []),
    )


def test_power_uses_one_detailed_all_device_read():
    client = RecordingClient()
    executor = LiveStateSemanticMetricComparisonExecutor(
        router_for(client)
    )

    result = asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )

    assert result.is_error is False
    assert len(client.calls) == 1

    name, arguments = client.calls[0]
    assert name == "hub_list_devices"
    assert arguments == {
        "detailed": True,
        "format": "detailed",
        "fields": [
            "id",
            "name",
            "label",
            "room",
            "attributes",
            "disabled",
            "lastActivity",
        ],
    }
    assert result.data["evidenceSources"] == [
        "all-device-detailed-attributes"
    ]


def test_power_direct_read_preserves_all_measurements():
    client = RecordingClient()
    executor = LiveStateSemanticMetricComparisonExecutor(
        router_for(client)
    )

    result = asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )

    rows = result.data["devices"]
    assert len(rows) == 2
    assert rows[0]["attributes"]["power"]["value"] == 82
    assert rows[1]["attributes"]["power"]["value"] == 1
