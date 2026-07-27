from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import webui  # noqa: E402
from dashboard_api import DashboardSnapshot  # noqa: E402
from dashboard_health_tile import install_dashboard_health_tile  # noqa: E402
from device_intelligence_catalogue import (  # noqa: E402
    CapabilityCatalogueDeviceIndex,
)


class RoomMetricIndex(CapabilityCatalogueDeviceIndex):
    def __init__(self) -> None:
        self._snapshot = None
        self._metadata = None
        self.metadata_ttl_seconds = 600.0
        self._last_metadata_orphans_dropped = 0

    async def enriched_devices(
        self,
        *,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "light",
                "label": "Living Room Lamp",
                "room": "Living Room",
                "capabilities": ["Switch", "SwitchLevel"],
                "currentStates": {"switch": "on"},
            },
            {
                "id": "motion",
                "label": "Kitchen Motion",
                "room": "Kitchen",
                "capabilities": ["MotionSensor"],
                "currentStates": {"motion": "active"},
            },
            {
                "id": "both",
                "label": "Kitchen Light",
                "room": "Kitchen",
                "capabilities": ["Switch", "SwitchLevel", "MotionSensor"],
                "currentStates": {"switch": "on", "motion": "active"},
            },
            {
                "id": "socket",
                "label": "Bedroom Socket",
                "room": "Bedroom",
                "capabilities": ["Switch", "PowerMeter"],
                "currentStates": {"switch": "on", "power": 40},
            },
            {
                "id": "unassigned",
                "label": "Unassigned Motion",
                "capabilities": ["MotionSensor"],
                "currentStates": {"motion": "active"},
            },
        ]


class HealthFallback:
    async def answer(self, query: str) -> dict[str, Any]:
        return {
            "success": True,
            "offline_count": 0,
            "stale_telemetry_count": 0,
        }


class PowerAccounting:
    async def answer(self, query: str) -> dict[str, Any]:
        assert query == "Compare whole-house power with monitored devices"
        return {
            "success": True,
            "whole_house_power_w": 190,
            "monitored_device_power_w": 123.8,
            "active_reading_count": 7,
            "active_power_readings": [
                {"label": "Freezer", "value": 74},
                {"label": "Computer", "value": 28},
            ],
        }


class FailedPowerAccounting:
    async def answer(self, query: str) -> dict[str, Any]:
        raise RuntimeError("power read failed")


def test_active_rooms_require_motion_or_a_light_that_is_on():
    metrics = asyncio.run(RoomMetricIndex().dashboard_metrics())

    assert metrics["active_rooms"] == 2
    assert metrics["active_room_names"] == ["Kitchen", "Living Room"]
    assert metrics["active_room_details"] == [
        {"room": "Kitchen", "lights_on": 1, "motion_active": 2},
        {"room": "Living Room", "lights_on": 1, "motion_active": 0},
    ]
    assert metrics["lights_on"] == 2
    assert metrics["motion_active"] == 3
    assert metrics["switches_on"] == 1


def test_dashboard_exposes_room_and_power_tile_data():
    snapshot = DashboardSnapshot(
        HealthFallback(),
        ttl_seconds=30,
        device_index=RoomMetricIndex(),
        power_accounting=PowerAccounting(),
    )

    value = asyncio.run(snapshot.get())

    assert value["active_rooms"] == 2
    assert value["active_room_names"] == ["Kitchen", "Living Room"]
    assert value["power_success"] is True
    assert value["whole_house_power_w"] == 190
    assert value["monitored_device_power_w"] == 123.8
    assert value["active_power_reading_count"] == 7
    assert value["active_power_readings"] == [
        {"label": "Freezer", "power_w": 74},
        {"label": "Computer", "power_w": 28},
    ]


def test_dashboard_remains_available_when_power_accounting_fails():
    snapshot = DashboardSnapshot(
        HealthFallback(),
        ttl_seconds=30,
        device_index=RoomMetricIndex(),
        power_accounting=FailedPowerAccounting(),
    )

    value = asyncio.run(snapshot.get())

    assert value["success"] is True
    assert value["active_rooms"] == 2
    assert value["power_success"] is False
    assert value["whole_house_power_w"] is None
    assert value["monitored_device_power_w"] is None
    assert value["power_source"] == "unavailable"
    assert "power read failed" in value["power_error"]


def test_rendered_dashboard_has_room_and_power_summary_tiles():
    old_summary = webui.NEW_SUMMARY
    old_status = webui.NEW_STATUS_FUNCTION
    try:
        install_dashboard_health_tile(webui)
        page = webui.render_page("Hubitat MCP AI", "0.10.164")
    finally:
        webui.NEW_SUMMARY = old_summary
        webui.NEW_STATUS_FUNCTION = old_status

    assert 'id="roomsSummary"' in page
    assert 'id="dashRooms"' in page
    assert 'id="dashRoomsDetail"' in page
    assert 'data-q="Which rooms are active based on motion or lights?"' in page
    assert 'id="powerSummary"' in page
    assert 'id="dashWholePower"' in page
    assert 'id="dashPowerDetail"' in page
    assert 'data-q="Compare Octopus power and power devices"' in page
    assert "dash.active_room_names" in page
    assert "dash.whole_house_power_w" in page
    assert "dash.monitored_device_power_w" in page
    assert "formatDashWatts" in page
    assert "Number.isInteger(number)?0:1" in page
    assert (
        "#summaryCard.dashboard-grid"
        "{grid-template-columns:repeat(3,minmax(0,1fr))"
    ) in page
