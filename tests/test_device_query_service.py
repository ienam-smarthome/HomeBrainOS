import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from device_target_resolver import resolve_device_candidate  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


class QueryMCP:
    def __init__(self, devices):
        self.devices = devices

    async def call_tool(self, name, arguments):
        return MCPToolResult(
            name, arguments, {}, "ok", {"devices": self.devices}
        )

    async def get_cached_devices(self):
        return self.devices


def device(label, room, capabilities, **attributes):
    return {
        "id": label,
        "label": label,
        "room": room,
        "capabilities": capabilities,
        "attributes": attributes,
    }


@pytest.mark.asyncio
async def test_query_devices_finds_hottest_room():
    service = DeviceQueryService(
        QueryMCP([
            device("Bedroom Meter", "Bedroom", ["TemperatureMeasurement"], temperature=27.5),
            device("Hallway Meter", "Hallway", ["TemperatureMeasurement"], temperature=30),
            device("Fridge Meter", "Appliances", ["TemperatureMeasurement"], temperature=-1),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.query_devices({
        "attribute": "temperature",
        "operation": "maximum",
        "group_by": "room",
    })

    assert result.data["winner"]["room"] == "Hallway"
    assert result.data["winner"]["value"] == 30
    assert result.data["winner"]["unit"] == "°C"


@pytest.mark.asyncio
async def test_query_devices_finds_highest_humidity():
    service = DeviceQueryService(
        QueryMCP([
            device("Living Meter", "Living Room", ["RelativeHumidityMeasurement"], humidity=48),
            device("Bathroom Meter", "Bathroom", ["RelativeHumidityMeasurement"], humidity="71%"),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.query_devices({
        "attribute": "humidity",
        "operation": "maximum",
        "group_by": "room",
    })

    assert result.data["winner"]["room"] == "Bathroom"
    assert result.data["winner"]["value"] == 71


@pytest.mark.asyncio
async def test_query_devices_ranks_only_sockets_by_power():
    service = DeviceQueryService(
        QueryMCP([
            device("TV socket", "Sockets", ["Switch", "PowerMeter"], power=82),
            device("Desk plug", "Office", ["Outlet", "PowerMeter"], power=40),
            device("Whole Home Meter", "Energy", ["PowerMeter"], power=900),
        ]),
        lambda *args, **kwargs: None,
    )

    result = await service.query_devices({
        "attribute": "power",
        "operation": "maximum",
        "device_kind": "socket",
    })

    assert result.data["winner"]["label"] == "TV socket"
    assert result.data["count"] == 2


def test_target_resolution_accepts_spaced_room_name_and_omitted_kind():
    result = resolve_device_candidate(
        "living room two",
        [
            {"id": "1", "label": "Livingroom Light 1"},
            {"id": "2", "label": "Livingroom Light 2"},
            {"id": "3", "label": "Bedroom 2 Light"},
        ],
    )

    assert result.target["id"] == "2"
    assert result.reason == "exact semantic name with device-kind token omitted"
