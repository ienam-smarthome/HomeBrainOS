from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_types import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


class FakeDeviceTypeMCP:
    configured = True
    server_info = {"name": "Hubitat MCP", "version": "3.4.1"}

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_list_devices",
                "List selected Hubitat devices",
                {"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        assert name == "hub_list_devices"
        data = {
            "devices": [
                {
                    "id": "1",
                    "label": "Bedroom 1 FP300",
                    "room": "Bedroom 1",
                    "deviceType": "Aqara Presence Sensor",
                    "capabilities": ["Motion Sensor", "Illuminance Measurement"],
                    "currentStates": {"motion": "active", "illuminance": 14},
                },
                {
                    "id": "2",
                    "label": "Hallway LWR01 Motion",
                    "room": "Hallway",
                    "deviceType": "Zigbee Motion Sensor",
                    "capabilities": ["Motion Sensor", "Battery"],
                    "currentStates": {"motion": "inactive", "battery": 88},
                },
                {
                    "id": "3",
                    "label": "Front Door",
                    "room": "Hallway",
                    "deviceType": "Contact Sensor",
                    "capabilities": ["Contact Sensor", "Battery"],
                    "currentStates": {"contact": "open", "battery": 70},
                },
                {
                    "id": "4",
                    "label": "Livingroom TRV",
                    "room": "Livingroom",
                    "deviceType": "Thermostatic Radiator Valve",
                    "capabilities": ["Thermostat", "Battery"],
                    "currentStates": {
                        "thermostatMode": "heat",
                        "heatingSetpoint": 21,
                        "battery": 12,
                    },
                },
                {
                    "id": "5",
                    "label": "Bathroom Meter",
                    "room": "Bathroom",
                    "deviceType": "Temperature Humidity Sensor",
                    "capabilities": [
                        "Temperature Measurement",
                        "Relative Humidity Measurement",
                    ],
                    "currentStates": {"temperature": 23.4, "humidity": 64},
                },
                {
                    "id": "6",
                    "label": "Cudy CAM-Camera-G100",
                    "room": "Hallway",
                    "deviceType": "MQTT Camera",
                    "capabilities": [],
                    "currentStates": {"status": "online"},
                },
                {
                    "id": "7",
                    "label": "Bedroom 2 Light",
                    "room": "Bedroom 2",
                    "deviceType": "Generic Zigbee Light",
                    "capabilities": ["Switch", "Switch Level"],
                    "currentStates": {"switch": "off", "level": 30},
                },
                {
                    "id": "8",
                    "label": "Freezer (MQTT)",
                    "room": "Kitchen",
                    "deviceType": "MQTT Power Meter",
                    "capabilities": ["Switch", "Power Meter", "Energy Meter"],
                    "currentStates": {"switch": "on", "power": 72, "energy": 94.753},
                },
            ]
        }
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def router() -> FastFallbackRouter:
    return FastFallbackRouter(FakeDeviceTypeMCP(), cpu_probe_enabled=False)


def test_device_type_questions_route_to_mcp_fast():
    for query in (
        "show all motion sensors",
        "Which contact sensors do I have?",
        "list thermostats",
        "show cameras",
        "What temperature sensors are available?",
    ):
        assert classify_query(query).route == "mcp-fast"


def test_show_all_motion_sensors_returns_inventory_not_exact_name_error():
    answer = asyncio.run(router().answer("show all motion sensors"))

    assert answer["success"] is True
    assert answer["intent"] == "fallback-device-type-motion"
    assert answer["device_count"] == 2
    assert "Bedroom 1 FP300" in answer["message"]
    assert "Hallway LWR01 Motion" in answer["message"]
    assert "exact device" not in answer["message"].lower()
    assert answer["display"]["title"] == "Motion sensors"


def test_active_motion_question_keeps_active_only_handler():
    answer = asyncio.run(router().answer("Which motion sensors are active?"))

    assert answer["intent"] == "fallback-motion-active"
    assert "Bedroom 1 FP300" in answer["message"]
    assert "Hallway LWR01 Motion" not in answer["message"]


def test_other_device_classes_use_live_states_and_metadata():
    contact = asyncio.run(router().answer("Which contact sensors do I have?"))
    assert contact["intent"] == "fallback-device-type-contact"
    assert contact["device_count"] == 1
    assert "Front Door: Open" in contact["message"]

    thermostats = asyncio.run(router().answer("List thermostats"))
    assert thermostats["intent"] == "fallback-device-type-thermostat"
    assert thermostats["device_count"] == 1
    assert "Livingroom TRV" in thermostats["message"]

    cameras = asyncio.run(router().answer("Show cameras"))
    assert cameras["intent"] == "fallback-device-type-camera"
    assert cameras["device_count"] == 1
    assert "Cudy CAM-Camera-G100" in cameras["message"]

    temperature = asyncio.run(router().answer("Show all temperature sensors"))
    assert temperature["intent"] == "fallback-device-type-temperature"
    assert temperature["device_count"] == 1
    assert "Bathroom Meter: 23.4°C" in temperature["message"]


def test_lights_power_and_energy_are_device_type_inventories():
    lights = asyncio.run(router().answer("Show all lights"))
    assert lights["intent"] == "fallback-device-type-light"
    assert lights["device_count"] == 1
    assert "Bedroom 2 Light: Off" in lights["message"]

    power = asyncio.run(router().answer("List power meters"))
    assert power["intent"] == "fallback-device-type-power"
    assert power["device_count"] == 1
    assert "Freezer (MQTT): 72 W" in power["message"]

    energy = asyncio.run(router().answer("Which energy meters do I have?"))
    assert energy["intent"] == "fallback-device-type-energy"
    assert energy["device_count"] == 1
    assert "94.753 kWh" in energy["message"]


def test_exact_device_status_query_still_resolves_one_device():
    answer = asyncio.run(router().answer("Show Hallway LWR01 Motion"))

    assert answer["intent"] == "fallback-device-status"
    assert answer["device_label"] == "Hallway LWR01 Motion"
