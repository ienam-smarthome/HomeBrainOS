from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import HubitatMCPClient, MCPToolResult  # noqa: E402


@pytest.mark.asyncio
async def test_home_snapshot_uses_bulk_context_without_full_inventory() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")

    async def get_live_context():
        return {
            "devices": [
                {
                    "id": "1",
                    "label": "Enamul Khan",
                    "room": "Life360",
                    "capabilities": ["PresenceSensor", "Battery"],
                    "attributes": {"presence": "present", "battery": "80"},
                },
                {
                    "id": "2",
                    "label": "FP2 Livingroom sensor (homekit)",
                    "room": "Living Room",
                    "capabilities": ["PresenceSensor", "MotionSensor"],
                    "attributes": {"presence": "present", "motion": "active"},
                },
                {
                    "id": "3",
                    "label": "Hallway Light 1",
                    "room": "Hallway",
                    "capabilities": ["Switch", "Light"],
                    "attributes": {"switch": "on"},
                },
                {
                    "id": "4",
                    "label": "Microwave Door",
                    "room": "Kitchen",
                    "capabilities": ["ContactSensor", "Battery"],
                    "attributes": {"contact": "open", "battery": "15"},
                },
            ],
            "totalDevices": 4,
            "partial": False,
            "truncated": False,
            "idsComplete": True,
        }

    async def unexpected_call_tool(*_args, **_kwargs):
        raise AssertionError(
            "home snapshot must not issue hub_list_devices when live context is complete"
        )

    client.get_live_context = get_live_context  # type: ignore[method-assign]
    client.call_tool = unexpected_call_tool  # type: ignore[method-assign]
    receipts = []
    service = DeviceQueryService(
        client,
        lambda *args, **kwargs: receipts.append((args, kwargs)),
    )

    result = await service.home_snapshot({})

    assert result.data["read_scope"] == "bulk live context"
    assert result.data["complete"] is True
    assert result.data["alerts_complete"] is False
    assert result.data["counts"]["alerts"] is None
    assert [item["label"] for item in result.data["presence"]] == ["Enamul Khan"]
    assert [item["label"] for item in result.data["tracked_presence"]] == ["Enamul Khan"]
    assert [item["label"] for item in result.data["active_motion"]] == [
        "FP2 Livingroom sensor (homekit)"
    ]
    assert [item["label"] for item in result.data["lights_on"]] == ["Hallway Light 1"]
    assert [item["label"] for item in result.data["open_contacts"]] == ["Microwave Door"]
    assert result.data["low_batteries"] == [
        {
            "id": "4",
            "label": "Microwave Door",
            "room": "Kitchen",
            "battery": 15,
        }
    ]
    assert receipts[0][0][0] == "hub_read_devices"
    assert receipts[0][0][1]["resource"] == "hubitat://context"
    assert receipts[0][1]["evidence_kind"] == "authoritative_state_snapshot"

    await client.close()


@pytest.mark.asyncio
async def test_home_snapshot_fallback_preserves_complete_health_alerts() -> None:
    devices = [
        {
            "id": "1",
            "label": "Hallway Motion",
            "room": "Hallway",
            "capabilities": ["MotionSensor"],
            "attributes": {"motion": "inactive", "healthStatus": "offline"},
        }
    ]

    class FallbackMCP:
        async def call_tool(self, name, arguments):
            assert name == "hub_read_devices"
            assert arguments == {"tool": "hub_list_devices", "args": {}}
            return MCPToolResult(name, arguments, {}, "", {"devices": devices})

        async def get_cached_devices(self):
            return devices

    service = DeviceQueryService(FallbackMCP(), lambda *_args, **_kwargs: None)

    result = await service.home_snapshot({})

    assert result.data["read_scope"] == "complete inventory"
    assert result.data["alerts_complete"] is True
    assert result.data["counts"]["alerts"] == 1
    assert result.data["alerts"] == [
        {
            "id": "1",
            "label": "Hallway Motion",
            "room": "Hallway",
            "status": "offline",
            "source": "connectivity",
        }
    ]
