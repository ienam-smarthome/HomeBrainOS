from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def _device(
    device_id: str,
    label: str,
    room: str,
    capabilities: list[str],
    *,
    attributes: dict | None = None,
) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": list(capabilities),
        "attributes": dict(attributes or {}),
        "commands": ["on", "off"] if "Switch" in capabilities else [],
    }


HALLWAY_1 = _device(
    "8101",
    "Hallway Light 1",
    "Hallway",
    ["Switch", "Light"],
    attributes={"switch": "off"},
)
HALLWAY_2 = _device(
    "8102",
    "Hallway Light 2",
    "Hallway",
    ["Switch", "Light"],
    attributes={"switch": "on"},
)
KITCHEN = _device(
    "8201",
    "Kitchen Light",
    "Kitchen",
    ["Switch", "Light"],
    attributes={"switch": "off"},
)
HALLWAY_METER = _device(
    "8301",
    "Hallway Meter",
    "Hallway",
    ["TemperatureMeasurement"],
    attributes={"temperature": 22.0},
)


class _RoomKindMCP:
    def __init__(self, identities: list[dict]) -> None:
        self.identities = [dict(item) for item in identities]
        self.calls: list[tuple[str, dict]] = []

    def peek_device_identities(self):
        return [dict(item) for item in self.identities]

    async def get_device_identities(self):
        return [dict(item) for item in self.identities]

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        operation = arguments.get("tool")
        args = arguments.get("args") or {}

        if operation == "hub_list_devices":
            # Reproduce the live failure: the legacy label filter does not
            # understand a room-kind group phrase.
            label_filter = str(args.get("labelFilter") or "")
            if label_filter.casefold() == "hallway lights":
                return MCPToolResult(name, arguments, {}, "ok", {"devices": []})
            if label_filter.casefold() == "toilet lights":
                return MCPToolResult(name, arguments, {}, "ok", {"devices": []})
            raise AssertionError(
                ("unexpected broader label lookup", label_filter, arguments)
            )

        if operation == "hub_list_device_events":
            device_id = str(args.get("deviceId") or "")
            assert device_id == "8401"
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-09-24T15:00:00.000+0100",
                            "isStateChange": True,
                        }
                    ],
                    "count": 1,
                },
            )

        raise AssertionError(("unexpected operation", operation, arguments))


@pytest.mark.asyncio
async def test_room_plural_lights_surface_exact_hallway_members() -> None:
    mcp = _RoomKindMCP([HALLWAY_1, HALLWAY_2, KITCHEN, HALLWAY_METER])
    service = DeviceQueryService(mcp, lambda *args, **kwargs: None)

    result = await service.resolve_device({"name": "hallway lights"})

    assert result.is_error is False
    assert result.data["matched"] is False
    assert result.data["alternatives"] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    assert "2 light devices in Hubitat room 'Hallway'" in result.data["reason"]
    assert result.data["attempts"] == [
        {"source": "label_filter", "count": 0},
        {"source": "authoritative_room_kind", "count": 2},
    ]
    assert len(mcp.calls) == 1
    assert mcp.calls[0][1]["args"]["labelFilter"] == "hallway lights"


@pytest.mark.asyncio
async def test_history_room_plural_never_falls_back_to_generic_lights_lookup() -> None:
    mcp = _RoomKindMCP([HALLWAY_1, HALLWAY_2, KITCHEN, HALLWAY_METER])
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "hallway lights"})

    assert result.is_error is True
    assert result.data["success"] is False
    assert result.data["error"] == "device is ambiguous"
    assert result.data["alternatives"] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    assert result.data["fallbackLookup"] is None
    assert "2 light devices in Hubitat room 'Hallway'" in str(
        result.data["resolutionReason"]
    )

    label_filters = [
        str(arguments.get("args", {}).get("labelFilter") or "")
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
    ]
    assert label_filters == ["hallway lights"]
    assert not any(
        arguments.get("tool") == "hub_list_device_events"
        for _name, arguments in mcp.calls
    )


@pytest.mark.asyncio
async def test_unique_room_plural_can_resolve_single_light() -> None:
    toilet = _device(
        "8401",
        "Toilet Light",
        "Toilet",
        ["Switch", "Light"],
        attributes={"switch": "on"},
    )
    mcp = _RoomKindMCP([toilet, HALLWAY_1, HALLWAY_2])
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({
        "name": "toilet lights",
        "attribute": "switch",
        "hours_back": 24,
    })

    assert result.is_error is False
    assert result.data["deviceId"] == "8401"
    assert result.data["label"] == "Toilet Light"
    assert result.data["count"] == 1

    label_filters = [
        str(arguments.get("args", {}).get("labelFilter") or "")
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
    ]
    assert label_filters == ["toilet lights"]
    assert any(
        arguments.get("tool") == "hub_list_device_events"
        and arguments.get("args", {}).get("deviceId") == "8401"
        for _name, arguments in mcp.calls
    )


def test_room_kind_reference_requires_exact_room_and_kind() -> None:
    devices = [HALLWAY_1, HALLWAY_2, KITCHEN, HALLWAY_METER]

    hallway = DeviceQueryService._room_kind_reference("Hallway lights", devices)
    assert hallway is not None
    kind, room, matches = hallway
    assert kind == "light"
    assert room == "Hallway"
    assert [item["label"] for item in matches] == [
        "Hallway Light 1",
        "Hallway Light 2",
    ]

    assert DeviceQueryService._room_kind_reference(
        "Hall light", devices
    ) is None
    assert DeviceQueryService._room_kind_reference(
        "Hallway meters", devices
    ) is None
