from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import (  # noqa: E402
    DEVICE_GATEWAY,
    EVENT_OPERATION,
    DeviceHistoryService,
)
from mcp_client import MCPToolResult  # noqa: E402


class SmallLimitHistoryMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == DEVICE_GATEWAY
        assert arguments.get("tool") == EVENT_OPERATION
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
                        "date": "2026-10-05T12:00:00.000+0100",
                        "isStateChange": True,
                    },
                    {
                        "name": "switch",
                        "value": "on",
                        "date": "2026-10-05T11:00:00.000+0100",
                        "isStateChange": True,
                    },
                    {
                        "name": "switch",
                        "value": "off",
                        "date": "2026-10-05T10:00:00.000+0100",
                        "isStateChange": True,
                    },
                    {
                        "name": "switch",
                        "value": "on",
                        "date": "2026-10-05T09:00:00.000+0100",
                        "isStateChange": True,
                    },
                ],
                "count": 4,
            },
        )


@pytest.mark.asyncio
async def test_limit_one_only_limits_presented_events_not_temporal_analysis() -> None:
    mcp = SmallLimitHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history(
        {
            "name": "Bathroom Light 1",
            "attribute": "switch",
            "limit": 1,
            "_resolved_target": {
                "id": "7818",
                "label": "Bathroom Light 1",
                "capabilities": ["Switch"],
                "attributes": ["switch"],
            },
        }
    )

    assert result.is_error is False
    assert result.data["count"] == 1
    assert len(result.data["events"]) == 1
    assert result.data["analysisEventCount"] == 4
    assert result.data["sourceEventCount"] == 4

    analysis = result.data["temporalAnalysis"]
    assert analysis["intervalCount"] == 2
    assert analysis["totalActiveSeconds"] == 7200
    assert analysis["totalActiveDuration"] == "2h"
