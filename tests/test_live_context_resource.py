from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_read_contract import (  # noqa: E402
    live_context_devices,
    live_context_is_complete,
)
from device_state_summary import device_attributes  # noqa: E402
from mcp_client import HubitatMCPClient, MCPError  # noqa: E402


def _context(*, partial: bool = False) -> dict[str, Any]:
    return {
        "currentMode": "Home",
        "devices": [
            {
                "id": "1",
                "label": "Hall Motion",
                "room": "Hallway",
                "capabilities": ["MotionSensor"],
                "attributes": {"motion": "active", "battery": "71"},
            }
        ],
        "totalDevices": 1,
        "partial": partial,
        "truncated": False,
    }


def _response(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": {
            "contents": [
                {
                    "uri": "hubitat://context",
                    "mimeType": "application/json",
                    "text": json.dumps(value),
                }
            ],
            "ttlMs": 0,
            "cacheScope": "private",
        }
    }


def test_context_contract_rejects_partial_or_truncated_inventory() -> None:
    assert live_context_is_complete(_context())

    partial = _context(partial=True)
    assert not live_context_is_complete(partial)

    truncated = _context()
    truncated["truncated"] = True
    assert not live_context_is_complete(truncated)

    incomplete_ids = _context()
    incomplete_ids["idsComplete"] = False
    assert not live_context_is_complete(incomplete_ids)

    wrong_total = _context()
    wrong_total["totalDevices"] = 2
    assert not live_context_is_complete(wrong_total)


def test_context_normalization_keeps_live_values_separate_from_detailed_attributes() -> None:
    devices = live_context_devices(_context())

    assert devices == [
        {
            "id": "1",
            "label": "Hall Motion",
            "room": "Hallway",
            "capabilities": ["MotionSensor"],
            "currentStates": {"motion": "active", "battery": "71"},
        }
    ]
    assert device_attributes(devices[0]) == {"motion": "active", "battery": "71"}


@pytest.mark.asyncio
async def test_live_context_uses_two_second_cache() -> None:
    now = [100.0]
    client = HubitatMCPClient("http://hubitat.test/mcp", clock=lambda: now[0])
    client._initialized = True
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        return _response(_context())

    client._post = fake_post  # type: ignore[method-assign]

    first = await client.get_live_context()
    second = await client.get_live_context()
    assert first == second
    assert len(posts) == 1

    now[0] += 2.1
    await client.get_live_context()
    assert len(posts) == 2
    assert all(post["method"] == "resources/read" for post in posts)

    await client.close()


@pytest.mark.asyncio
async def test_concurrent_live_context_reads_are_single_flight() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    entered = asyncio.Event()
    release = asyncio.Event()
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        entered.set()
        await release.wait()
        return _response(_context())

    client._post = fake_post  # type: ignore[method-assign]

    first = asyncio.create_task(client.get_live_context())
    await entered.wait()
    second = asyncio.create_task(client.get_live_context())
    await asyncio.sleep(0)
    assert len(posts) == 1

    release.set()
    left, right = await asyncio.gather(first, second)
    assert left == right
    assert len(posts) == 1

    await client.close()


@pytest.mark.asyncio
async def test_inflight_pre_write_context_is_rejected_after_generation_invalidation() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    entered = asyncio.Event()
    release = asyncio.Event()
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        if len(posts) == 1:
            entered.set()
            await release.wait()
        value = _context()
        value["currentMode"] = "Before" if len(posts) == 1 else "After"
        return _response(value)

    client._post = fake_post  # type: ignore[method-assign]

    stale = asyncio.create_task(client.get_live_context())
    await entered.wait()
    client.invalidate_live_device_snapshot()
    release.set()

    with pytest.raises(MCPError, match="invalidated"):
        await stale

    fresh = await client.get_live_context()
    assert fresh["currentMode"] == "After"
    assert len(posts) == 2

    await client.close()
