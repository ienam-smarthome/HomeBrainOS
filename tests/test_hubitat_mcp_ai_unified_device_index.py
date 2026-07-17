from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_catalogue_safe import (  # noqa: E402
    SafeCapabilityCatalogueDeviceIndex,
)
from fast_fallback_device_index import FastFallbackRouter  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


SUMMARY_DEVICES = [
    {
        "id": "1",
        "name": "Front Door",
        "label": "Front Door",
        "room": "Hallway",
        "currentStates": {"contact": "open", "battery": 70},
    },
    {
        "id": "2",
        "name": "Bathroom Meter",
        "label": "Bathroom Meter",
        "room": "Bathroom",
        "currentStates": {"temperature": 23.4, "humidity": 64, "battery": 91},
    },
    {
        "id": "3",
        "name": "Hallway Motion",
        "label": "Hallway Motion",
        "room": "Hallway",
        "currentStates": {"motion": "inactive", "battery": 88},
    },
    {
        "id": "4",
        "name": "Bedroom 1 Light",
        "label": "Bedroom 1 Light",
        "room": "Bedroom 1",
        "currentStates": {"switch": "on", "level": 30},
    },
    {
        "id": "5",
        "name": "Freezer (MQTT)",
        "label": "Freezer (MQTT)",
        "room": "Kitchen",
        "currentStates": {"switch": "on", "battery": 17},
    },
    {
        "id": "6",
        "name": "Bedroom 2 Light",
        "label": "Bedroom 2 Light",
        "room": "",
        "currentStates": {"switch": "off"},
    },
]


METADATA_DEVICES = [
    {
        "id": "1",
        "name": "Front Door",
        "label": "Front Door",
        "room": "Hallway",
        # Simulates a custom driver name that an exact "Contact Sensor" filter misses.
        "capabilities": ["Sensor", "ContactSensor", "Battery"],
    },
    {
        "id": "2",
        "name": "Bathroom Meter",
        "label": "Bathroom Meter",
        "room": "Bathroom",
        "capabilities": [
            "Sensor",
            "TemperatureMeasurement",
            "RelativeHumidityMeasurement",
            "Battery",
        ],
    },
    {
        "id": "3",
        "name": "Hallway Motion",
        "label": "Hallway Motion",
        "room": "Hallway",
        "capabilities": ["Sensor", "MotionSensor", "Battery"],
    },
    {
        "id": "4",
        "name": "Bedroom 1 Light",
        "label": "Bedroom 1 Light",
        "room": "Bedroom 1",
        "capabilities": ["Actuator", "Switch", "SwitchLevel"],
    },
    {
        "id": "5",
        "name": "Freezer (MQTT)",
        "label": "Freezer (MQTT)",
        "room": "Kitchen",
        "capabilities": ["Actuator", "Switch", "Battery"],
    },
    {
        "id": "6",
        "name": "Bedroom 2 Light",
        "label": "Bedroom 2 Light",
        "room": "",
        "capabilities": ["Actuator", "Switch"],
    },
]


class ExactFilterMissMCP:
    configured = True
    server_info = {"name": "Hubitat MCP", "version": "3.4.1"}

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.invalidators = []

    def register_invalidator(self, callback):
        self.invalidators.append(callback)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        assert name == "hub_list_devices"
        args = dict(arguments or {})
        self.calls.append(args)
        fields = set(args.get("fields") or [])

        if args.get("capabilityFilter"):
            # This reproduces the real screenshot failure: the exact server-side
            # capability spelling returns zero.
            data = {
                "devices": [],
                "count": 0,
                "total": 0,
                "unfilteredTotal": len(SUMMARY_DEVICES),
                "capabilityFilter": args["capabilityFilter"],
                "capabilityFilterMatchedKnownCapability": False,
            }
        elif "capabilities" in fields:
            data = {
                "devices": [dict(item) for item in METADATA_DEVICES],
                "count": len(METADATA_DEVICES),
                "total": len(METADATA_DEVICES),
            }
        else:
            data = {
                "devices": [dict(item) for item in SUMMARY_DEVICES],
                "count": len(SUMMARY_DEVICES),
                "total": len(SUMMARY_DEVICES),
            }
        return MCPToolResult(
            name=name,
            arguments=args,
            raw={},
            text="",
            data=data,
            is_error=False,
        )

    async def trigger_invalidation(self, category: str = "devices") -> None:
        for callback in tuple(self.invalidators):
            result = callback(category)
            if asyncio.iscoroutine(result):
                await result


