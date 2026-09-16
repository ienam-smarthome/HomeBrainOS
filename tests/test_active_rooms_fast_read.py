from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import HubitatMCPClient  # noqa: E402


def _resource_response(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": {
            "contents": [
                {
                    "uri": "hubitat://context",
                    "mimeType": "application/json",
                    "text": json.dumps(context),
                }
            ],
            "ttlMs": 0,
            "cacheScope": "private",
        }
    }


def _context() -> dict[str, Any]:
    return {
        "currentMode": "Home",
        "devices": [
            {
                "id": "1",
                "label": "Living Room Motion",
                "room": "Living Room",
                "capabilities": ["MotionSensor"],
                "attributes": {"motion": "active", "battery": "88"},
            },
            {
                "id": "2",
                "label": "Bedroom Lamp",
                "room": "Bedroom 1",
                "capabilities": ["Switch", "Light"],
                "attributes": {"switch": "off"},
            },
            {
                "id": "3",
                "label": "Kitchen Light",
                "room": "Kitchen",
                "capabilities": ["Switch", "Light"],
                "attributes": {"switch": "on", "battery": "15"},
            },
        ],
        "totalDevices": 3,
        "partial": False,
        "truncated": False,
    }


@pytest.mark.asyncio
async def test_active_rooms_uses_one_bulk_context_resource_read() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        assert payload["method"] == "resources/read"
        assert payload["params"] == {"uri": "hubitat://context"}
        return _resource_response(_context())

    client._post = fake_post  # type: ignore[method-assign]
    receipts = []
    service = DeviceQueryService(
        client, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.active_rooms({})

    assert result.data["active_rooms"] == [
        {"name": "Kitchen", "reasons": ["light on"]},
        {"name": "Living Room", "reasons": ["motion"]},
    ]
    assert result.data["read_scope"] == "bulk live context"
    assert len(posts) == 1
    assert len(receipts) == 1
    assert receipts[0][0][0] == "hub_read_devices"
    assert receipts[0][0][1]["resource"] == "hubitat://context"
    assert receipts[0][0][1]["required_attributes"] == ["motion", "switch"]
    assert receipts[0][1]["summary"] == "3 bulk live-context device records"

    await client.close()


@pytest.mark.asyncio
async def test_common_live_reads_share_the_same_short_lived_context_snapshot() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        return _resource_response(_context())

    client._post = fake_post  # type: ignore[method-assign]
    service = DeviceQueryService(client, lambda *_a, **_k: None)

    rooms = await service.active_rooms({})
    lights = await service.active_lights({})
    low_battery = await service.filter_devices(
        {"attribute": "battery", "operator": "lte", "value": 20}
    )
    motion = await service.filter_devices(
        {"attribute": "motion", "operator": "eq", "value": "active"}
    )

    assert rooms.data["count"] == 2
    assert lights.data["lights"] == [
        {
            "id": "3",
            "label": "Kitchen Light",
            "room": "Kitchen",
            "switch": "on",
        }
    ]
    assert low_battery.data["count"] == 1
    assert low_battery.data["matches"][0]["label"] == "Kitchen Light"
    assert motion.data["count"] == 1
    assert motion.data["matches"][0]["label"] == "Living Room Motion"
    # One upstream bulk read serves all four structured consumers inside the 2s TTL.
    assert [post["method"] for post in posts] == ["resources/read"]

    await client.close()


@pytest.mark.asyncio
async def test_partial_context_falls_back_to_complete_inventory() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    posts: list[dict[str, Any]] = []

    partial = _context()
    partial["partial"] = True

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        if payload["method"] == "resources/read":
            return _resource_response(partial)
        assert payload["method"] == "tools/call"
        assert payload["params"]["arguments"] == {
            "tool": "hub_list_devices",
            "args": {},
        }
        return {
            "result": {
                "structuredContent": {
                    "devices": [
                        {
                            "id": "7",
                            "label": "Fallback Motion",
                            "room": "Office",
                            "capabilities": ["MotionSensor"],
                            "currentStates": {"motion": "active"},
                        }
                    ]
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]
    receipts = []
    service = DeviceQueryService(
        client, lambda *args, **kwargs: receipts.append((args, kwargs))
    )

    result = await service.active_rooms({})

    assert result.data["active_rooms"] == [
        {"name": "Office", "reasons": ["motion"]}
    ]
    assert [post["method"] for post in posts] == ["resources/read", "tools/call"]
    # Partial context is never recorded as authoritative evidence; only fallback is.
    assert len(receipts) == 1
    assert receipts[0][0][1] == {"tool": "hub_list_devices", "args": {}}

    await client.close()


@pytest.mark.asyncio
async def test_attribute_outside_context_contract_uses_complete_inventory() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    posts: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posts.append(payload)
        assert payload["method"] == "tools/call"
        return {
            "result": {
                "structuredContent": {
                    "devices": [
                        {
                            "id": "9",
                            "label": "Offline Sensor",
                            "attributes": {"healthStatus": "offline"},
                        }
                    ]
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]
    service = DeviceQueryService(client, lambda *_a, **_k: None)

    result = await service.filter_devices(
        {"attribute": "healthStatus", "operator": "eq", "value": "offline"}
    )

    assert result.data["count"] == 1
    assert result.data["matches"][0]["label"] == "Offline Sensor"
    assert [post["method"] for post in posts] == ["tools/call"]

    await client.close()
