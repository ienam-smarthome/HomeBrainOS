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
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error

    async def call_tool(self, name, arguments):
        if self.error is not None:
            raise self.error
        return MCPToolResult(name, arguments, {}, "", {"success": True})


def clock(*values: float):
    sequence = iter(values)
    return lambda: next(sequence)


@pytest.mark.asyncio
async def test_remote_calls_accumulate_mcp_duration() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    executor = ToolExecutor(
        FakeMCP(),
        EvidenceRecorder(),
        clock=clock(1.0, 1.025, 2.0, 2.040),
    )
    try:
        await executor.execute("hub_read_devices", {})
        await executor.execute("hub_read_rules", {})
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert snapshot["timings_ms"]["mcp"] == 65


@pytest.mark.asyncio
async def test_failed_remote_call_still_records_mcp_duration() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    executor = ToolExecutor(
        FakeMCP(error=RuntimeError("offline")),
        EvidenceRecorder(),
        clock=clock(3.0, 3.018),
    )
    try:
        execution = await executor.execute("hub_read_devices", {})
        snapshot = metrics.finish("failed")
    finally:
        metrics.reset(token)

    assert execution.success is False
    assert snapshot["timings_ms"]["mcp"] == 18


@pytest.mark.asyncio
async def test_local_adapter_time_is_not_reported_as_mcp_latency() -> None:
    async def local(arguments):
        return MCPToolResult("local_read", arguments, {}, "", {"success": True})

    metrics = RequestMetrics()
    token = metrics.begin()
    executor = ToolExecutor(
        FakeMCP(),
        EvidenceRecorder(),
        local_handlers={"local_read": local},
        clock=clock(4.0, 4.050),
    )
    try:
        await executor.execute("local_read", {})
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert "mcp" not in snapshot["timings_ms"]
