from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from conversation_context_safe import SafeConversationContextStore  # noqa: E402


DEVICES = [
    {
        "id": "1",
        "label": "Livingroom TRV",
        "room": "Livingroom",
        "currentStates": {"battery": 12},
    },
    {
        "id": "2",
        "label": "Fridge Door",
        "room": "Kitchen",
        "currentStates": {"battery": 17},
    },
]


class FakeIndex:
    async def enriched_devices(self):
        return [dict(item) for item in DEVICES]

    async def summary_devices(self):
        return [dict(item) for item in DEVICES]

    @staticmethod
    def _groups(item):
        return {"battery"} if "battery" in (item.get("currentStates") or {}) else set()


class FakeFallback:
    pass


def req(query: str):
    return SimpleNamespace(query=query, session_id="browser-1", history=[])


def test_which_battery_is_lowest_uses_context_comparison():
    async def scenario():
        store = SafeConversationContextStore(FakeIndex(), FakeFallback())
        await store.capture(
            req("List battery devices"),
            {
                "success": True,
                "intent": "fallback-device-type-battery",
                "device_type": "battery",
                "message": "Battery devices",
                "display": {
                    "items": [
                        {"title": "Livingroom TRV", "value": "12%"},
                        {"title": "Fridge Door", "value": "17%"},
                    ]
                },
            },
            original_query="List battery devices",
            resolved_query="List battery devices",
        )
        return await store.resolve(req("Which battery is lowest?"))

    resolution = asyncio.run(scenario())
    assert resolution.reason == "context-comparison"
    assert resolution.answer["device_label"] == "Livingroom TRV"
    assert "12%" in resolution.answer["message"]
