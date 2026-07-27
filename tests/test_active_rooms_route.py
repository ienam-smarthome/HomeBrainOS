from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from active_rooms_route import build_active_rooms_terminal_route, is_active_rooms_query


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


class Snapshot:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def get(self, force=False):
        self.calls.append(force)
        return dict(self.value)


def test_active_rooms_query_matches_dashboard_wording():
    assert is_active_rooms_query("Which rooms are active based on motion or lights?")
    assert is_active_rooms_query("What rooms are active?")
    assert not is_active_rooms_query("Turn off the active room lights")


def test_active_rooms_route_answers_without_ai_or_mcp_calls():
    snapshot = Snapshot(
        {
            "success": True,
            "active_rooms": 2,
            "active_room_names": ["Bedroom 2", "Living Room"],
            "active_room_details": [
                {"room": "Bedroom 2", "motion_active": True},
                {"room": "Living Room", "lights_on": 2},
            ],
        }
    )
    route = build_active_rooms_terminal_route(
        SimpleNamespace(VERSION="0.10.184"),
        snapshot,
    )

    answer = asyncio.run(
        route(SimpleNamespace(query="Which rooms are active based on motion or lights?"))
    )

    assert answer["route"] == "mcp-dashboard-active-rooms"
    assert answer["model"] is None
    assert answer["selected_tools"] == []
    assert answer["active_room_names"] == ["Bedroom 2", "Living Room"]
    assert answer["message"] == "The active rooms are Bedroom 2 and Living Room."
    assert snapshot.calls == [False]


def test_active_rooms_route_falls_through_for_unrelated_query():
    snapshot = Snapshot({"success": True})
    route = build_active_rooms_terminal_route(SimpleNamespace(VERSION="test"), snapshot)

    answer = asyncio.run(route(SimpleNamespace(query="What is the thermostat setpoint?")))

    assert answer is None
    assert snapshot.calls == []


def test_active_rooms_route_is_first_in_read_execution_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    active = source.index('read_execution_registry.register_terminal_route(\n    "active-rooms"')
    health = source.index('read_execution_registry.register_terminal_route(\n    "device-health-fast-route"')
    octopus = source.index('read_execution_registry.register_terminal_route(\n    "control-focus-octopus-energy"')

    assert active < health < octopus
    assert "_core.dashboard_snapshot" in source