def make_index():
    client = ExactFilterMissMCP()
    index = SafeCapabilityCatalogueDeviceIndex(
        client,
        ttl_seconds=30,
        capability_ttl_seconds=60,
        metadata_ttl_seconds=120,
    )
    return client, index


def test_contact_sensor_question_uses_capability_catalogue_when_exact_filter_would_miss():
    client, index = make_index()
    router = FastFallbackRouter(
        client,
        device_index=index,
        cpu_probe_enabled=False,
    )

    answer = asyncio.run(router.answer("Which contact sensors do I have?"))

    assert answer["success"] is True
    assert answer["device_count"] == 1
    assert "Front Door: Open" in answer["message"]
    assert answer["display"]["title"] == "Contact sensors"
    assert not any(call.get("capabilityFilter") == "Contact Sensor" for call in client.calls)


def test_temperature_motion_and_humidity_share_one_summary_and_metadata_snapshot():
    client, index = make_index()
    router = FastFallbackRouter(
        client,
        device_index=index,
        cpu_probe_enabled=False,
    )

    temperature = asyncio.run(router.answer("List temperature sensors"))
    motion = asyncio.run(router.answer("Show all motion sensors"))
    humidity = asyncio.run(router.answer("List humidity sensors"))

    assert temperature["device_count"] == 1
    assert "Bathroom Meter: 23.4°C" in temperature["message"]
    assert motion["device_count"] == 1
    assert "Hallway Motion: Inactive" in motion["message"]
    assert humidity["device_count"] == 1
    assert "Bathroom Meter: 64%" in humidity["message"]

    summary_calls = [
        call for call in client.calls
        if not call.get("capabilityFilter") and "capabilities" not in set(call.get("fields") or [])
    ]
    metadata_calls = [
        call for call in client.calls if "capabilities" in set(call.get("fields") or [])
    ]
    assert len(summary_calls) == 1
    assert len(metadata_calls) == 1


def test_dashboard_aliases_and_diagnostics_use_same_index():
    client, index = make_index()

    dashboard = asyncio.run(index.dashboard_metrics())
    match, alternatives = asyncio.run(index.exact_device("bedroom one light"))
    diagnostics = asyncio.run(index.diagnostics())

    assert dashboard["lights_on"] == 1
    assert dashboard["switches_on"] == 1
    assert dashboard["motion_active"] == 0
    assert dashboard["low_batteries"] == 1
    assert match is not None
    assert match["label"] == "Bedroom 1 Light"
    assert alternatives == []
    assert diagnostics["selected_count"] == 6
    assert diagnostics["groups"]["contact"] == 1
    assert diagnostics["groups"]["temperature"] == 1
    assert diagnostics["groups"]["motion"] == 1
    assert diagnostics["without_room"] == ["Bedroom 2 Light"]


def test_generic_sensor_capability_does_not_turn_every_sensor_into_contact_motion_and_temperature():
    _, index = make_index()
    generic_only = {
        "id": "99",
        "label": "Generic Sensor",
        "capabilities": ["Sensor"],
        "currentStates": {},
    }

    groups = index._groups(generic_only)

    assert "sensor" in groups
    assert "contact" not in groups
    assert "motion" not in groups
    assert "temperature" not in groups


def test_device_invalidation_clears_summary_and_capability_metadata():
    client, index = make_index()

    asyncio.run(index.enriched_devices())
    assert index.stats()["summary_loaded"] is True
    assert index.stats()["metadata_loaded"] is True

    asyncio.run(client.trigger_invalidation("devices"))
    stats = index.stats()
    assert stats["summary_loaded"] is False
    assert stats["metadata_loaded"] is False

    asyncio.run(index.enriched_devices())
    summary_calls = [
        call for call in client.calls
        if not call.get("capabilityFilter") and "capabilities" not in set(call.get("fields") or [])
    ]
    metadata_calls = [
        call for call in client.calls if "capabilities" in set(call.get("fields") or [])
    ]
    assert len(summary_calls) == 2
    assert len(metadata_calls) == 2
