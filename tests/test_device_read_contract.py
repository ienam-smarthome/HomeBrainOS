from __future__ import annotations

from typing import Any

import pytest

from device_read_contract import (
    device_read_plan,
    normalize_hub_list_devices_arguments,
    projected_state_shape_is_usable,
)
from device_state_summary import device_attributes
from mcp_client import HubitatMCPClient


def test_summary_state_plan_uses_current_states() -> None:
    plan = device_read_plan(include_states=True)

    assert plan.detailed is False
    assert plan.state_field == "currentStates"
    assert plan.fields == ("id", "name", "label", "room", "currentStates")


def test_detailed_state_plan_uses_attributes() -> None:
    plan = device_read_plan(
        include_states=True,
        include_capabilities=True,
        include_commands=True,
    )

    assert plan.detailed is True
    assert plan.state_field == "attributes"
    assert plan.fields == (
        "id",
        "name",
        "label",
        "room",
        "capabilities",
        "attributes",
        "commands",
    )


def test_health_manifest_can_request_last_activity() -> None:
    plan = device_read_plan(
        include_states=True,
        include_capabilities=True,
        include_commands=True,
        include_last_activity=True,
    )

    assert plan.fields[-1] == "lastActivity"


def test_normalizer_repairs_the_010433_mixed_projection() -> None:
    arguments = {
        "tool": "hub_list_devices",
        "args": {
            "detailed": True,
            "capabilityFilter": "MotionSensor",
            "fields": [
                "id",
                "name",
                "label",
                "room",
                "capabilities",
                "currentStates",
            ],
            "limit": 100,
            "offset": 0,
        },
    }

    expected = normalize_hub_list_devices_arguments("hub_read_devices", arguments)

    assert expected == "attributes"
    assert arguments["args"]["fields"] == [
        "id",
        "name",
        "label",
        "room",
        "capabilities",
        "attributes",
    ]


def test_projection_shape_validation_distinguishes_missing_from_empty_state() -> None:
    assert projected_state_shape_is_usable(
        [{"id": "1", "attributes": []}], "attributes"
    )
    assert projected_state_shape_is_usable(
        [{"id": "1", "attributes": {}}], "attributes"
    )
    assert not projected_state_shape_is_usable(
        [{"id": "1", "capabilities": ["MotionSensor"]}], "attributes"
    )


def test_projection_shape_validation_rejects_mixed_complete_and_missing_records() -> None:
    assert not projected_state_shape_is_usable(
        [
            {"id": "1", "attributes": [{"name": "motion", "value": "active"}]},
            {"id": "2", "capabilities": ["MotionSensor"]},
        ],
        "attributes",
    )


@pytest.mark.asyncio
async def test_mcp_client_normalizes_detailed_projection_before_posting() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    posted: list[dict[str, Any]] = []

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        posted.append(payload)
        return {
            "result": {
                "structuredContent": {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Living Room Motion",
                            "room": "Living Room",
                            "capabilities": ["MotionSensor"],
                            "attributes": [
                                {"name": "motion", "value": "active"}
                            ],
                        }
                    ],
                    "count": 1,
                    "total": 1,
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]
    arguments = {
        "tool": "hub_list_devices",
        "args": {
            "detailed": True,
            "capabilityFilter": "MotionSensor",
            "fields": [
                "id", "name", "label", "room", "capabilities", "currentStates"
            ],
            "limit": 100,
            "offset": 0,
        },
    }

    result = await client.call_tool("hub_read_devices", arguments)

    sent = posted[0]["params"]["arguments"]["args"]
    assert sent["fields"] == [
        "id", "name", "label", "room", "capabilities", "attributes"
    ]
    assert result.is_error is False
    devices = HubitatMCPClient._find_device_list(result.data) or []
    assert device_attributes(devices[0])["motion"] == "active"

    await client.close()


@pytest.mark.asyncio
async def test_mcp_client_rejects_nonempty_projection_with_missing_state_shape() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True

    async def fake_post(
        payload: dict[str, Any], allow_empty: bool = False
    ) -> dict[str, Any]:
        return {
            "result": {
                "structuredContent": {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Living Room Motion",
                            "room": "Living Room",
                            "capabilities": ["MotionSensor"],
                        }
                    ],
                    "count": 1,
                    "total": 1,
                }
            }
        }

    client._post = fake_post  # type: ignore[method-assign]
    result = await client.call_tool(
        "hub_read_devices",
        {
            "tool": "hub_list_devices",
            "args": {
                "detailed": True,
                "capabilityFilter": "MotionSensor",
                "fields": [
                    "id", "name", "label", "room", "capabilities", "currentStates"
                ],
                "limit": 100,
                "offset": 0,
            },
        },
    )

    assert result.is_error is True
    assert result.data["projectionMismatch"] is True
    assert result.data["expectedStateField"] == "attributes"
    assert "omitted the projected live-state field" in result.data["error"]

    await client.close()
