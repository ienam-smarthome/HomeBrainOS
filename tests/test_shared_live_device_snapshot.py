from __future__ import annotations

from typing import Any

import pytest

from evidence_recorder import EvidenceRecorder
from mcp_client import HubitatMCPClient, MCPToolResult
from tool_executor import ToolExecutor


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@pytest.mark.asyncio
async def test_live_device_snapshot_reused_only_inside_short_ttl() -> None:
    clock = FakeClock()
    client = HubitatMCPClient("http://hubitat.test/mcp", clock=clock)
    client._initialized = True
    posts = 0

    async def fake_post(payload: dict[str, Any], allow_empty: bool = False) -> dict[str, Any]:
        nonlocal posts
        posts += 1
        return {
            "result": {
                "structuredContent": {
                    "devices": [{"id": "1", "label": f"Device {posts}"}]
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]
    arguments = {"tool": "hub_list_devices", "args": {}}

    first = await client.call_tool("hub_read_devices", arguments)
    clock.advance(1.0)
    second = await client.call_tool("hub_read_devices", arguments)

    assert posts == 1
    assert second.data == first.data
    assert second is not first

    clock.advance(1.1)
    third = await client.call_tool("hub_read_devices", arguments)
    assert posts == 2
    assert third.data != first.data

    await client.close()


@pytest.mark.asyncio
async def test_write_execution_invalidates_snapshot_before_and_after_attempt() -> None:
    class FakeMCP:
        def __init__(self) -> None:
            self.invalidations = 0

        def invalidate_live_device_snapshot(self) -> None:
            self.invalidations += 1

        async def call_tool(
            self,
            name: str,
            arguments: dict[str, Any],
        ) -> MCPToolResult:
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"success": True},
            )

    mcp = FakeMCP()
    executor = ToolExecutor(mcp, EvidenceRecorder())  # type: ignore[arg-type]

    execution = await executor.execute(
        "hub_manage_devices",
        {
            "tool": "hub_call_device_command",
            "args": {"deviceId": "1", "command": "off"},
        },
    )

    assert execution.success is True
    assert execution.effect.mutates is True
    assert mcp.invalidations == 2
