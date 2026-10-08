from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult  # noqa: E402


@pytest.mark.asyncio
async def test_device_manifest_cache_honours_ttl(monkeypatch):
    clock = iter([100.0, 105.0, 113.0, 118.0, 119.0])
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
async def test_device_manifest_ttl_starts_when_slow_refresh_completes(monkeypatch):
    now = [100.0]
    client = HubitatMCPClient(
        "http://hub/mcp", device_cache_seconds=12, clock=lambda: now[0]
    )
    calls = []

    async def list_tools():
        return [MCPTool("hub_list_devices", "devices", {"type": "object"})]

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        # Model a very slow upstream read. The completed manifest should still
        # receive a full TTL instead of inheriting the pre-fetch timestamp.
        now[0] = 125.0
        return MCPToolResult(name, arguments, {}, "", [{"id": "1", "label": "Lamp"}])

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)

    assert await client.get_cached_devices() == [{"id": "1", "label": "Lamp"}]
    assert client._devices_cached_at == 125.0
    now[0] = 126.0
    assert await client.get_cached_devices() == [{"id": "1", "label": "Lamp"}]
    assert len(calls) == 1
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
async def test_device_identities_use_fresh_manifest_without_io(monkeypatch):
    client = HubitatMCPClient(
        "http://hub/mcp",
        device_cache_seconds=12,
        identity_cache_seconds=120,
        clock=lambda: 1000.0,
    )
    client._cached_devices = [{"id": "1", "label": "Livingroom Light 2"}]
    client._devices_cached_at = 950.0

    async def unexpected_live_context(*_args, **_kwargs):
        raise AssertionError("fresh identity lookup must not refresh the hub")

    monkeypatch.setattr(client, "get_live_context", unexpected_live_context)

    assert await client.get_device_identities() == [
        {"id": "1", "label": "Livingroom Light 2"}
    ]
    await client.close()


@pytest.mark.asyncio
async def test_device_identities_refresh_expired_manifest_from_bulk_context(monkeypatch):
    client = HubitatMCPClient(
        "http://hub/mcp",
        device_cache_seconds=12,
        identity_cache_seconds=120,
        clock=lambda: 1000.0,
    )
    client._cached_devices = [{"id": "old", "label": "Old Hallway Light"}]
    client._devices_cached_at = 1.0
    calls = []

    async def fresh_context(*, refresh=False):
        calls.append(refresh)
        return {
            "devices": [{
                "id": "new",
                "label": "Hallway Light 1",
                "room": "Hallway",
                "capabilities": ["Actuator", "Light", "Switch", "SwitchLevel"],
            }],
            "totalDevices": 1,
            "idsComplete": True,
            "partial": False,
            "truncated": False,
        }

    async def forbidden_manifest(*_args, **_kwargs):
        raise AssertionError("complete bulk context should avoid the detailed manifest")

    monkeypatch.setattr(client, "get_live_context", fresh_context)
    monkeypatch.setattr(client, "get_cached_devices", forbidden_manifest)

    assert client.peek_device_identities() == []
    assert await client.get_device_identities() == [{
        "id": "new",
        "label": "Hallway Light 1",
        "room": "Hallway",
        "capabilities": ["Actuator", "Light", "Switch", "SwitchLevel"],
    }]
    assert calls == [True]
    await client.close()


@pytest.mark.asyncio
async def test_identity_peek_prefers_newer_complete_source() -> None:
    client = HubitatMCPClient(
        "http://hub/mcp",
        identity_cache_seconds=120,
        clock=lambda: 1000.0,
    )
    client._cached_devices = [{"id": "old", "label": "Old name"}]
    client._devices_cached_at = 950.0
    client._live_context_snapshot = (
        990.0,
        client._live_device_snapshot_generation,
        {
            "devices": [{"id": "new", "label": "New name"}],
            "totalDevices": 1,
            "idsComplete": True,
            "partial": False,
            "truncated": False,
        },
    )

    assert client.peek_device_identities() == [{"id": "new", "label": "New name"}]
    await client.close()


