from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_graph import ControlDeviceGraph  # noqa: E402
from control_agent_intent import ControlIntentInterpreter  # noqa: E402
from control_agent_semantic_target import decompose_natural_target  # noqa: E402


class NoAIApplication:
    OPTIONS: dict[str, Any] = {}

    def __init__(self) -> None:
        self.calls = 0
        self.ollama = SimpleNamespace()

    @staticmethod
    def option_bool(_name: str, default: bool = False) -> bool:
        return default


def light(device_id: str, label: str, room: str, level: int = 80) -> dict[str, Any]:
    return {
        "id": device_id,
        "name": label,
        "label": label,
        "room": room,
        "disabled": False,
        "currentStates": {"switch": "on", "level": level},
    }


def test_living_room_one_light_is_room_type_ordinal_not_literal_name():
    target = decompose_natural_target("living room one light")

    assert target.name_hint == ""
    assert target.room_hint == "Living Room"
    assert target.device_type == "light"
    assert target.ordinal == 1


def test_living_room_light_two_alternate_order_is_structured():
    target = decompose_natural_target("living room light two")

    assert target.room_hint == "Living Room"
    assert target.device_type == "light"
    assert target.ordinal == 2


def test_bedroom_one_light_is_canonical_numbered_room_device():
    target = decompose_natural_target("bedroom one light")

    assert target.name_hint == "Bedroom 1 Light"
    assert target.room_hint == "Bedroom 1"
    assert target.device_type == "light"
    assert target.ordinal is None


def test_reported_phrase_resolves_livingroom_light_one_without_ai_or_choices():
    install_combined_level_intent()
    application = NoAIApplication()
    interpreter = ControlIntentInterpreter(application)

    intent, diagnostics = asyncio.run(
        interpreter.interpret(
            "Put living room one light at about thirty percent.",
            history=[],
            context={},
            inventory=(
                "Livingroom Light 1 | Living Room | device,light\n"
                "Livingroom Light 2 | Living Room | device,light"
            ),
        )
    )

    assert intent is not None
    assert diagnostics["ai_used"] is False
    assert intent.model is None
    assert intent.interpreter == "deterministic-semantic-control-parser"
    action = intent.actions[0]
    assert action.command == "set_level"
    assert action.value == 30
    assert action.target.room_hint == "Living Room"
    assert action.target.device_type == "light"
    assert action.target.ordinal == 1

    graph = ControlDeviceGraph(
        [
            light("7027", "Livingroom Light 1", "Living Room"),
            light("7045", "Livingroom Light 2", "Living Room"),
        ]
    )
    resolution = graph.resolve(action.target)

    assert resolution.resolved is True
    assert [node.id for node in resolution.nodes] == ["7027"]
    assert resolution.method == "room-type-ordinal"
    assert resolution.candidates[0].label == "Livingroom Light 1"


def test_second_living_room_light_resolves_uniquely_too():
    install_combined_level_intent()
    interpreter = ControlIntentInterpreter(NoAIApplication())
    intent, diagnostics = asyncio.run(
        interpreter.interpret(
            "Put living room light two at about forty percent.",
            history=[],
            context={},
            inventory="",
        )
    )

    assert intent is not None
    assert diagnostics["ai_used"] is False
    action = intent.actions[0]
    graph = ControlDeviceGraph(
        [
            light("7027", "Livingroom Light 1", "Living Room"),
            light("7045", "Livingroom Light 2", "Living Room"),
        ]
    )
    resolution = graph.resolve(action.target)

    assert action.value == 40
    assert [node.id for node in resolution.nodes] == ["7045"]
