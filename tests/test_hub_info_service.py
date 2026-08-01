from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from hub_info_service import HubInfoService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def result(name: str, arguments: dict, data, *, error=False, text=""):
    return MCPToolResult(name, arguments, {}, text, data, is_error=error)


class FakeMCP:
    def __init__(self, cached=None, responses=None):
        self.cached = list(cached or [])
        self.responses = list(responses or [])
        self.calls = []

    async def get_cached_devices(self):
        return list(self.cached)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if not self.responses:
            raise AssertionError(f"Unexpected call: {name} {arguments}")
        return self.responses.pop(0)


async def no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_invalid_scope_fails_without_calling_hubitat():
    mcp = FakeMCP()

    snapshot = await HubInfoService(mcp).snapshot({"scope": "unknown"})

    assert snapshot.is_error
    assert snapshot.data == {
        "success": False,
        "error": "scope must be firmware, resources, or full",
    }
    assert mcp.calls == []


def test_hub_info_device_requires_one_normalized_match():
    first = {"id": "1", "label": "Hub Info (C8 Pro)"}
    second = {"id": "2", "label": "HubInfo Backup"}

    assert HubInfoService.hub_info_device([first]) is first
    assert HubInfoService.hub_info_device([first, second]) is None
    assert HubInfoService.hub_info_device([{"label": "Kitchen"}]) is None


def test_nested_device_record_and_identity_merge_preserve_live_state():
    nested = {
        "result": {
            "device": {
                "id": "1089",
                "attributes": {"freeMemory": 900},
            }
        }
    }
    record = HubInfoService.find_device_record(nested)
    merged = HubInfoService.merge_device_identity(
        [record],
        [{
            "id": "1089",
            "label": "Hub Info (C8 Pro)",
            "roomName": "System",
            "attributes": {"freeMemory": 800, "hubModel": "C-8 Pro"},
        }],
    )

    assert merged == [{
        "id": "1089",
        "label": "Hub Info (C8 Pro)",
        "roomName": "System",
        "attributes": {"freeMemory": 900, "hubModel": "C-8 Pro"},
    }]


@pytest.mark.asyncio
async def test_resource_snapshot_refreshes_and_preserves_reported_units():
    cached = [{"id": "1089", "label": "Hub Info (C8 Pro)"}]
    refresh = result("hub_manage_devices", {}, {"success": True})
    live = result(
        "hub_read_devices",
        {},
        {
            "id": "1089",
            "attributes": [
                {"name": "freeMemory", "currentValue": 948.12, "unit": "MB"},
                {"name": "temperatureC", "currentValue": 49.2, "unit": "°C"},
                {"name": "dbSize", "currentValue": 31.5, "unit": "MB"},
                {"name": "cpuPct", "currentValue": 19.25},
            ],
        },
    )
    mcp = FakeMCP(cached, [refresh, live])

    snapshot = await HubInfoService(mcp, sleep=no_sleep).snapshot(
        {"scope": "resources"}
    )

    assert snapshot.data["success"] is True
    assert snapshot.data["free_memory"] == 948.12
    assert snapshot.data["free_memory_unit"] == "MB"
    assert snapshot.data["temperature"] == 49.2
    assert snapshot.data["temperature_unit"] == "°C"
    assert snapshot.data["cpu_percent"] == 19.25
    assert mcp.calls[0] == (
        "hub_manage_devices",
        {
            "tool": "hub_call_device_command",
            "args": {"deviceId": "1089", "command": "refresh"},
        },
    )


@pytest.mark.asyncio
async def test_failed_refresh_command_returns_structured_error():
    cached = [{"id": "1089", "label": "Hub Info"}]
    failed = result(
        "hub_manage_devices",
        {},
        {"success": False},
        text="command failed",
    )
    mcp = FakeMCP(cached, [failed])

    snapshot = await HubInfoService(mcp).snapshot({"scope": "resources"})

    assert snapshot.is_error
    assert snapshot.data["success"] is False
    assert "command 'refresh' failed" in snapshot.data["error"]


@pytest.mark.asyncio
async def test_missing_unique_hub_info_device_fails_closed():
    listing = result("hub_read_devices", {}, {"devices": []})
    mcp = FakeMCP([], [listing])

    snapshot = await HubInfoService(mcp).snapshot({"scope": "firmware"})

    assert snapshot.is_error
    assert "unique Hub Info device" in snapshot.data["error"]


@pytest.mark.asyncio
async def test_missing_live_attributes_stops_after_bounded_polling():
    cached = [{"id": "1089", "label": "Hub Info"}]
    refresh = result("hub_manage_devices", {}, {"success": True})
    empty_reads = [
        result("hub_read_devices", {}, {"success": True})
        for _ in range(6)
    ]
    mcp = FakeMCP(cached, [refresh, *empty_reads])

    snapshot = await HubInfoService(mcp, sleep=no_sleep).snapshot(
        {"scope": "resources"}
    )

    assert snapshot.is_error
    assert "unavailable after refresh" in snapshot.data["error"]
    assert len(mcp.calls) == 7
