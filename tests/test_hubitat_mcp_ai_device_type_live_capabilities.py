from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_types_live import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


SUMMARY_KEYS = {
    "switch",
    "level",
    "motion",
    "contact",
    "temperature",
    "humidity",
    "battery",
}


DEVICES = [
    {
        "id": "1",
        "label": "Bedroom 1 FP300",
        "room": "Bedroom 1",
        "capabilities": ["Sensor", "Motion Sensor", "Presence Sensor"],
        "states": {"motion": "active", "presence": "present", "battery": 94},
    },
    {
        "id": "2",
        "label": "Hallway LWR01 Motion",
        "room": "Hallway",
        "capabilities": ["Sensor", "Motion Sensor", "Battery"],
        "states": {"motion": "inactive", "battery": 88},
    },
    {
        "id": "3",
        "label": "Front Door",
        "room": "Hallway",
        "capabilities": ["Sensor", "Contact Sensor", "Battery"],
        "states": {"contact": "open", "battery": 70},
    },
    {
        "id": "4",
        "label": "Bathroom Meter",
        "room": "Bathroom",
        "capabilities": [
            "Sensor",
            "Temperature Measurement",
            "Relative Humidity Measurement",
        ],
        "states": {"temperature": 23.4, "humidity": 64},
    },
    {
        "id": "5",
        "label": "Livingroom TRV",
        "room": "Livingroom",
        "capabilities": ["Sensor", "Thermostat", "Battery"],
        "states": {
            "thermostatMode": "heat",
            "thermostatOperatingState": "heating",
            "heatingSetpoint": 21,
            "battery": 12,
        },
    },
    {
        "id": "6",
        "label": "Bedroom 2 Light",
        "room": "Bedroom 2",
        "capabilities": ["Actuator", "Switch", "Switch Level"],
        "states": {"switch": "off", "level": 30},
    },
    {
        "id": "7",
        "label": "Cudy CAM-Camera-G100",
        "room": "Hallway",
        "capabilities": ["Actuator", "Switch"],
        "states": {"switch": "on"},
    },
]


class RealisticKingpantherMCP:
    configured = True
    server_info = {"name": "Hubitat MCP", "version": "3.4.1"}

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                "hub_list_devices",
                "List selected Hubitat devices",
                {"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        assert name == "hub_list_devices"
        self.calls.append(dict(arguments))

        valid_fields = {
            "id",
            "name",
            "label",
            "room",
            "disabled",
            "deviceNetworkId",
            "lastActivity",
            "parentDeviceId",
            "mcpManaged",
            "currentStates",
            "capabilities",
            "attributes",
            "commands",
        }
        requested_fields = set(arguments.get("fields") or [])
        unknown = requested_fields - valid_fields
        if unknown:
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text=f"Invalid params: Unknown fields: {sorted(unknown)}",
                data=None,
                is_error=True,
            )

        capability = str(arguments.get("capabilityFilter") or "").lower()
        selected = [
            item
            for item in DEVICES
            if not capability
            or any(str(cap).lower() == capability for cap in item["capabilities"])
        ]
        detailed = bool(arguments.get("detailed")) or arguments.get("format") == "detailed" or bool(
            requested_fields.intersection({"attributes", "capabilities", "commands"})
        )

        output = []
        for item in selected:
            row: dict[str, Any] = {
                "id": item["id"],
                "name": item["label"],
                "label": item["label"],
                "room": item["room"],
            }
            if detailed:
                if "attributes" in requested_fields:
                    row["attributes"] = [
                        {"name": key, "value": value}
                        for key, value in item["states"].items()
                    ]
                if "capabilities" in requested_fields:
                    row["capabilities"] = list(item["capabilities"])
            elif "currentStates" in requested_fields:
                row["currentStates"] = {
                    key: value
                    for key, value in item["states"].items()
                    if key in SUMMARY_KEYS
                }
            output.append(row)

        data = {
            "devices": output,
            "count": len(output),
            "total": len(output),
        }
        if capability:
            data["unfilteredTotal"] = len(DEVICES)
            data["capabilityFilter"] = arguments["capabilityFilter"]
            data["capabilityFilterMatchedKnownCapability"] = any(
                any(str(cap).lower() == capability for cap in item["capabilities"])
                for item in DEVICES
            )
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def make_router() -> tuple[FastFallbackRouter, RealisticKingpantherMCP]:
    client = RealisticKingpantherMCP()
    return FastFallbackRouter(client, cpu_probe_enabled=False), client


def test_common_sensor_inventories_use_server_capability_filters_and_return_devices():
    router, client = make_router()

    contact = asyncio.run(router.answer("Which contact sensors do I have?"))
    temperature = asyncio.run(router.answer("List temperature sensors"))
    motion = asyncio.run(router.answer("Show all motion sensors"))

    assert contact["device_count"] == 1
    assert "Front Door: Open" in contact["message"]
    assert temperature["device_count"] == 1
    assert "Bathroom Meter: 23.4°C" in temperature["message"]
    assert motion["device_count"] == 2
    assert "Bedroom 1 FP300: Active" in motion["message"]
    assert "Hallway LWR01 Motion: Inactive" in motion["message"]

    filters = [call.get("capabilityFilter") for call in client.calls]
    assert "Contact Sensor" in filters
    assert "Temperature Measurement" in filters
    assert "Motion Sensor" in filters


def test_light_inventory_does_not_treat_every_switch_as_a_light():
    router, _client = make_router()

    answer = asyncio.run(router.answer("Show lights"))

    assert answer["device_count"] == 1
    assert "Bedroom 2 Light: Off" in answer["message"]
    assert "Cudy CAM-Camera-G100" not in answer["message"]


def test_common_sensor_calls_do_not_request_huge_detailed_all_device_payloads():
    router, client = make_router()
    asyncio.run(router.answer("List temperature sensors"))

    filtered = next(
        call for call in client.calls if call.get("capabilityFilter") == "Temperature Measurement"
    )
    assert filtered["format"] == "summary"
    assert filtered["detailed"] is False
    assert "currentStates" in filtered["fields"]
    assert "attributes" not in filtered["fields"]
    assert "capabilities" not in filtered["fields"]
    assert "commands" not in filtered["fields"]


def test_non_summary_type_uses_small_capability_filtered_attribute_payload():
    router, client = make_router()
    answer = asyncio.run(router.answer("List thermostats"))

    assert answer["device_count"] == 1
    assert "Livingroom TRV: Heating" in answer["message"]
    thermostat_call = next(
        call for call in client.calls if call.get("capabilityFilter") == "Thermostat"
    )
    assert thermostat_call["format"] == "detailed"
    assert thermostat_call["detailed"] is True
    assert "attributes" in thermostat_call["fields"]
    assert "capabilities" not in thermostat_call["fields"]


def test_name_based_camera_inventory_falls_back_to_lightweight_summary():
    router, client = make_router()
    answer = asyncio.run(router.answer("Show cameras"))

    assert answer["device_count"] == 1
    assert "Cudy CAM-Camera-G100: On" in answer["message"]
    assert any(not call.get("capabilityFilter") for call in client.calls)


def test_standard_capability_zero_is_reported_only_after_live_fallback_check():
    router, client = make_router()
    answer = asyncio.run(router.answer("Show smoke detectors"))

    assert answer["device_count"] == 0
    assert "No smoke detectors were found" in answer["message"]
    assert any(call.get("capabilityFilter") == "Smoke Detector" for call in client.calls)
    assert any(not call.get("capabilityFilter") for call in client.calls)
