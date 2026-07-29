from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult  # noqa: E402


@pytest.mark.asyncio
async def test_device_manifest_cache_honours_ttl(monkeypatch):
    clock = iter([100.0, 105.0, 113.0])
    client = HubitatMCPClient(
        "http://hub/mcp", device_cache_seconds=12, clock=lambda: next(clock)
    )
    calls = []

    async def list_tools():
        return [MCPTool("hub_list_devices", "devices", {"type": "object"})]

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        return MCPToolResult(name, arguments, {}, "", [{"id": "1", "label": "Lamp"}])

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)

    assert await client.get_cached_devices() == [{"id": "1", "label": "Lamp"}]
    assert await client.get_cached_devices() == [{"id": "1", "label": "Lamp"}]
    assert await client.get_cached_devices() == [{"id": "1", "label": "Lamp"}]
    assert len(calls) == 2
    await client.close()


@pytest.mark.asyncio
async def test_device_manifest_refresh_bypasses_cache(monkeypatch):
    client = HubitatMCPClient("http://hub/mcp", device_cache_seconds=60)
    calls = []

    async def list_tools():
        return [MCPTool("get_devices", "devices", {"type": "object"})]

    async def call_tool(name, arguments):
        calls.append(name)
        return MCPToolResult(name, arguments, {}, "", {"devices": [{"id": "2"}]})

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)
    await client.get_cached_devices()
    await client.get_cached_devices(refresh=True)
    assert calls == ["get_devices", "get_devices"]
    await client.close()


@pytest.mark.asyncio
async def test_device_identities_use_known_manifest_without_ttl_refresh(monkeypatch):
    client = HubitatMCPClient(
        "http://hub/mcp",
        device_cache_seconds=12,
        clock=lambda: 1000.0,
    )
    client._cached_devices = [{"id": "1", "label": "Livingroom Light 2"}]
    client._devices_cached_at = 1.0

    async def unexpected_list_tools():
        raise AssertionError("identity lookup must not refresh live device state")

    monkeypatch.setattr(client, "list_tools", unexpected_list_tools)

    assert await client.get_device_identities() == [
        {"id": "1", "label": "Livingroom Light 2"}
    ]
    await client.close()


@pytest.mark.asyncio
async def test_device_manifest_uses_consolidated_read_gateway(monkeypatch):
    client = HubitatMCPClient("http://hub/mcp")
    calls = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "device gateway", {"type": "object"})]

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        return MCPToolResult(
            name,
            arguments,
            {},
            "",
            {"result": {"devices": [{"id": "7", "label": "Kitchen Light"}]}},
        )

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)

    devices = await client.get_cached_devices()

    assert devices == [{"id": "7", "label": "Kitchen Light"}]
    assert calls == [(
        "hub_read_devices",
        {
            "tool": "hub_list_devices",
            "args": {
                "detailed": True,
                "fields": [
                    "id", "name", "label", "room",
                    "capabilities", "attributes",
                ],
                "limit": 50,
                "offset": 0,
            },
        },
    )]
    await client.close()
