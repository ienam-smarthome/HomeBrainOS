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


class FakeClient:
    def __init__(self):
        self.calls = []
        self.invalidations = []

    async def invalidate(self, category):
        self.invalidations.append(category)

    async def call_tool(self, name, arguments):
        self.calls.append(
            {
                "name": name,
                "arguments": dict(arguments),
            }
        )
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "devices": [
                    {
                        "id": "1",
                        "label": "Test Power",
                        "currentStates": {
                            "power": {
                                "value": 12.5,
                                "unit": "W",
                            }
                        },
                    }
                ]
            },
            is_error=False,
        )


class FakeIndex:
    def __init__(self, client):
        self.client = client
        self.invalidations = []
        self.capability_calls = []

    async def invalidate(self):
        self.invalidations.append(True)

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
        return MCPToolResult(
            name="hub_list_devices",
            arguments={},
            raw={},
            text="",
            data={"devices": []},
            is_error=False,
        )


def test_live_metric_read_does_not_invalidate_device_cache():
    client = FakeClient()
    index = FakeIndex(client)
    router = SimpleNamespace(
        device_index=index,
        client=client,
        _device_rows=lambda data: data.get("devices", []),
    )
    executor = LiveStateSemanticMetricComparisonExecutor(router)

    result = asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )

    assert result.is_error is False
    assert client.invalidations == []
    assert index.invalidations == []
    assert len(client.calls) == 1


def test_live_metric_source_does_not_force_catalogue_refresh():
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

    assert 'invalidate("devices")' not in method
    assert "await index.invalidate()" not in method
    assert "force=True" not in method
    assert "force=False" in method
