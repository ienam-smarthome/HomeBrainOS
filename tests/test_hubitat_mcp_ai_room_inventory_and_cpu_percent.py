from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_room_inventory import FastFallbackRouter  # noqa: E402
from hub_cpu_probe import parse_cpu_info  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


class FakeRoomMCP:
    async def list_tools(self):
        return [
            MCPTool("hub_list_rooms", "rooms", {"type": "object", "properties": {}}),
            MCPTool("hub_list_devices", "devices", {"type": "object", "properties": {}}),
        ]

    async def supported_arguments(self, _name, desired):
        return desired

    async def call_tool(self, name, arguments):
        if name == "hub_list_rooms":
            data = {
                "rooms": [
                    {"id": "1", "name": "Apps"},
                    {"id": "2", "name": "Bedroom 1"},
                    {"id": "3", "name": "Hallway"},
                ]
            }
        elif name == "hub_list_devices":
            data = {
                "devices": [
                    {
                        "id": "101",
                        "label": "HomeBrain Report",
                        "room": "Apps",
                        "deviceType": "Virtual Device",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "102",
                        "label": "MCP Status Display",
                        "room": {"name": "Apps"},
                        "deviceType": "Virtual Display",
                        "currentStates": {"status": "ready"},
                    },
                    {
                        "id": "201",
                        "label": "Bedroom 1 Light",
                        "room": "Bedroom 1",
                        "deviceType": "Generic Zigbee Light",
                        "currentStates": {"switch": "off"},
                    },
                    {
                        "id": "301",
                        "label": "Hallway FP300",
                        "room": "Hallway",
                        "deviceType": "Motion Sensor",
                        "currentStates": {"motion": "inactive"},
                    },
                    {
                        "id": "302",
                        "label": "Hallway Light 1",
                        "room": "Hallway",
                        "deviceType": "Generic Zigbee Light",
                        "currentStates": {"switch": "on"},
                    },
                    {
                        "id": "303",
                        "label": "Hallway Meter",
                        "room": "Hallway",
                        "deviceType": "Temperature Humidity Sensor",
                        "currentStates": {
                            "temperature": 29.2,
                            "humidity": 36,
                        },
                    },
                ]
            }
        else:
            raise AssertionError(f"Unexpected tool: {name}")
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_list_apps_routes_directly_to_mcp_fast():
    decision = classify_query("List Apps")
    assert decision.route == "mcp-fast"


def test_list_apps_returns_only_devices_in_exact_apps_room():
    answer = asyncio.run(FastFallbackRouter(FakeRoomMCP()).answer("List Apps"))

    assert answer["success"] is True
    assert answer["intent"] == "fallback-room-devices"
    assert answer["room"] == "Apps"
    assert "HomeBrain Report" in answer["message"]
    assert "MCP Status Display" in answer["message"]
    assert "Bedroom 1 Light" not in answer["message"]
    assert answer["display"]["kind"] == "room-device-inventory"
    assert answer["display"]["metrics"][0]["value"] == "2"


def test_explicit_room_wording_also_matches():
    answer = asyncio.run(
        FastFallbackRouter(FakeRoomMCP()).answer("Show devices under Apps room")
    )
    assert answer["intent"] == "fallback-room-devices"
    assert answer["room"] == "Apps"


def test_real_room_name_with_room_suffix_is_preferred_before_fallback():
    class LivingRoomMCP(FakeRoomMCP):
        async def call_tool(self, name, arguments):
            result = await super().call_tool(name, arguments)
            if name == "hub_list_rooms":
                result.data["rooms"].append({"id": "4", "name": "Living room"})
            elif name == "hub_list_devices":
                result.data["devices"].append(
                    {
                        "id": "401",
                        "label": "Living Room Lamp",
                        "room": "Living room",
                        "deviceType": "Dimmer",
                        "currentStates": {"switch": "off"},
                    }
                )
            return result

    answer = asyncio.run(
        FastFallbackRouter(LivingRoomMCP()).answer(
            "Show devices in the Living room"
        )
    )

    assert answer["intent"] == "fallback-room-devices"
    assert answer["room"] == "Living room"
    assert "Living Room Lamp" in answer["message"]


