from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from home_snapshot_service import HomeSnapshotService  # noqa: E402
from mcp_client import HubitatMCPClient, MCPToolResult  # noqa: E402


def result(arguments, data, *, error=False):
    return MCPToolResult(
        "hub_read_devices",
        arguments,
        {},
        "error" if error else "ok",
        data,
        is_error=error,
    )


def context_device(device_id, label, room, capabilities, **attributes):
    return {
        "id": str(device_id),
        "label": label,
        "room": room,
        "capabilities": capabilities,
        "attributes": attributes,
    }


def full_device(device_id, label, room, capabilities, **attributes):
    return {
        "id": str(device_id),
        "label": label,
        "room": room,
        "capabilities": capabilities,
        "attributes": attributes,
    }


def health_summary(devices):
    lines = ["Mode: Home", f"Devices: {len(devices)} of {len(devices)}"]
    lines.extend(devices)
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_home_snapshot_uses_bulk_state_and_projected_health_without_full_inventory(
    monkeypatch,
):
    client = HubitatMCPClient("http://hub/mcp")
    calls = []
    receipts = []
    live_devices = [
        context_device(
            1,
            "Enamul Khan",
            "Life360",
            ["PresenceSensor", "Battery"],
            presence="present",
            battery="52",
        ),
        context_device(
            2,
            "FP2 Livingroom sensor (homekit)",
            "Living Room",
            ["PresenceSensor", "MotionSensor"],
            presence="present",
            motion="active",
        ),
        context_device(
            3,
            "Microwave Door",
            "Kitchen",
            ["ContactSensor", "Battery"],
            contact="open",
            battery="15",
        ),
        context_device(
            4,
            "Hallway Light 1",
            "Hallway",
            ["Switch", "Light"],
            switch="on",
        ),
    ]

    async def get_live_context(refresh=False):
        return {
            "devices": live_devices,
            "totalDevices": len(live_devices),
            "idsComplete": True,
            "partial": False,
            "truncated": False,
        }

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments["tool"] == "hub_list_devices"
        assert arguments["args"]["format"] == "context"
        assert arguments["args"]["attributeNames"] == [
            "healthStatus",
            "networkStatus",
            "rtt",
            "hubAlerts",
        ]
        summary = health_summary(
            [
                "- Enamul Khan (1, Life360) - PresenceSensor, Battery; healthStatus=online",
                "- FP2 Livingroom sensor (homekit) (2, Living Room) - PresenceSensor, MotionSensor; healthStatus=online",
                "- Microwave Door (3, Kitchen) - ContactSensor, Battery; healthStatus=offline",
                "- Hallway Light 1 (4, Hallway) - Switch, Light; healthStatus=online",
            ]
        )
        return result(
            arguments,
            {
                "summary": summary,
                "count": 4,
                "total": 4,
                "hasMore": False,
            },
        )

    async def no_manifest(*_args, **_kwargs):
        raise AssertionError("fast home snapshot must not refresh the detailed manifest")

    monkeypatch.setattr(client, "get_live_context", get_live_context)
    monkeypatch.setattr(client, "call_tool", call_tool)
    monkeypatch.setattr(client, "get_cached_devices", no_manifest)

    service = DeviceQueryService(
        client,
        lambda *args, **kwargs: receipts.append((args, kwargs)),
    )
    snapshot = await service.home_snapshot({})

    assert snapshot.data["complete"] is True
    assert snapshot.data["alerts_complete"] is True
    assert snapshot.data["read_scope"] == "bulk live context + projected health context"
    assert [item["label"] for item in snapshot.data["presence"]] == ["Enamul Khan"]
    assert [item["label"] for item in snapshot.data["tracked_presence"]] == [
        "Enamul Khan"
    ]
    assert [item["label"] for item in snapshot.data["occupancy_presence"]] == [
        "FP2 Livingroom sensor (homekit)"
    ]
    assert [item["label"] for item in snapshot.data["open_contacts"]] == [
        "Microwave Door"
    ]
    assert snapshot.data["low_batteries"] == [
        {"id": "3", "label": "Microwave Door", "room": "Kitchen", "battery": 15}
    ]
    assert snapshot.data["alerts"] == [
        {
            "id": "3",
            "label": "Microwave Door",
            "room": "Kitchen",
            "status": "offline",
            "source": "connectivity",
        }
    ]
    assert len(calls) == 1
    assert calls[0][1]["args"]["format"] == "context"
    assert not any(call[1]["args"] == {} for call in calls)
    assert any(
        kwargs.get("summary", "").endswith("projected health-context device records across 1 page(s)")
        for _args, kwargs in receipts
    )
    await client.close()


@pytest.mark.asyncio
async def test_partial_health_projection_falls_back_to_complete_inventory(monkeypatch):
    client = HubitatMCPClient("http://hub/mcp")
    calls = []
    live_devices = [
        context_device(
            1,
            "Enamul Khan",
            "Life360",
            ["PresenceSensor"],
            presence="present",
        ),
        context_device(
            2,
            "Bedroom Mesh",
            "Bedroom 3",
            ["Switch"],
            switch="on",
        ),
    ]
    complete_devices = [
        full_device(
            1,
            "Enamul Khan",
            "Life360",
            ["PresenceSensor"],
            presence="present",
            healthStatus="online",
        ),
        full_device(
            2,
            "Bedroom Mesh",
            "Bedroom 3",
            ["Switch"],
            switch="on",
            healthStatus="offline",
        ),
    ]

    async def get_live_context(refresh=False):
        return {
            "devices": live_devices,
            "totalDevices": 2,
            "idsComplete": True,
            "partial": False,
            "truncated": False,
        }

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        if arguments.get("args", {}).get("format") == "context":
            return result(
                arguments,
                {
                    "summary": health_summary(
                        [
                            "- Enamul Khan (1, Life360) - PresenceSensor; healthStatus=online",
                            "- Bedroom Mesh (2, Bedroom 3) - Switch (state unavailable)",
                        ]
                    ),
                    "count": 2,
                    "total": 2,
                    "partial": True,
                    "hasMore": False,
                },
            )
        assert arguments == {"tool": "hub_list_devices", "args": {}}
        return result(arguments, {"devices": complete_devices})

    async def cached_devices(refresh=False):
        return complete_devices

    monkeypatch.setattr(client, "get_live_context", get_live_context)
    monkeypatch.setattr(client, "call_tool", call_tool)
    monkeypatch.setattr(client, "get_cached_devices", cached_devices)

    service = DeviceQueryService(client, lambda *_args, **_kwargs: None)
    snapshot = await service.home_snapshot({})

    assert snapshot.data["complete"] is True
    assert snapshot.data["alerts_complete"] is True
    assert snapshot.data["read_scope"] == "complete inventory fallback"
    assert snapshot.data["alerts"] == [
        {
            "id": "2",
            "label": "Bedroom Mesh",
            "room": "Bedroom 3",
            "status": "offline",
            "source": "connectivity",
        }
    ]
    assert any(arguments == {"tool": "hub_list_devices", "args": {}} for _, arguments in calls)
    await client.close()


def test_health_parser_preserves_commas_inside_hub_alerts():
    parsed, complete = HomeSnapshotService._parse_health_summary(
        health_summary(
            [
                "- Front Door (17, Hallway) - ContactSensor; "
                "hubAlerts=lowBattery, tamper, networkStatus=online"
            ]
        )
    )

    assert complete is True
    assert parsed == [
        {
            "id": "17",
            "label": "Front Door",
            "room": "Hallway",
            "currentStates": {
                "hubAlerts": "lowBattery, tamper",
                "networkStatus": "online",
            },
        }
    ]