@pytest.mark.asyncio
async def test_identity_refresh_falls_back_to_detailed_manifest_when_context_incomplete(
    monkeypatch,
):
    client = HubitatMCPClient(
        "http://hub/mcp",
        identity_cache_seconds=120,
        clock=lambda: 1000.0,
    )
    client._cached_devices = [{"id": "old", "label": "Old name"}]
    client._devices_cached_at = 1.0
    calls = []

    async def incomplete_context(*, refresh=False):
        calls.append(("context", refresh))
        return {
            "devices": [{"id": "partial", "label": "Partial name"}],
            "totalDevices": 2,
            "idsComplete": False,
        }

    async def fresh_manifest(*, refresh=False):
        calls.append(("manifest", refresh))
        client._cached_devices = [{"id": "new", "label": "Fresh detailed name"}]
        client._devices_cached_at = 1000.0
        return list(client._cached_devices)

    monkeypatch.setattr(client, "get_live_context", incomplete_context)
    monkeypatch.setattr(client, "get_cached_devices", fresh_manifest)

    assert await client.get_device_identities() == [
        {"id": "new", "label": "Fresh detailed name"}
    ]
    assert calls == [("context", True), ("manifest", True)]
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
                        "capabilities", "attributes", "commands", "lastActivity",
                ],
                "limit": 50,
                "offset": 0,
            },
        },
    )]
    await client.close()


@pytest.mark.asyncio
async def test_device_manifest_pagination_follows_advancing_offsets(monkeypatch):
    """A well-behaved paginated gateway should still fetch every page."""

    client = HubitatMCPClient("http://hub/mcp")
    pages = [
        {"devices": [{"id": "1"}], "hasMore": True, "nextOffset": 50},
        {"devices": [{"id": "2"}], "hasMore": True, "nextOffset": 100},
        {"devices": [{"id": "3"}], "hasMore": False, "nextOffset": None},
    ]
    calls = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "device gateway", {"type": "object"})]

    async def call_tool(name, arguments):
        calls.append(arguments["args"]["offset"])
        return MCPToolResult(name, arguments, {}, "", {"result": pages[len(calls) - 1]})

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)

    devices = await client.get_cached_devices()

    assert devices == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert calls == [0, 50, 100]
    await client.close()


@pytest.mark.asyncio
async def test_device_manifest_pagination_stops_on_non_advancing_offset(monkeypatch):
    """A broken upstream that repeats the same nextOffset must not loop forever."""

    client = HubitatMCPClient("http://hub/mcp")
    calls = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "device gateway", {"type": "object"})]

    async def call_tool(name, arguments):
        offset = arguments["args"]["offset"]
        calls.append(offset)
        return MCPToolResult(
            name,
            arguments,
            {},
            "",
            {"result": {
                "devices": [{"id": str(offset)}],
                "hasMore": True,
                # Always repeats the same offset instead of advancing.
                "nextOffset": 0,
            }},
        )

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)

    devices = await client.get_cached_devices()

    assert calls == [0]
    assert devices == [{"id": "0"}]
    await client.close()


@pytest.mark.asyncio
async def test_device_manifest_pagination_is_bounded_by_a_hard_page_cap(monkeypatch):
    """A misbehaving upstream that always reports hasMore=True with a
    genuinely advancing offset must still terminate eventually.
    """

    client = HubitatMCPClient("http://hub/mcp")
    calls = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "device gateway", {"type": "object"})]

    async def call_tool(name, arguments):
        offset = arguments["args"]["offset"]
        calls.append(offset)
        next_offset = offset + 50
        return MCPToolResult(
            name,
            arguments,
            {},
            "",
            {"result": {
                "devices": [{"id": str(offset)}],
                "hasMore": True,
                "nextOffset": next_offset,
            }},
        )

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)

    devices = await client.get_cached_devices()

    assert len(calls) == HubitatMCPClient._MAX_DEVICE_PAGES
    assert len(devices) == HubitatMCPClient._MAX_DEVICE_PAGES
    await client.close()



