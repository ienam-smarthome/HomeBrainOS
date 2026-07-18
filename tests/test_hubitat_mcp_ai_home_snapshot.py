from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from home_snapshot import HomeSnapshotService, install_home_snapshot  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


DEVICES = [
    {
        "id": "1",
        "label": "Bedroom 2 Light",
        "room": "Bedroom 2",
        "currentStates": {"switch": "on"},
        "capabilities": ["Switch", "Switch Level"],
    },
    {
        "id": "2",
        "label": "Bedroom1 (MQTT)",
        "room": "Bedroom 1",
        "currentStates": {"switch": "on"},
        "capabilities": ["Switch"],
    },
    {
        "id": "3",
        "label": "Cudy CAM-Camera-G100",
        "room": "Hallway",
        "currentStates": {"switch": "on", "status": "online"},
        "capabilities": ["Switch"],
    },
    {
        "id": "4",
        "label": "Bedroom 2 FP1",
        "room": "Bedroom 2",
        "currentStates": {"motion": "active"},
        "capabilities": ["Motion Sensor"],
    },
    {
        "id": "5",
        "label": "Bedroom 3 Presence Sensor",
        "room": "Bedroom 3",
        "currentStates": {"motion": "active"},
        "capabilities": ["Motion Sensor"],
    },
    {
        "id": "6",
        "label": "Livingroom TRV",
        "room": "Livingroom",
        "currentStates": {
            "battery": 12,
            "thermostatOperatingState": "heating",
            "heatingSetpoint": 21,
        },
        "capabilities": ["Battery", "Thermostat"],
    },
    {
        "id": "7",
        "label": "Fridge Door",
        "room": "Kitchen",
        "currentStates": {"battery": 17, "contact": "closed"},
        "capabilities": ["Battery", "Contact Sensor"],
    },
    {
        "id": "8",
        "label": "Front Door",
        "room": "Hallway",
        "currentStates": {"contact": "open", "battery": 80},
        "capabilities": ["Contact Sensor", "Battery"],
    },
]


class FakeIndex:
    async def enriched_devices(self):
        return [dict(item) for item in DEVICES]

    async def diagnostics(self):
        return {
            "selected_count": len(DEVICES),
            "last_refresh_age_seconds": 0.4,
            "rooms": ["Bedroom 1", "Bedroom 2", "Bedroom 3", "Hallway", "Kitchen", "Livingroom"],
        }

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        attrs = item.get("currentStates") or {}
        groups = set()
        label = str(item.get("label") or "").lower()
        if "switch" in attrs:
            groups.add("light" if "light" in label else "switch")
        for key in ("motion", "contact", "battery", "thermostatOperatingState"):
            if key in attrs:
                groups.add("thermostat" if key == "thermostatOperatingState" else key)
        return groups


class FakeMCP:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        if self.fail:
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="hub unavailable",
                data=None,
                is_error=True,
            )
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"safeMode": False, "healthAlerts": {"active": []}},
            is_error=False,
        )


class FakeOllama:
    model = "qwen3.5:9b"
    num_ctx = 4096

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    async def health(self):
        return {"online": True, "models": [self.model]}

    def _resolve_routine_model(self, installed):
        return self.model

    async def _chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("synthetic timeout")
        return {
            "message": {
                "content": (
                    "Two batteries need attention: Livingroom TRV is at 12% and Fridge Door is at 17%. "
                    "Motion is active in Bedroom 2 and Bedroom 3, while Bedroom 2 Light and Bedroom1 (MQTT) are on."
                )
            }
        }


class FakeApplication:
    VERSION = "0.4.1-alpha"

    def __init__(self, *, ollama_fail: bool = False, hub_fail: bool = False) -> None:
        self.mcp = FakeMCP(fail=hub_fail)
        self.ollama = FakeOllama(fail=ollama_fail)



def test_home_snapshot_is_structured_prioritised_and_exact():
    async def scenario():
        app = FakeApplication()
        service = HomeSnapshotService(app, FakeIndex(), ai_timeout_seconds=3)
        return app, await service.answer("What's happening at home?")

    app, answer = asyncio.run(scenario())

    assert answer["route"] == "ollama+snapshot"
    assert answer["intent"] == "home-snapshot"
    assert answer["display"]["title"] == "Home right now"
    assert answer["display"]["summary"] == answer["message"]
    assert [item["value"] for item in answer["display"]["metrics"]] == ["2", "1", "1", "2"]

    items = answer["display"]["items"]
    assert items[0]["group"] == "Needs attention"
    assert items[0]["title"] == "Livingroom TRV"
    assert items[0]["value"] == "12%"
    assert any(item["title"] == "Bedroom 2 FP1" and item["group"] == "Activity" for item in items)
    assert any(item["title"] == "Bedroom 2 Light" and item["group"] == "Lights on" for item in items)
    assert any(item["title"] == "Bedroom1 (MQTT)" and item["group"] == "Other devices on" for item in items)
    assert not any(item["title"] == "Cudy CAM-Camera-G100" for item in items)
    assert "1 always-on/background device" in answer["display"]["note"]

    assert len(app.ollama.calls) == 1
    assert app.ollama.calls[0]["tools"] is None
    assert app.ollama.calls[0]["num_predict"] == 100


def test_home_snapshot_falls_back_to_structured_mcp_answer_when_ai_fails():
    async def scenario():
        app = FakeApplication(ollama_fail=True)
        service = HomeSnapshotService(app, FakeIndex(), ai_timeout_seconds=3)
        return await service.answer("Home status")

    answer = asyncio.run(scenario())

    assert answer["route"] == "mcp-snapshot"
    assert answer["synthesis_error"] == "synthetic timeout"
    assert "Livingroom TRV 12%" in answer["message"]
    assert "Fridge Door 17%" in answer["message"]
    assert "Bedroom 2 FP1" in answer["message"]
    assert answer["display"]["metrics"][3]["value"] == "2"


def test_home_snapshot_marks_incomplete_hub_coverage_without_claiming_all_clear():
    async def scenario():
        app = FakeApplication(hub_fail=True)
        service = HomeSnapshotService(app, FakeIndex(), ai_enabled=False)
        return await service.answer("What's happening?")

    answer = asyncio.run(scenario())

    assert answer["coverage_complete"] is False
    assert "scan incomplete" in answer["display"]["subtitle"]
    assert "Incomplete sources: hub: hub unavailable" in answer["display"]["note"]
    assert answer["route"] == "mcp-snapshot"


def test_home_snapshot_wrapper_only_intercepts_home_summary_queries():
    async def scenario():
        app = FakeApplication()
        calls = []

        async def original(request):
            calls.append(request.query)
            return {"success": True, "route": "original", "message": "original"}

        app.ask = original
        install_home_snapshot(app, FakeIndex(), ai_enabled=False)
        home = await app.ask(SimpleNamespace(query="What's happening at home?"))
        weather = await app.ask(SimpleNamespace(query="What is the weather?"))
        return calls, home, weather

    calls, home, weather = asyncio.run(scenario())
    assert home["intent"] == "home-snapshot"
    assert weather["route"] == "original"
    assert calls == ["What is the weather?"]
