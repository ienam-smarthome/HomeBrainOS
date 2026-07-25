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
from semantic_metric_comparison import (
    SemanticMetricComparisonExecutor,
    _SPECS,
)


def result_for(name: str = "hub_list_devices") -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw={},
        text="",
        data={"devices": []},
        is_error=False,
    )


class FakeIndex:
    def __init__(self):
        self.capability_calls = []
        self.metadata_calls = []

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
        return result_for()

    async def metadata_result(self, *, force=False):
        self.metadata_calls.append({"force": force})
        return result_for()


def test_metric_capability_read_reuses_index_snapshot():
    index = FakeIndex()
    router = SimpleNamespace(device_index=index)
    executor = SemanticMetricComparisonExecutor(router)

    result = asyncio.run(
        executor._fresh_capability_result(_SPECS["power"])
    )

    assert result.is_error is False
    assert index.capability_calls == [
        {
            "capability": "Power Meter",
            "detailed": True,
            "force": False,
        }
    ]


def test_metric_metadata_fallback_does_not_force_refresh():
    index = FakeIndex()
    router = SimpleNamespace(device_index=index)
    executor = SemanticMetricComparisonExecutor(router)

    result = asyncio.run(
        executor._fallback_detailed_result()
    )

    assert result is not None
    assert index.metadata_calls == [{"force": False}]


def test_metric_source_no_longer_invalidates_before_read():
    source = (
        APP_DIR / "semantic_metric_comparison.py"
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