def test_room_first_hallway_inventory_returns_all_room_devices():
    for query in ("Find hallway devices", "Show hallway devices"):
        answer = asyncio.run(FastFallbackRouter(FakeRoomMCP()).answer(query))

        assert answer["success"] is True
        assert answer["intent"] == "fallback-room-devices"
        assert answer["room"] == "Hallway"
        assert "Hallway FP300" in answer["message"]
        assert "Hallway Light 1" in answer["message"]
        assert "Hallway Meter: 29.2°C, 36% humidity" in answer["message"]
        assert "Bedroom 1 Light" not in answer["message"]
        assert answer["display"]["metrics"][0]["value"] == "3"

        hallway_meter = next(
            item
            for item in answer["display"]["items"]
            if item["title"] == "Hallway Meter"
        )
        assert hallway_meter["value"] == "29.2°C, 36% humidity"


def test_hub_info_load_and_percent_format_returns_percentage():
    cpu = parse_cpu_info("CPU Load/Load% 0.6 / 15.0 %")
    assert cpu["available"] is True
    assert cpu["mode"] == "percent"
    assert cpu["load_average"] == 0.6
    assert cpu["percent"] == 15.0
    assert cpu["value"] == "15%"
    assert cpu["derived_percent"] is False


def test_load_average_and_processors_derives_percentage():
    cpu = parse_cpu_info("Processors: 4\nLoad average: 0.6")
    assert cpu["available"] is True
    assert cpu["mode"] == "percent"
    assert cpu["percent"] == 15.0
    assert cpu["value"] == "15.0%"
    assert cpu["derived_percent"] is True


def test_empty_lux_summary_is_completed_by_bounded_device_detail():
    class LuxDetailMCP(FakeRoomMCP):
        def __init__(self):
            self.detail_ids = []

        async def list_tools(self):
            tools = await super().list_tools()
            tools.append(
                MCPTool(
                    "hub_get_device",
                    "device detail",
                    {"type": "object", "properties": {}},
                )
            )
            return tools

        async def call_tool(self, name, arguments):
            if name == "hub_get_device":
                device_id = str(arguments.get("deviceId") or "")
                self.detail_ids.append(device_id)
                return MCPToolResult(
                    name=name,
                    arguments=arguments,
                    raw={},
                    text="",
                    data={
                        "device": {
                            "id": device_id,
                            "label": "Hallway FP300 Lux",
                            "room": "Hallway",
                            "currentStates": {
                                "illuminance": 3,
                                "networkStatus": "online",
                            },
                        }
                    },
                    is_error=False,
                )

            result = await super().call_tool(name, arguments)

            if name == "hub_list_devices":
                result.data["devices"].append(
                    {
                        "id": "303",
                        "label": "Hallway FP300 Lux",
                        "name": "Illuminance Sensor",
                        "room": "Hallway",
                        "deviceType": "Illuminance Sensor",
                        "currentStates": {},
                    }
                )

            return result

    mcp = LuxDetailMCP()
    answer = asyncio.run(
        FastFallbackRouter(mcp).answer("Show hallway devices")
    )

    assert answer["success"] is True
    assert "Hallway FP300 Lux: 3 lx" in answer["message"]

    lux_item = next(
        item
        for item in answer["display"]["items"]
        if item["title"] == "Hallway FP300 Lux"
    )
    assert lux_item["value"] == "3 lx"
    assert lux_item["icon"] == "🔆"
    assert mcp.detail_ids == ["303"]

    technical = json.loads(answer["technical"])
    assert technical["detail_probes"] == 1
    assert technical["detail_reads"] == [
        {
            "device_id": "303",
            "label": "Hallway FP300 Lux",
            "success": True,
        }
    ]


