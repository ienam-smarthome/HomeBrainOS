from __future__ import annotations

import pytest

from device_query_service import DeviceQueryService
from mcp_client import MCPToolResult
from request_metrics import RequestMetrics


class FakeMCP:
    def __init__(self) -> None:
        self.calls = 0

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        self.calls += 1
        devices = [
            {
                "id": "1",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "attributes": {"temperature": 26.8, "humidity": 35},
            },
            {
                "id": "2",
                "label": "Bedroom 1 TRV",
                "room": "Bedroom 1",
                "attributes": {"temperature": 26.5},
            },
        ]
        return MCPToolResult(tool_name, arguments, {}, "ok", {"devices": devices})

    async def get_cached_devices(self) -> list[dict]:
        return []


@pytest.mark.asyncio
async def test_device_snapshot_is_reused_only_within_active_request() -> None:
    mcp = FakeMCP()
    evidence: list[tuple] = []
    service = DeviceQueryService(mcp, lambda *args, **kwargs: evidence.append((args, kwargs)))
    metrics = RequestMetrics()

    first = metrics.begin()
    try:
        filtered = await service.filter_devices({"attribute": "temperature", "operator": "exists"})
        resolved = await service.resolve_device({"name": "Bedroom 1"})
        assert not filtered.is_error
        assert not resolved.is_error
        assert mcp.calls == 1
        assert len(evidence) == 1
    finally:
        metrics.reset(first)

    second = metrics.begin()
    try:
        await service.filter_devices({"attribute": "humidity", "operator": "exists"})
        assert mcp.calls == 2
        assert len(evidence) == 2
    finally:
        metrics.reset(second)