@pytest.mark.asyncio
async def test_health_audit_uses_fresh_lean_projection_and_concurrent_verified_pages(monkeypatch):
    """Fresh state survives, while command-bearing global cache is unchanged."""
    import asyncio

    client = HubitatMCPClient("http://hub/mcp", max_concurrent_calls=2)
    client._cached_devices = [{
        "id": "existing", "label": "Legacy device", "commands": ["on", "off"]
    }]
    peak = active = 0
    requests = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "gateway", {"type": "object"})]

    async def call_tool(name, arguments):
        nonlocal active, peak
        assert name == "hub_read_devices"
        assert arguments["tool"] == "hub_list_devices"
        args = arguments["args"]
        assert args["detailed"] is True
        assert args["fields"] == [
            "id", "name", "label", "room", "capabilities", "attributes",
            "lastActivity",
        ]
        offset = args["offset"]
        requests.append(offset)
        active += 1
        peak = max(peak, active)
        if offset != 0:
            await asyncio.sleep(0.02)
        active -= 1
        count = min(50, 120 - offset)
        page = {
            "devices": [
                {"id": str(i), "label": f"Device {i}",
                 "capabilities": ["Battery"],
                 "attributes": [{"name": "battery", "currentValue": 85}],
                 "lastActivity": "2026-10-08T13:00:00Z"}
                for i in range(offset, offset + count)
            ],
            "total": 120,
            "hasMore": offset + count < 120,
            "nextOffset": offset + count if offset + count < 120 else None,
        }
        return MCPToolResult(name, arguments, {}, "", {"result": page})

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)
    devices, metrics = await client.get_audit_devices()
    assert len(devices) == 120
    assert requests[0] == 0
    assert set(requests) == {0, 50, 100}
    assert peak == 2
    assert metrics["source"] == "fresh_projected_gateway"
    assert metrics["mode"] == "bounded_parallel_pages"
    assert metrics["complete"] is True
    assert metrics["pages"] == 3
    assert client._cached_devices[0]["commands"] == ["on", "off"]
    await client.close()


@pytest.mark.asyncio
async def test_health_audit_rejects_missing_state_on_any_page_and_falls_back(monkeypatch):
    client = HubitatMCPClient("http://hub/mcp")
    full_reads = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "gateway", {"type": "object"})]

    async def call_tool(name, args):
        return MCPToolResult(name, args, {}, "", {"result": {
            "devices": [{"id": "1", "label": "Contact"}],
            "total": 1, "hasMore": False,
        }})

    async def full_read(*, refresh=False):
        full_reads.append(refresh)
        return [{
            "id": "1", "label": "Contact",
            "attributes": [{"name": "contact", "currentValue": "open"}],
            "commands": ["refresh"],
        }]

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)
    monkeypatch.setattr(client, "get_cached_devices", full_read)
    devices, metrics = await client.get_audit_devices()
    assert full_reads == [True]
    assert devices[0]["commands"] == ["refresh"]
    assert metrics["source"] == "full_detailed_fallback"
    assert metrics["complete"] is False
    await client.close()


@pytest.mark.asyncio
async def test_health_audit_rejects_duplicate_page_ids_and_falls_back(monkeypatch):
    client = HubitatMCPClient("http://hub/mcp")
    fallbacks = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "gateway", {"type": "object"})]

    async def call_tool(name, args):
        offset = args["args"]["offset"]
        page = {
            "devices": [
                {"id": str(i if offset == 0 else i - 50),
                 "attributes": []}
                for i in range(offset, offset + 50)
            ],
            "total": 100, "hasMore": offset == 0,
            "nextOffset": 50 if offset == 0 else None,
        }
        return MCPToolResult(name, args, {}, "", page)

    async def full_read(*, refresh=False):
        fallbacks.append(refresh)
        return [{"id": "stable", "label": "Safe full result", "attributes": []}]

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)
    monkeypatch.setattr(client, "get_cached_devices", full_read)
    devices, metrics = await client.get_audit_devices()
    assert fallbacks == [True]
    assert len(devices) == 1 and devices[0]["id"] == "stable"
    assert metrics["source"] == "full_detailed_fallback"
    await client.close()


@pytest.mark.asyncio
async def test_health_audit_serial_pages_when_total_not_reported(monkeypatch):
    client = HubitatMCPClient("http://hub/mcp", max_concurrent_calls=2)
    requests = []

    async def list_tools():
        return [MCPTool("hub_read_devices", "gateway", {"type": "object"})]

    async def call_tool(name, args):
        offset = args["args"]["offset"]
        requests.append(offset)
        return MCPToolResult(name, args, {}, "", {
            "devices": [{"id": str(offset), "attributes": []}],
            "hasMore": offset == 0,
            "nextOffset": 50 if offset == 0 else None,
        })

    monkeypatch.setattr(client, "list_tools", list_tools)
    monkeypatch.setattr(client, "call_tool", call_tool)
    devices, metrics = await client.get_audit_devices()
    assert [item["id"] for item in devices] == ["0", "50"]
    assert requests == [0, 50]
    assert metrics["mode"] == "verified_serial_pages"
    assert metrics["complete"] is True
    await client.close()
