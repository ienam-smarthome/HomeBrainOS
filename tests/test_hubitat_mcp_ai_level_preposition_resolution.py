from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_rescue import RescueControlAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def result(data: Any) -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={},
        text="",
        data=data,
        is_error=False,
    )


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
    device("7057", "Bedroom 1 Light", "Bedroom 1", {"switch": "on", "level": 80}),
    device("7026", "Bedroom 2 Light", "Bedroom 2", {"switch": "off", "level": 100}),
    device("7058", "Bedroom 3 Light", "Bedroom 3", {"switch": "off", "level": 100}),
    device("7044", "Big lamp", "Bedroom 3", {"switch": "off", "level": 100}),
    device("7028", "My Floor Lamp", "Bedroom 1", {"switch": "off", "level": 100}),
]


class FakeApplication:
    ollama = SimpleNamespace()

    @staticmethod
    def option_bool(name: str, default: bool = False) -> bool:
        if name in {"control_agent_ai_rescue_enabled", "ollama_enabled"}:
            return True
        return default


class FakeIndex:
    async def summary_devices(self, force: bool = False):
        return list(DEVICES)


class FakeFallback:
    def __init__(self) -> None:
        self.client = SimpleNamespace()

    async def _direct_fresh_devices(self, capability: str | None = None, detailed: bool = False):
        assert capability == "Switch"
        assert detailed is False
        return result({"devices": DEVICES})

    @staticmethod
    def _device_rows(value: Any):
        if isinstance(value, dict):
            value = value.get("devices") or []
        return [item for item in value if isinstance(item, dict)]

    async def _control_device(self, label: str, action: str):
        raise AssertionError("The absolute level request must not become an on/off command")


async def forbidden_original(_request: Any):
    raise AssertionError("A clear exact level command must not reach the legacy planner")


def request(query: str):
    return SimpleNamespace(query=query, session_id="level-at-test", history=[])


def test_clear_set_at_level_resolves_exactly_without_choice_or_ai(tmp_path: Path):
    install_combined_level_intent()
    agent = RescueControlAgent(
        FakeApplication(),
        FakeIndex(),
        FakeFallback(),
        alias_path=str(tmp_path / "aliases.json"),
        intent_timeout_seconds=1,
    )
    executed: list[tuple[str, float]] = []

    async def verified_level(_self, node, value: float):
        executed.append((node.label, value))
        return {
            "success": True,
            "intent": "control-agent-level-confirmed",
            "message": f"{node.label} is confirmed at {value:g}%.",
            "tools_used": [{"name": "hub_call_device_command", "success": True}],
        }

    async def forbidden_rescue(_self, _query, **_kwargs):
        raise AssertionError("AI rescue must not run for a correctly parsed exact target")

    agent._set_level = MethodType(verified_level, agent)
    agent.interpreter._interpret_with_ai = MethodType(forbidden_rescue, agent.interpreter)

    answer = asyncio.run(
        agent.answer(request("set Bedroom 1 Light at 30%"), forbidden_original)
    )

    assert answer["success"] is True
    assert answer["route"] == "control-agent+mcp"
    assert executed == [("Bedroom 1 Light", 30.0)]
    assert answer["control_intent"]["actions"][0]["target"]["name_hint"] == "Bedroom 1 Light"
    assert answer["control_intent"]["actions"][0]["value"] == 30
    assert "confirmation_required" not in answer
    assert "alternatives" not in answer
    assert "control_ai_rescue" not in answer
    assert answer["answered_by"] == "Deterministic Control Agent + verified Hubitat MCP"
