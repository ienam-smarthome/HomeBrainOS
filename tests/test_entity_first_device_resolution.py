from __future__ import annotations

import asyncio
from typing import Any

from device_query_service import DeviceQueryService
from mcp_client import MCPToolResult


class FakeMCP:
    def __init__(self, devices: list[dict[str, Any]]) -> None:
        self.devices = devices
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"devices": self.devices},
        )

    async def get_cached_devices(self) -> list[dict[str, Any]]:
        return list(self.devices)


def run(coro):
    return asyncio.run(coro)


def test_named_device_resolution_reads_complete_inventory_without_name_filter() -> None:
    devices = [
        {
            "id": "101",
            "label": "Bathroom Meter",
            "room": "Bathroom",
            "attributes": {"battery": 66, "humidity": 58},
        },
        {
            "id": "102",
            "label": "Bedroom 1 Meter",
            "room": "Bedroom 1",
            "attributes": {"battery": 73},
        },
    ]
    mcp = FakeMCP(devices)
    evidence: list[dict[str, Any]] = []
    service = DeviceQueryService(
        mcp, lambda tool, arguments, **extra: evidence.append(
            {"tool": tool, "arguments": arguments, **extra}
        )
    )

    result = run(service.resolve_device({"name": "Bathroom Meter"}))

    assert result.is_error is False
    assert result.data["matched"] is True
    assert result.data["deviceId"] == "101"
    assert result.data["label"] == "Bathroom Meter"
    assert result.data["target"]["attributes"]["battery"] == 66
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert "filter" not in mcp.calls[0][1]["args"]
    assert result.data["attempts"] == [
        {"source": "complete_inventory", "count": 2}
    ]
    assert evidence[0]["evidence_kind"] == "authoritative_state_snapshot"


def test_missing_named_device_remains_unmatched_after_complete_scan() -> None:
    mcp = FakeMCP([
        {"id": "102", "label": "Bedroom 1 Meter", "attributes": {"battery": 73}}
    ])
    service = DeviceQueryService(mcp, lambda *args, **kwargs: None)

    result = run(service.resolve_device({"name": "Bathroom Meter"}))

    assert result.is_error is False
    assert result.data["matched"] is False
    assert result.data["deviceId"] is None
    assert result.data["attempts"][0]["count"] == 1
    assert mcp.calls[0][1] == {"tool": "hub_list_devices", "args": {}}


def test_device_name_is_never_forwarded_as_hubitat_filter() -> None:
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "hubitat-mcp-ai"
        / "rootfs"
        / "app"
        / "device_query_service.py"
    ).read_text(encoding="utf-8")

    resolve_block = source.split("async def resolve_device", 1)[1].split(
        "async def query_devices", 1
    )[0]
    assert '"filter": variant' not in resolve_block
    assert '"args": {"filter"' not in resolve_block
    assert "_live_devices(enrich_identity=True)" in resolve_block
