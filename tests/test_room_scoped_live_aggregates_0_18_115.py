"""0.18.115: original user room scope survives model-selected global aggregate tools.

Mocks the authoritative Hubitat live-context rows and calls the actual
service/agent wrappers. No real Hubitat commands or provider requests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from device_query_service import DeviceQueryService
from deterministic_tool_presenter import present_tool_result
from mcp_agent_orchestrator import UnifiedMCPAgent
from mcp_client import MCPToolResult
from tool_registry import active_lights_tool, active_switches_tool
from room_scoped_live_aggregates import room_scope

DEVICES = [
    {"id": "7805", "label": "Livingroom Light 1",
     "room": "Living Room", "capabilities": ["Switch", "Light"],
     "attributes": {"switch": "off"}},
    {"id": "7806", "label": "Livingroom Light 2",
     "room": "Living Room", "capabilities": ["Switch", "Light"],
     "attributes": {"switch": "on"}},
    {"id": "1", "label": "Bedroom 1 Light",
     "room": "Bedroom 1", "capabilities": ["Switch", "Light"],
     "attributes": {"switch": "on"}},
    {"id": "2", "label": "Bedroom 2 Light",
     "room": "Bedroom 2", "capabilities": ["Switch", "Light"],
     "attributes": {"switch": "on"}},
    {"id": "3", "label": "Big lamp", "room": "Bedroom 1",
     "capabilities": ["Switch", "Light"], "attributes": {"switch": "on"}},
    {"id": "4", "label": "Hallway Light 1", "room": "Hallway",
     "capabilities": ["Switch", "Light"], "attributes": {"switch": "on"}},
    {"id": "5", "label": "Hallway Light 2", "room": "Hallway",
     "capabilities": ["Switch", "Light"], "attributes": {"switch": "on"}},
    {"id": "6", "label": "My Floor Lamp", "room": "Bedroom 3",
     "capabilities": ["Switch", "Light"], "attributes": {"switch": "on"}},
    {"id": "9", "label": "Living Room PC socket", "room": "Living Room",
     "capabilities": ["Switch", "Outlet"], "attributes": {"switch": "on"}},
    {"id": "10", "label": "Hallway socket", "room": "Hallway",
     "capabilities": ["Switch", "Outlet"], "attributes": {"switch": "on"}},
]


@pytest.fixture
def fake_snapshot(monkeypatch):
    calls = []

    async def fake_bulk(self, attrs, **_kwargs):
        calls.append(set(attrs))
        data = {"devices": list(DEVICES)}
        result = MCPToolResult(
            "hub_read_devices", {"resource": "hubitat://context"},
            {}, json.dumps(data), data,
        )
        return result, list(DEVICES)

    monkeypatch.setattr(DeviceQueryService, "_bulk_live_devices", fake_bulk)
    return calls


@pytest.mark.asyncio
async def test_original_live_failure_room_is_enforced_when_model_omits_room(fake_snapshot):
    service = DeviceQueryService(None, lambda *_a, **_k: None)
    result = await service.active_lights(
        {}, user_question="which livingroom lights are currently on?"
    )
    assert result.data["count"] == 1
    assert result.data["scopeVerified"] is True
    assert result.data["matchedRooms"] == ["Living Room"]
    assert [row["label"] for row in result.data["lights"]] == [
        "Livingroom Light 2"
    ]
    message = present_tool_result("homebrain_active_lights", result.data)
    assert message == "1 light is on in **Living Room**: Livingroom Light 2."
    assert "Bedroom" not in message
    assert fake_snapshot == [{"switch"}]


@pytest.mark.asyncio
async def test_currently_no_livingroom_lights_on_is_not_whole_home_result(
    fake_snapshot, monkeypatch
):
    off = [dict(device) for device in DEVICES]
    for device in off:
        if device["room"] == "Living Room" and "Light" in device["label"]:
            device["attributes"] = {"switch": "off"}

    async def fake_bulk(self, attrs, **kwargs):
        data = {"devices": off}
        return MCPToolResult("hub_read_devices", {}, {}, json.dumps(data), data), off

    monkeypatch.setattr(DeviceQueryService, "_bulk_live_devices", fake_bulk)
    result = await DeviceQueryService(None, lambda *_a, **_k: None).active_lights(
        {}, user_question="Show lights on in the Living Room"
    )
    assert result.data["lights"] == []
    assert result.data["complete"]
    assert present_tool_result("homebrain_active_lights", result.data) == (
        "No lights are currently on in **Living Room**."
    )


@pytest.mark.asyncio
async def test_model_cannot_override_room_named_by_user(fake_snapshot):
    service = DeviceQueryService(None, lambda *_a, **_k: None)
    result = await service.active_lights(
        {"room": "Hallway"},
        user_question="which livingroom lights are on?"
    )
    assert result.data["matchedRooms"] == ["Living Room"]
    assert [row["label"] for row in result.data["lights"]] == [
        "Livingroom Light 2"
    ]


@pytest.mark.asyncio
async def test_genuinely_whole_home_light_question_keeps_every_on_light(fake_snapshot):
    result = await DeviceQueryService(None, lambda *_a, **_k: None).active_lights(
        {}, user_question="Which lights are currently on across my home?"
    )
    assert result.data["scope"] == "whole-home"
    assert result.data["count"] == 7
    assert "Bedroom 1 Light" in present_tool_result(
        "homebrain_active_lights", result.data
    )


@pytest.mark.asyncio
async def test_non_light_switches_obey_same_room_semantics(fake_snapshot):
    result = await DeviceQueryService(None, lambda *_a, **_k: None).active_switches(
        {}, user_question="Which Living Room switches are on?"
    )
    assert result.data["scope"] == "room"
    assert [row["label"] for row in result.data["switches"]] == [
        "Living Room PC socket"
    ]
    msg = present_tool_result("homebrain_active_switches", result.data)
    assert "Living Room PC socket" in msg and "Hallway socket" not in msg


@pytest.mark.asyncio
async def test_unknown_tool_room_never_turns_into_unfiltered_success(fake_snapshot):
    result = await DeviceQueryService(None, lambda *_a, **_k: None).active_lights(
        {"room": "Imaginary room"}, user_question=""
    )
    assert result.is_error
    assert result.data["lights"] == []
    assert not result.data["complete"]


def test_multi_room_requests_and_aliases_are_grounded_in_room_names():
    a, requested, verified = room_scope(
        DEVICES, question="Show lights in Livingroom and Bedroom 2"
    )
    assert a == ("Living Room", "Bedroom 2")
    assert requested and verified
    a, requested, verified = room_scope(
        DEVICES, question="Which lights in the living room?"
    )
    assert a == ("Living Room",) and requested and verified


def test_lights_and_switches_schemas_offer_optional_room_field():
    assert active_lights_tool().input_schema["properties"]["room"]["type"] == "string"
    assert active_switches_tool().input_schema["properties"]["room"]["type"] == "string"
    assert active_lights_tool().input_schema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_real_agent_wrapper_injects_original_user_scope(fake_snapshot):
    class FakeMCP:
        async def list_tools(self): return []
    agent = UnifiedMCPAgent(
        FakeMCP(), "key", "fake", require_sensitive_confirmation=False
    )
    token = agent._current_user_objective.set(
        "which livingroom lights are currently on?"
    )
    try:
        result = await agent._active_lights({})
        assert result.data["scope"] == "room"
        assert result.data["matchedRooms"] == ["Living Room"]
        assert [x["label"] for x in result.data["lights"]] == [
            "Livingroom Light 2"
        ]
    finally:
        agent._current_user_objective.reset(token)
