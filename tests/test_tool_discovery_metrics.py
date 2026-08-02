from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402


class FakeMCP:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def call_tool(self, name, arguments):
        if self.fail:
            raise RuntimeError("search unavailable")
        return MCPToolResult(name, arguments, {}, "", {"results": []})


def clock(*values):
    sequence = iter(values)
    return lambda: next(sequence)


@pytest.mark.asyncio
async def test_successful_discovery_records_count_and_duration() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        executor = ToolExecutor(FakeMCP(), EvidenceRecorder(), clock=clock(1.0, 1.025))
        await executor.execute("hub_search_tools", {"query": "device state"})
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["counters"]["tool_discovery_calls"] == 1
    assert snapshot["timings_ms"]["tool_discovery"] == 25


@pytest.mark.asyncio
async def test_failed_discovery_is_still_measured() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        executor = ToolExecutor(FakeMCP(fail=True), EvidenceRecorder(), clock=clock(2.0, 2.04))
        execution = await executor.execute("hub_search_tools", {"query": "logs"})
        snapshot = metrics.finish("failed")
    finally:
        metrics.reset(token)

    assert execution.success is False
    assert snapshot["counters"]["tool_discovery_calls"] == 1
    assert snapshot["timings_ms"]["tool_discovery"] == 40


@pytest.mark.asyncio
async def test_non_discovery_tools_do_not_increment_discovery_metrics() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        executor = ToolExecutor(FakeMCP(), EvidenceRecorder(), clock=clock(3.0, 3.01))
        await executor.execute("hub_read_devices", {})
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert "tool_discovery_calls" not in snapshot["counters"]
    assert "tool_discovery" not in snapshot["timings_ms"]
