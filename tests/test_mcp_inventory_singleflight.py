from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import HubitatMCPClient, MCPTool  # noqa: E402


@pytest.mark.asyncio
async def test_live_snapshot_joins_inflight_manifest_without_duplicate_post() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    client._tools = {
        "hub_read_devices": MCPTool(
            "hub_read_devices", "device gateway", {"type": "object"}
        )
    }

    started = asyncio.Event()
    release = asyncio.Event()
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        del allow_empty
        posts.append(payload)
        args = payload["params"]["arguments"]["args"]
        if args.get("detailed") is True:
            started.set()
            await release.wait()
            return {
                "result": {
                    "structuredContent": {
                        "devices": [
                            {
                                "id": "1",
                                "label": "Living Room Motion",
                                "room": "Living Room",
                            }
                        ],
                        "hasMore": False,
                    }
                }
            }
        raise AssertionError("aggregate read issued a duplicate hub_list_devices POST")

    client._post = fake_post  # type: ignore[method-assign]

    manifest_task = asyncio.create_task(client.get_cached_devices(refresh=True))
    await asyncio.wait_for(started.wait(), timeout=1)

    snapshot_task = asyncio.create_task(
        client.call_tool(
            "hub_read_devices", {"tool": "hub_list_devices", "args": {}}
        )
    )
    await asyncio.sleep(0)
    assert not snapshot_task.done()

    release.set()
    manifest, snapshot = await asyncio.gather(manifest_task, snapshot_task)

    assert len(posts) == 1
    assert manifest == [
        {"id": "1", "label": "Living Room Motion", "room": "Living Room"}
    ]
    assert snapshot.data == {"devices": manifest}
    await client.close()


@pytest.mark.asyncio
async def test_manifest_singleflight_coalesces_two_refresh_callers() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    client._tools = {
        "hub_read_devices": MCPTool(
            "hub_read_devices", "device gateway", {"type": "object"}
        )
    }

    started = asyncio.Event()
    release = asyncio.Event()
    posts = 0

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        nonlocal posts
        del payload, allow_empty
        posts += 1
        started.set()
        await release.wait()
        return {
            "result": {
                "structuredContent": {
                    "devices": [{"id": "1", "label": "Lamp"}],
                    "hasMore": False,
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]

    first = asyncio.create_task(client.get_cached_devices(refresh=True))
    await asyncio.wait_for(started.wait(), timeout=1)
    second = asyncio.create_task(client.get_cached_devices(refresh=True))
    await asyncio.sleep(0)

    release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert posts == 1
    assert first_result == second_result == [{"id": "1", "label": "Lamp"}]
    await client.close()


@pytest.mark.asyncio
async def test_write_invalidation_prevents_reusing_inflight_manifest_snapshot() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    client._tools = {
        "hub_read_devices": MCPTool(
            "hub_read_devices", "device gateway", {"type": "object"}
        )
    }

    started = asyncio.Event()
    release = asyncio.Event()
    posts = 0

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        nonlocal posts
        del allow_empty
        posts += 1
        args = payload["params"]["arguments"]["args"]
        if args.get("detailed") is True:
            started.set()
            await release.wait()
            devices = [{"id": "1", "label": "Before write"}]
        else:
            devices = [{"id": "1", "label": "After write"}]
        return {"result": {"structuredContent": {"devices": devices, "hasMore": False}}}

    client._post = fake_post  # type: ignore[method-assign]

    manifest_task = asyncio.create_task(client.get_cached_devices(refresh=True))
    await asyncio.wait_for(started.wait(), timeout=1)
    snapshot_task = asyncio.create_task(
        client.call_tool(
            "hub_read_devices", {"tool": "hub_list_devices", "args": {}}
        )
    )
    await asyncio.sleep(0)

    client.invalidate_live_device_snapshot()
    release.set()

    await manifest_task
    snapshot = await snapshot_task

    assert posts == 2
    assert snapshot.data["devices"] == [{"id": "1", "label": "After write"}]
    await client.close()
