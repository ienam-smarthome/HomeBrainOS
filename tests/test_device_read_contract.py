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
    assert plan.fields == ("id", "name", "label", "room", "driver", "currentStates")


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
        "driver",
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
    assert arguments["args"]["format"] == "detailed"
    assert "detailed" not in arguments["args"]
    assert "offset" not in arguments["args"]
    assert arguments["args"]["cursor"] == "0"


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
    assert sent["format"] == "detailed"
    assert sent["cursor"] == "0"
    assert "detailed" not in sent and "offset" not in sent
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


def test_device_plan_generates_only_native_format_and_cursor_fields() -> None:
    detailed = device_read_plan(
        include_states=True, include_capabilities=True,
    ).arguments(limit=20, offset=40)
    assert detailed["format"] == "detailed"
    assert detailed["cursor"] == "40"
    assert "detailed" not in detailed
    assert "offset" not in detailed
    assert "attributes" in detailed["fields"]

    summary = device_read_plan(include_states=True).arguments(
        limit=20, offset=0
    )
    assert summary["format"] == "summary"
    assert summary["cursor"] == "0"
    assert "currentStates" in summary["fields"]


def test_native_wire_normalizer_removes_legacy_flags_even_without_fields() -> None:
    gateway = {
        "tool": "hub_list_devices",
        "args": {"labelFilter": "Synthetic Lamp", "detailed": True, "offset": 20},
    }
    assert normalize_hub_list_devices_arguments("hub_read_devices", gateway) is None
    assert gateway["args"] == {
        "labelFilter": "Synthetic Lamp", "format": "detailed", "cursor": "20",
    }

    explicit = {
        "tool": "hub_list_devices",
        "args": {
            "labelFilter": "Synthetic Lamp",
            "format": "summary",
            "fields": ["id", "label", "capabilities", "currentStates"],
        },
    }
    assert normalize_hub_list_devices_arguments("hub_read_devices", explicit) == "attributes"
    assert explicit["args"]["format"] == "detailed"
    assert explicit["args"]["fields"] == [
        "id", "label", "capabilities", "attributes",
    ]


@pytest.mark.asyncio
async def test_native_contract_rejects_legacy_but_accepts_normalized_targeted_read() -> None:
    client = HubitatMCPClient("http://hubitat.test/mcp")
    client._initialized = True
    accepted = []
    async def strict_native_post(payload: dict[str, Any], allow_empty: bool = False):
        args = payload["params"]["arguments"]["args"]
        accepted.append(dict(args))
        allowed = {
            "scope", "format", "labelFilter", "capabilityFilter",
            "roomFilter", "fields", "limit", "cursor", "attributeNames",
            "stateFilter", "disabled", "staleHours", "changedSince",
        }
        if set(args) - allowed:
            return {"result": {"structuredContent": {
                "success": False,
                "error": "Unknown argument: " + ",".join(sorted(set(args)-allowed)),
            }}}
        return {"result": {"structuredContent": {
            "success": True,
            "devices": [{
                "id": "801", "label": "Synthetic Lamp",
                "attributes": [{"name": "switch", "currentValue": "on"},
                               {"name": "level", "currentValue": 60}],
                "capabilities": ["Switch", "SwitchLevel"],
                "commands": ["on", "off", "setLevel"],
            }],
            "count": 1, "total": 1,
        }}}
    client._post = strict_native_post  # type: ignore[method-assign]
    result = await client.call_tool(
        "hub_read_devices",
        {
            "tool": "hub_list_devices",
            "args": {
                "labelFilter": "Synthetic Lamp",
                "fields": [
                    "id", "name", "label", "room",
                    "capabilities", "attributes", "commands",
                ],
                "detailed": True,
            },
        },
    )
    assert result.is_error is False
    assert len(accepted) == 1
    assert accepted[0]["format"] == "detailed"
    assert "detailed" not in accepted[0]
    devices = HubitatMCPClient._find_device_list(result.data) or []
    assert len(devices) == 1
    assert device_attributes(devices[0])["switch"] == "on"
    assert device_attributes(devices[0])["level"] == 60
    await client.close()
