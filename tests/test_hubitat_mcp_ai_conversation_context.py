from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from conversation_context import ConversationContextStore  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


DEVICES = [
    {
        "id": "1",
        "label": "Bedroom 2 Light",
        "room": "Bedroom 2",
        "currentStates": {"switch": "on", "level": 30},
        "capabilities": ["Switch", "Switch Level"],
    },
    {
        "id": "2",
        "label": "Livingroom Light 1",
        "room": "Livingroom",
        "currentStates": {"switch": "on", "level": 70},
        "capabilities": ["Switch", "Switch Level"],
    },
    {
        "id": "3",
        "label": "Bathroom Meter",
        "room": "Bathroom",
        "currentStates": {"temperature": 24.2, "humidity": 67},
        "capabilities": ["Temperature Measurement", "Relative Humidity Measurement"],
    },
    {
        "id": "4",
        "label": "Hallway Meter",
        "room": "Hallway",
        "currentStates": {"temperature": 21.1, "humidity": 52},
        "capabilities": ["Temperature Measurement", "Relative Humidity Measurement"],
    },
    {
        "id": "5",
        "label": "Bedroom 1 FP300",
        "room": "Bedroom 1",
        "currentStates": {"motion": "active"},
        "capabilities": ["Motion Sensor"],
    },
    {
        "id": "6",
        "label": "Hallway Motion",
        "room": "Hallway",
        "currentStates": {"motion": "inactive"},
        "capabilities": ["Motion Sensor"],
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
            groups.add("light" if "light" in str(item.get("label") or "").lower() else "switch")
        for key in ("temperature", "humidity", "motion", "battery", "power", "contact"):
            if key in attrs:
                groups.add(key)
        return groups


class FakeFallback:
    def __init__(self) -> None:
        self.group_calls: list[dict[str, Any]] = []

    async def _control_group(self, requested_name, action, rows, source):
        self.group_calls.append(
            {
                "requested_name": requested_name,
                "action": action,
                "ids": [str(item.get("id")) for item in rows],
            }
        )
        return {
            "success": True,
            "intent": "fallback-device-group-control-confirmed",
            "message": f"Confirmed {action} for {len(rows)} devices.",
            "display": {
                "title": "Previous devices",
                "metrics": [],
                "items": [
                    {"title": item["label"], "value": action.title()}
                    for item in rows
                ],
            },
        }


def request(query: str, session_id: str = "browser-1"):
    return SimpleNamespace(query=query, session_id=session_id, history=[])


def answer_with_devices(intent: str, title: str, labels: list[str], **extra):
    return {
        "success": True,
        "intent": intent,
        "message": title,
        "display": {
            "title": title,
            "metrics": [],
            "items": [{"title": label, "value": "Available"} for label in labels],
        },
        **extra,
    }


async def seed(store: ConversationContextStore, query_text: str, answer: dict[str, Any]):
    req = request(query_text)
    return await store.capture(
        req,
        answer,
        original_query=query_text,
        resolved_query=query_text,
    )


def test_room_qualified_follow_up_control_resolves_one_known_device():
    async def scenario():
        store = ConversationContextStore(FakeIndex(), FakeFallback())
        await seed(
            store,
            "Which lights are on?",
            answer_with_devices(
                "fallback-lights-on",
                "Lights on",
                ["Bedroom 2 Light", "Livingroom Light 1"],
            ),
        )
        return await store.resolve(request("turn the living-room one off"))

    resolution = asyncio.run(scenario())
    assert resolution.answer is None
    assert resolution.query == "turn off Livingroom Light 1"
    assert resolution.reason == "context-single-device-control"


def test_it_only_resolves_when_previous_result_has_one_device():
    async def scenario():
        store = ConversationContextStore(FakeIndex(), FakeFallback())
        await seed(
            store,
            "Show Bedroom 2 Light",
            answer_with_devices(
                "fallback-device-status",
                "Bedroom 2 Light",
                ["Bedroom 2 Light"],
                device_label="Bedroom 2 Light",
            ),
        )
        one = await store.resolve(request("turn it off"))
        await seed(
            store,
            "Which lights are on?",
            answer_with_devices(
                "fallback-lights-on",
                "Lights on",
                ["Bedroom 2 Light", "Livingroom Light 1"],
            ),
        )
        ambiguous = await store.resolve(request("turn the one off"))
        return one, ambiguous

    one, ambiguous = asyncio.run(scenario())
    assert one.query == "turn off Bedroom 2 Light"
    assert ambiguous.answer["confirmation_required"] is True
    assert "Bedroom 2 Light" in ambiguous.answer["message"]
    assert "Livingroom Light 1" in ambiguous.answer["message"]


def test_turn_them_off_controls_only_previous_switch_devices():
    async def scenario():
        fallback = FakeFallback()
        store = ConversationContextStore(FakeIndex(), fallback)
        await seed(
            store,
            "Which lights are on?",
            answer_with_devices(
                "fallback-lights-on",
                "Lights on",
                ["Bedroom 2 Light", "Livingroom Light 1"],
            ),
        )
        resolution = await store.resolve(request("turn them off"))
        return fallback, resolution

    fallback, resolution = asyncio.run(scenario())
    assert resolution.answer["success"] is True
    assert resolution.answer["route"] == "mcp-context"
    assert fallback.group_calls == [
        {
            "requested_name": "Previous devices",
            "action": "off",
            "ids": ["1", "2"],
        }
    ]


def test_temperature_follow_up_compares_recent_devices_without_ollama():
    async def scenario():
        store = ConversationContextStore(FakeIndex(), FakeFallback())
        await seed(
            store,
            "List temperature sensors",
            answer_with_devices(
                "fallback-device-type-temperature",
                "Temperature sensors",
                ["Bathroom Meter", "Hallway Meter"],
                device_type="temperature",
            ),
        )
        return await store.resolve(request("Which one is hottest?"))

    resolution = asyncio.run(scenario())
    assert resolution.reason == "context-comparison"
    assert resolution.answer["route"] == "mcp-context"
    assert resolution.answer["device_label"] == "Bathroom Meter"
    assert "24.2°C" in resolution.answer["message"]


def test_active_ones_reuses_previous_motion_device_type():
    async def scenario():
        store = ConversationContextStore(FakeIndex(), FakeFallback())
        await seed(
            store,
            "Show all motion sensors",
            answer_with_devices(
                "fallback-device-type-motion",
                "Motion sensors",
                ["Bedroom 1 FP300", "Hallway Motion"],
                device_type="motion",
            ),
        )
        return await store.resolve(request("Only active ones"))

    resolution = asyncio.run(scenario())
    assert resolution.query == "Which motion sensors are active?"
    assert resolution.answer is None
    assert resolution.reason == "context-active-motion"


def test_what_about_bathroom_reuses_previous_temperature_question():
    async def scenario():
        store = ConversationContextStore(FakeIndex(), FakeFallback())
        await seed(
            store,
            "List temperature sensors",
            answer_with_devices(
                "fallback-device-type-temperature",
                "Temperature sensors",
                ["Bathroom Meter", "Hallway Meter"],
                device_type="temperature",
            ),
        )
        return await store.resolve(request("What about the bathroom?"))

    resolution = asyncio.run(scenario())
    assert resolution.reason == "context-room-follow-up"
    assert resolution.answer["room"] == "Bathroom"
    assert resolution.answer["device_type"] == "temperature"
    assert resolution.answer["display"]["items"][0]["title"] == "Bathroom Meter"
    assert resolution.answer["display"]["items"][0]["value"] == "24.2°C"


def test_context_is_separate_per_browser_session_and_can_be_cleared():
    async def scenario():
        store = ConversationContextStore(FakeIndex(), FakeFallback())
        await seed(
            store,
            "Show Bedroom 2 Light",
            answer_with_devices(
                "fallback-device-status",
                "Bedroom 2 Light",
                ["Bedroom 2 Light"],
                device_label="Bedroom 2 Light",
            ),
        )
        other = await store.resolve(request("turn it off", session_id="browser-2"))
        removed = await store.clear("browser-1")
        diagnostics = await store.diagnostics("browser-1")
        return other, removed, diagnostics

    other, removed, diagnostics = asyncio.run(scenario())
    assert other.answer is None
    assert other.query == "turn it off"
    assert removed is True
    assert diagnostics["active"] is False
