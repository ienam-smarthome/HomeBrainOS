from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from conversation_context_safe import SafeConversationContextStore  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


DEVICES = [
    {
        "id": "1",
        "label": "Livingroom Light 1",
        "room": "Livingroom",
        "currentStates": {"switch": "on"},
        "capabilities": ["Switch"],
    },
    {
        "id": "2",
        "label": "Livingroom Meter",
        "room": "Livingroom",
        "currentStates": {"temperature": 23.5},
        "capabilities": ["Temperature Measurement"],
    },
]


class FakeIndex:
    async def enriched_devices(self):
        return [dict(item) for item in DEVICES]

    async def summary_devices(self):
        return [dict(item) for item in DEVICES]

    async def summary_result(self):
        return MCPToolResult(
            name="hub_list_devices",
            arguments={},
            raw={},
            text="",
            data={"devices": [dict(item) for item in DEVICES]},
            is_error=False,
        )

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        attrs = item.get("currentStates") or {}
        groups = set()
        if "switch" in attrs:
            groups.add("light")
        if "temperature" in attrs:
            groups.add("temperature")
        return groups


class FakeFallback:
    async def _control_group(self, *args, **kwargs):
        raise AssertionError("group control should not be called in these tests")


def request(query: str, session_id: str = "browser-1"):
    return SimpleNamespace(query=query, session_id=session_id, history=[])


async def capture(store, query, answer):
    return await store.capture(
        request(query),
        answer,
        original_query=query,
        resolved_query=query,
    )


def test_unrelated_answer_clears_previous_device_pronouns():
    async def scenario():
        store = SafeConversationContextStore(FakeIndex(), FakeFallback())
        await capture(
            store,
            "Show Livingroom Light 1",
            {
                "success": True,
                "intent": "fallback-device-status",
                "device_label": "Livingroom Light 1",
                "message": "Livingroom Light 1 is on.",
                "display": {"items": [{"title": "Livingroom Light 1", "value": "On"}]},
            },
        )
        before = await store.resolve(request("turn it off"))
        await capture(
            store,
            "What is the weather?",
            {
                "success": True,
                "intent": "fallback-weather",
                "message": "Clear and dry.",
                "display": {"title": "Weather", "metrics": [], "items": []},
            },
        )
        after = await store.resolve(request("turn it off"))
        return before, after

    before, after = asyncio.run(scenario())
    assert before.query == "turn off Livingroom Light 1"
    assert after.query == "turn it off"
    assert after.answer is None


def test_empty_new_inventory_does_not_reuse_previous_devices():
    async def scenario():
        store = SafeConversationContextStore(FakeIndex(), FakeFallback())
        await capture(
            store,
            "Show Livingroom Light 1",
            {
                "success": True,
                "intent": "fallback-device-status",
                "device_label": "Livingroom Light 1",
                "message": "Livingroom Light 1 is on.",
                "display": {"items": [{"title": "Livingroom Light 1", "value": "On"}]},
            },
        )
        await capture(
            store,
            "Show smoke detectors",
            {
                "success": True,
                "intent": "fallback-device-type-smoke",
                "device_type": "smoke",
                "device_count": 0,
                "message": "No smoke detectors were found.",
                "display": {"title": "Smoke detectors", "metrics": [], "items": []},
            },
        )
        state = await store.get("browser-1")
        resolution = await store.resolve(request("turn them off"))
        return state, resolution

    state, resolution = asyncio.run(scenario())
    assert state.last_device_type == "smoke"
    assert state.devices == []
    assert resolution.query == "turn them off"
    assert resolution.answer["confirmation_required"] is True
    assert "recent device result" in resolution.answer["message"]


def test_living_room_follow_up_preserves_room_name_word():
    async def scenario():
        store = SafeConversationContextStore(FakeIndex(), FakeFallback())
        await capture(
            store,
            "List temperature sensors",
            {
                "success": True,
                "intent": "fallback-device-type-temperature",
                "device_type": "temperature",
                "message": "Temperature sensors",
                "display": {"items": [{"title": "Livingroom Meter", "value": "23.5°C"}]},
            },
        )
        return await store.resolve(request("What about the living room?"))

    resolution = asyncio.run(scenario())
    assert resolution.answer["room"] == "Livingroom"
    assert resolution.answer["display"]["items"][0]["title"] == "Livingroom Meter"
