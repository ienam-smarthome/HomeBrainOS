from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_capability_filter import install_control_graph_capability_filter  # noqa: E402
from control_agent_rescue import RescueControlAgent  # noqa: E402


def device(device_id: str, label: str, room: str, states: dict[str, Any]):
    return {
        "id": device_id,
        "name": label,
        "label": label,
        "room": room,
        "disabled": False,
        "currentStates": states,
    }


DEVICES = [
    device("7057", "Bedroom 1 Light", "Bedroom 1", {"switch": "off"}),
    device("7026", "Bedroom 2 Light", "Bedroom 2", {"switch": "off"}),
    device("7058", "Bedroom 3 Light", "Bedroom 3", {"switch": "off"}),
    device("7381", "FP2 Bedroom 3 Lux", "Bedroom 3", {}),
]


class FakeIndex:
    async def summary_devices(self, force: bool = False):
        return list(DEVICES)


class FakeFallback:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.client = SimpleNamespace()

    async def _control_device(self, label: str, action: str):
        self.calls.append((label, action))
        raise AssertionError("A read-only sensor guard must send no command")


class FakeApplication:
    def __init__(self) -> None:
        self.ollama = SimpleNamespace()

    @staticmethod
    def option_bool(name: str, default: bool = False) -> bool:
        if name in {
            "control_agent_enabled",
            "control_agent_ai_rescue_enabled",
            "ollama_enabled",
        }:
            return True
        return default


def request(query: str):
    return SimpleNamespace(query=query, session_id="lux-guard", history=[])


async def unused(_request: Any):
    raise AssertionError("The legacy or Cloud planner must not receive an exact sensor target")


def make_agent(tmp_path: Path):
    install_control_graph_capability_filter()
    fallback = FakeFallback()
    agent = RescueControlAgent(
        FakeApplication(),
        FakeIndex(),
        fallback,
        alias_path=str(tmp_path / "aliases.json"),
    )
    return agent, fallback


def test_exact_lux_sensor_returns_read_only_explanation_without_choices_or_ai(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)
    ai_calls = 0

    async def forbidden_ai(*_args: Any, **_kwargs: Any):
        nonlocal ai_calls
        ai_calls += 1
        raise AssertionError("Exact read-only targets must be stopped before AI rescue")

    agent.interpreter._interpret_with_ai = forbidden_ai
    answer = asyncio.run(
        agent.answer(request("Turn off FP2 Bedroom 3 Lux."), unused)
    )

    assert answer["success"] is False
    assert answer["route"] == "control-agent"
    assert answer["intent"] == "control-agent-device-not-controllable"
    assert answer["confirmation_required"] is False
    assert answer["alternatives"] == []
    assert answer["model"] is None
    assert answer["answered_by"] == "Deterministic Control Agent capability guard"
    assert "FP2 Bedroom 3 Lux is an illuminance (Lux) sensor" in answer["message"]
    assert "cannot be turned off" in answer["message"]
    assert "did not substitute a different actuator" in answer["message"]
    assert "Bedroom 1 Light" not in answer["message"]
    assert "AI rescue" not in answer["technical"]
    assert '"ai_rescue_attempted": false' in answer["technical"].lower()
    assert ai_calls == 0
    assert fallback.calls == []

    pending = asyncio.run(agent.pending.get("lux-guard"))
    assert pending is None


def test_exact_read_only_guard_uses_canonical_spoken_name_matching(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    answer = asyncio.run(
        agent.answer(request("turn off fp2-bedroom-3-lux"), unused)
    )

    assert answer["intent"] == "control-agent-device-not-controllable"
    assert "FP2 Bedroom 3 Lux" in answer["message"]
    assert answer["alternatives"] == []
    assert fallback.calls == []


def test_unknown_similar_target_is_not_misclassified_as_exact_sensor(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def no_rescue(*_args: Any, **_kwargs: Any):
        return None, {"ai_used": False}

    agent.interpreter._interpret_with_ai = no_rescue
    answer = asyncio.run(
        agent.answer(request("Turn off FP2 Bedroom Lux."), unused)
    )

    assert answer["intent"] != "control-agent-device-not-controllable"
    assert fallback.calls == []
