from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import HubitatMCPClient  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def command_arguments(device_id: str) -> dict[str, Any]:
    return {
        "tool": "hub_call_device_command",
        "args": {
            "deviceId": device_id,
            "command": "off",
            "waitFor": {
                "attribute": "switch",
                "expectedValue": "off",
                "timeoutMs": 5000,
            },
        },
    }


def success_response() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "result": {
            "structuredContent": {
                "success": True,
                "waitFor": {"converged": True, "value": "off"},
            }
        },
    }


@pytest.mark.asyncio
async def test_two_independent_tool_calls_can_overlap_and_report_peak() -> None:
    client = HubitatMCPClient(
        "http://hubitat.test/mcp",
        max_concurrent_calls=2,
    )
    client._initialized = True

    active = 0
    peak = 0
    posts = 0
    both_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_post(
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        nonlocal active, peak, posts
        del payload, allow_empty
        posts += 1
        active += 1
        peak = max(peak, active)
        if active >= 2:
            both_started.set()
        try:
            await release.wait()
            return success_response()
        finally:
            active -= 1

    client._post = fake_post  # type: ignore[method-assign]
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        first = asyncio.create_task(
            client.call_tool("hub_manage_devices", command_arguments("1"))
        )
        second = asyncio.create_task(
            client.call_tool("hub_manage_devices", command_arguments("2"))
        )
        await asyncio.wait_for(both_started.wait(), timeout=1)

        assert posts == 2
        assert peak == 2
        assert not first.done()
        assert not second.done()

        release.set()
        first_result, second_result = await asyncio.gather(first, second)
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)
        await client.close()

    assert first_result.is_error is False
    assert second_result.is_error is False
    assert snapshot["counters"]["mcp_concurrent_peak"] == 2
    assert "mcp_queue_wait" in snapshot["timings_ms"]
    assert "mcp_http" in snapshot["timings_ms"]


@pytest.mark.asyncio
async def test_concurrency_setting_one_restores_serial_tool_calls() -> None:
    client = HubitatMCPClient(
        "http://hubitat.test/mcp",
        max_concurrent_calls=1,
    )
    client._initialized = True

    posts = 0
    active = 0
    peak = 0
    first_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_post(
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        nonlocal posts, active, peak
        del payload, allow_empty
        posts += 1
        active += 1
        peak = max(peak, active)
        first_started.set()
        try:
            await release.wait()
            return success_response()
        finally:
            active -= 1

    client._post = fake_post  # type: ignore[method-assign]

    first = asyncio.create_task(
        client.call_tool("hub_manage_devices", command_arguments("1"))
    )
    await asyncio.wait_for(first_started.wait(), timeout=1)
    second = asyncio.create_task(
        client.call_tool("hub_manage_devices", command_arguments("2"))
    )
    await asyncio.sleep(0)

    assert posts == 1
    assert peak == 1
    assert not second.done()

    release.set()
    await asyncio.gather(first, second)
    assert posts == 2
    assert peak == 1
    await client.close()


@pytest.mark.asyncio
async def test_cacheable_live_snapshot_stays_singleflight_under_concurrency() -> None:
    client = HubitatMCPClient(
        "http://hubitat.test/mcp",
        max_concurrent_calls=2,
    )
    client._initialized = True

    posts = 0
    first_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_post(
        payload: dict[str, Any],
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        nonlocal posts
        del allow_empty
        posts += 1
        first_started.set()
        await release.wait()
        return {
            "jsonrpc": "2.0",
            "result": {
                "structuredContent": {
                    "devices": [{"id": "1", "label": "Hallway Light 1"}]
                }
            },
        }

    client._post = fake_post  # type: ignore[method-assign]
    args = {"tool": "hub_list_devices", "args": {}}

    first = asyncio.create_task(client.call_tool("hub_read_devices", dict(args)))
    await asyncio.wait_for(first_started.wait(), timeout=1)
    second = asyncio.create_task(client.call_tool("hub_read_devices", dict(args)))
    await asyncio.sleep(0)

    assert posts == 1
    assert not second.done()

    release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert posts == 1
    assert first_result.data == second_result.data
    assert first_result.data["devices"][0]["label"] == "Hallway Light 1"
    await client.close()
