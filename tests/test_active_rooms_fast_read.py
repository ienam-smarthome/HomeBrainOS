from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import HubitatMCPClient, MCPToolResult  # noqa: E402


class ActiveRoomMCP(HubitatMCPClient):
    def __init__(self) -> None:
        # Deliberately do not construct the transport: these tests exercise the
        # production-client branch while replacing call_tool with a deterministic
        # fake upstream.
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        args = arguments.get("args") or {}
        capability = args.get("capabilityFilter")
        if capability == "MotionSensor":
            devices = [
                {
                    "id": "1",
                    "label": "Living Room Motion",
                    "room": "Living Room",
                    "capabilities": ["MotionSensor"],
                    "currentStates": [
                        {"name": "motion", "currentValue": "active"}
                    ],
                }
            ]
        elif capability == "Switch":
            devices = [
                {
                    "id": "2",
                    "label": "Bedroom Lamp",
                    "room": "Bedroom 1",
                    "capabilities": ["Switch"],
                    "currentStates": [
                        {"name": "switch", "currentValue": "off"}
                    ],
                },
                {
                    "id": "3",
                    "label": "Kitchen Light",
                    "room": "Kitchen",
                    "capabilities": ["Light", "Switch"],
                    "currentStates": [
                        {"name": "switch", "currentValue": "on"}
                    ],
                },
            ]
        else:
            devices = []
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"devices": devices, "hasMore": False},
        )


@pytest.mark.asyncio
async def test_active_rooms_uses_capability_filtered_current_states() -> None:
    mcp = ActiveRoomMCP()
    receipts = []
    service = DeviceQueryService(
        mcp, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.active_rooms({})

    assert result.data["active_rooms"] == [
        {"name": "Kitchen", "reasons": ["light on"]},
        {"name": "Living Room", "reasons": ["motion"]},
    ]
    assert result.data["read_scope"] == (
        "capability-filtered motion/switch currentStates"
    )
    assert len(mcp.calls) == 2
    assert [call[1]["args"]["capabilityFilter"] for call in mcp.calls] == [
        "MotionSensor",
        "Switch",
    ]
    for tool_name, arguments in mcp.calls:
        assert tool_name == "hub_read_devices"
        assert arguments["tool"] == "hub_list_devices"
        assert arguments["args"]["fields"] == [
            "id", "name", "label", "room", "capabilities", "currentStates"
        ]
        assert arguments["args"]["limit"] == 100
    assert len(receipts) == 1
    assert receipts[0][1]["evidence_kind"] == "authoritative_state_snapshot"
    assert receipts[0][1]["summary"].startswith("3 capability-filtered")


@pytest.mark.asyncio
async def test_active_rooms_follows_pagination_per_capability() -> None:
    class PagedMCP(HubitatMCPClient):
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
            self.calls.append((name, arguments))
            args = arguments["args"]
            capability = args["capabilityFilter"]
            offset = args["offset"]
            if capability == "MotionSensor" and offset == 0:
                data = {
                    "devices": [{
                        "id": "1",
                        "label": "Hall Motion",
                        "room": "Hallway",
                        "capabilities": ["MotionSensor"],
                        "currentStates": [
                            {"name": "motion", "currentValue": "active"}
                        ],
                    }],
                    "hasMore": True,
                    "nextOffset": 1,
                }
            elif capability == "MotionSensor":
                data = {"devices": [], "hasMore": False}
            else:
                data = {
                    "devices": [{
                        "id": "2",
                        "label": "Kitchen Light",
                        "room": "Kitchen",
                        "capabilities": ["Light", "Switch"],
                        "currentStates": [
                            {"name": "switch", "currentValue": "on"}
                        ],
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
    assert len(mcp.calls) == 3
    assert mcp.calls[1][1]["args"]["offset"] == 1


@pytest.mark.asyncio
async def test_active_rooms_zero_filtered_records_falls_back_to_full_inventory() -> None:
    class EmptyProjectionMCP(HubitatMCPClient):
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
            self.calls.append((name, arguments))
            args = arguments.get("args") or {}
            if args.get("capabilityFilter"):
                data = {"devices": [], "hasMore": False}
            else:
                data = {
                    "devices": [{
                        "id": "7",
                        "label": "Fallback Motion",
                        "room": "Office",
                        "capabilities": ["MotionSensor"],
                        "attributes": {"motion": "active"},
                    }]
                }
            return MCPToolResult(name, arguments, {}, "ok", data)

        async def get_cached_devices(self):
            return []

    mcp = EmptyProjectionMCP()
    receipts = []
    service = DeviceQueryService(
        mcp, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.active_rooms({})

    assert result.data["active_rooms"] == [
        {"name": "Office", "reasons": ["motion"]}
    ]
    assert len(mcp.calls) == 3
    assert mcp.calls[-1] == (
        "hub_read_devices", {"tool": "hub_list_devices", "args": {}}
    )
    # Only the fallback complete snapshot is authoritative evidence; the empty
    # fast-path attempt is not presented as a successful state snapshot.
    assert len(receipts) == 1
    assert receipts[0][1]["summary"] == "1 source device records"
