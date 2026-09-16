from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


class ActiveRoomMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        devices = [
            {
                "id": "1",
                "label": "Living Room Motion",
                "room": "Living Room",
                "capabilities": ["MotionSensor"],
                "attributes": {"motion": "active"},
            },
            {
                "id": "2",
                "label": "Bedroom Lamp",
                "room": "Bedroom 1",
                "capabilities": ["Switch"],
                "attributes": {"switch": "off"},
            },
        ]
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"devices": devices, "hasMore": False},
        )


@pytest.mark.asyncio
async def test_active_rooms_uses_narrow_gateway_fields() -> None:
    mcp = ActiveRoomMCP()
    receipts = []
    service = DeviceQueryService(
        mcp, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.active_rooms({})

    assert result.data["active_rooms"] == [
        {"name": "Living Room", "reasons": ["motion"]}
    ]
    assert result.data["read_scope"] == "active-room fields only"
    assert len(mcp.calls) == 1
    tool_name, arguments = mcp.calls[0]
    assert tool_name == "hub_read_devices"
    assert arguments["tool"] == "hub_list_devices"
    assert arguments["args"] == {
        "detailed": True,
        "fields": [
            "id", "name", "label", "room", "capabilities", "attributes"
        ],
        "limit": 200,
        "offset": 0,
    }
    assert len(receipts) == 1
    assert receipts[0][1]["evidence_kind"] == "authoritative_state_snapshot"


@pytest.mark.asyncio
async def test_active_rooms_follows_gateway_pagination() -> None:
    class PagedMCP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
            self.calls.append((name, arguments))
            offset = arguments["args"]["offset"]
            if offset == 0:
                data = {
                    "devices": [{
                        "id": "1",
                        "label": "Hall Motion",
                        "room": "Hallway",
                        "capabilities": ["MotionSensor"],
                        "attributes": {"motion": "active"},
                    }],
                    "hasMore": True,
                    "nextOffset": 1,
                }
            else:
                data = {
                    "devices": [{
                        "id": "2",
                        "label": "Kitchen Light",
                        "room": "Kitchen",
                        "capabilities": ["Light", "Switch"],
                        "attributes": {"switch": "on"},
                    }],
                    "hasMore": False,
                }
            return MCPToolResult(name, arguments, {}, "ok", data)

    mcp = PagedMCP()
    service = DeviceQueryService(mcp, lambda *_a, **_k: None)

    result = await service.active_rooms({})

    assert {item["name"] for item in result.data["active_rooms"]} == {
        "Hallway", "Kitchen"
    }
    assert len(mcp.calls) == 2
    assert mcp.calls[1][1]["args"]["offset"] == 1