def test_empty_fan_summary_is_completed_by_device_detail():
    class FanDetailMCP(FakeRoomMCP):
        def __init__(self):
            self.detail_ids = []

        async def list_tools(self):
            tools = await super().list_tools()
            tools.append(
                MCPTool(
                    "hub_get_device",
                    "device detail",
                    {"type": "object", "properties": {}},
                )
            )
            return tools

        async def call_tool(self, name, arguments):
            if name == "hub_get_device":
                device_id = str(arguments.get("deviceId") or "")
                self.detail_ids.append(device_id)

                return MCPToolResult(
                    name=name,
                    arguments=arguments,
                    raw={},
                    text="",
                    data={
                        "device": {
                            "id": device_id,
                            "label": "Standing Fan",
                            "room": "Living Room",
                            "currentStates": {
                                "speed": "off",
                                "networkStatus": "online",
                            },
                        }
                    },
                    is_error=False,
                )

            result = await super().call_tool(name, arguments)

            if name == "hub_list_rooms":
                result.data["rooms"].append(
                    {"id": "34", "name": "Living Room"}
                )

            if name == "hub_list_devices":
                result.data["devices"].append(
                    {
                        "id": "7402",
                        "label": "Standing Fan",
                        "name": "Fan Control",
                        "room": "Living Room",
                        "deviceType": "Standing Fan",
                        "capabilities": [
                            "Actuator",
                            "FanControl",
                            "Switch",
                            "SwitchLevel",
                        ],
                        "currentStates": {},
                    }
                )

            return result

    mcp = FanDetailMCP()
    answer = asyncio.run(
        FastFallbackRouter(mcp).answer("Show livingroom devices")
    )

    assert answer["success"] is True
    assert "Standing Fan: Off" in answer["message"]

    fan_item = next(
        item
        for item in answer["display"]["items"]
        if item["title"] == "Standing Fan"
    )

    assert fan_item["value"] == "Off"
    assert fan_item["icon"] == "🌀"
    assert answer["display"]["title"] == "Living Room"
    assert mcp.detail_ids == ["7402"]

    technical = json.loads(answer["technical"])
    assert technical["detail_probes"] == 1
    assert technical["detail_reads"] == [
        {
            "device_id": "7402",
            "label": "Standing Fan",
            "success": True,
        }
    ]


def test_multi_word_room_before_devices_preserves_full_room_name():
    assert (
        FastFallbackRouter._room_candidate("Show living room devices")
        == "living room"
    )
    assert (
        FastFallbackRouter._room_candidate("List dining room devices")
        == "dining room"
    )


def test_room_inventory_message_does_not_repeat_room():
    class LivingRoomMCP(FakeRoomMCP):
        async def call_tool(self, name, arguments):
            result = await super().call_tool(name, arguments)

            if name == "hub_list_rooms":
                result.data["rooms"].append(
                    {"id": "34", "name": "Living Room"}
                )

            if name == "hub_list_devices":
                result.data["devices"].append(
                    {
                        "id": "7402",
                        "label": "Standing Fan",
                        "name": "Fan Control",
                        "room": "Living Room",
                        "currentStates": {"speed": "off"},
                    }
                )

            return result

    answer = asyncio.run(
        FastFallbackRouter(LivingRoomMCP()).answer(
            "Show living room devices"
        )
    )

    assert answer["success"] is True
    assert answer["room"] == "Living Room"
    assert answer["display"]["title"] == "Living Room"
    assert "assigned to Living Room:" in answer["message"]
    assert "Living Room room" not in answer["message"]


def test_room_state_enrichment_formats_common_device_metrics():
    from fast_fallback_room_inventory import _room_device_states

    assert _room_device_states(
        {
            "thermostatMode": "heat",
            "heatingSetpoint": 22,
            "temperature": 20.5,
        },
        "",
    ) == ["Heat", "22°C setpoint", "20.5°C"]

    assert _room_device_states(
        {
            "switch": "on",
            "power": 84,
            "energy": 12.4,
        },
        "",
    ) == ["84 W", "12.4 kWh", "On"]

    assert _room_device_states({"lock": "locked"}, "") == ["Locked"]
    assert _room_device_states({"water": "dry"}, "") == ["Dry"]
    assert _room_device_states({"smoke": "clear"}, "") == ["Clear"]


def test_empty_common_sensor_types_are_eligible_for_bounded_detail():
    from fast_fallback_room_inventory import _needs_empty_device_detail

    examples = [
        {"label": "Livingroom TRV", "name": "Thermostat"},
        {"label": "TV socket power", "name": "Power Meter"},
        {"label": "Front Door Lock", "name": "Lock"},
        {"label": "Bathroom Leak", "name": "Water Sensor"},
        {"label": "Kitchen Smoke", "name": "Smoke Detector"},
    ]

    for item in examples:
        assert _needs_empty_device_detail(item, {}) is True

    assert _needs_empty_device_detail(
        {"label": "Unrelated Device", "name": "Generic Device"},
        {},
    ) is False


def test_room_inventory_technical_response_is_compact():
    answer = asyncio.run(
        FastFallbackRouter(FakeRoomMCP()).answer("Show hallway devices")
    )

    assert answer["success"] is True

    technical = json.loads(answer["technical"])
    assert "devices" not in technical
    assert isinstance(technical["inventory_count"], int)
    assert isinstance(technical["room_device_count"], int)
    assert technical["room_device_count"] == len(
        answer["display"]["items"]
    )
    assert technical["detail_probes"] <= 4
