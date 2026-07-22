from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent import HomeBrainControlAgent  # noqa: E402
from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_postfix_control import install_postfix_control_intent  # noqa: E402
from control_postfix_language import parse_postfix_control  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


def result(data: Any) -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={"isError": False},
        text="",
        data=data,
        is_error=False,
    )


def device(device_id: str, label: str, room: str) -> dict[str, Any]:
    return {
        "id": device_id,
        "name": label,
        "label": label,
        "room": room,
        "disabled": False,
        "currentStates": {"switch": "on"},
    }


DEVICES = [
    device("1", "Livingroom Light 1", "Living Room"),
    device("2", "Livingroom Light 2", "Living Room"),
    device("3", "Bedroom 1 Light", "Bedroom 1"),
]


class FakeIndex:
    async def summary_devices(self, force: bool = False):
        return list(DEVICES)

    async def capability_devices(self, capability: str, force: bool = False):
        return list(DEVICES) if capability == "Switch" else []


class FakeFallback:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.client = SimpleNamespace()

    async def _direct_fresh_devices(self, capability: str | None = None, detailed: bool = False):
        assert capability == "Switch"
        return result({"devices": list(DEVICES)})

    @staticmethod
    def _device_rows(value: Any):
        if isinstance(value, dict):
            value = value.get("devices") or []
        return [item for item in value if isinstance(item, dict)]

    async def _control_device(self, label: str, action: str):
        self.calls.append((label, action))
        return {
            "success": True,
            "intent": "fallback-device-control-confirmed",
            "message": f"{label} is confirmed {action}.",
            "tools_used": [
                {"name": "hub_call_device_command", "success": True},
                {"name": "hub_list_devices", "success": True},
            ],
        }


class FakeApplication:
    ollama = SimpleNamespace()

    @staticmethod
    def option_bool(name: str, default: bool = False) -> bool:
        return False if name == "ollama_enabled" else default


def request(query: str):
    return SimpleNamespace(query=query, session_id="postfix-control", history=[])


async def unused(_request: Any):
    raise AssertionError("The Cloud/legacy planner must not receive a resolved postfix control")


def install_language() -> None:
    install_combined_level_intent()
    install_postfix_control_intent()


def test_postfix_parser_extracts_room_type_and_ordinal():
    parsed = parse_postfix_control("Switch the second living-room light off.")

    assert parsed is not None
    assert parsed.action == "off"
    assert parsed.name_hint == ""
    assert parsed.room_hint == "Living Room"
    assert parsed.device_type == "light"
    assert parsed.ordinal == 2


def test_postfix_ordinal_control_is_classified_mcp_fast():
    decision = classify_query("Switch the second living-room light off.")

    assert decision.route == "mcp-fast"
    assert "ordinal" in decision.reason


def test_exact_target_before_action_is_also_deterministic():
    parsed = parse_postfix_control("Switch Bedroom 1 Light off")

    assert parsed is not None
    assert parsed.action == "off"
    assert parsed.name_hint == "Bedroom 1 Light"
    assert parsed.ordinal is None


def test_context_and_group_postfix_phrases_are_not_flattened_to_one_device():
    assert parse_postfix_control("Turn the other light off") is None
    assert parse_postfix_control("Turn all living room lights off") is None


def test_second_living_room_light_executes_once_without_ai_or_choice(tmp_path: Path):
    install_language()
    fallback = FakeFallback()
    agent = HomeBrainControlAgent(
        FakeApplication(),
        FakeIndex(),
        fallback,
        alias_path=str(tmp_path / "aliases.json"),
    )

    answer = asyncio.run(
        agent.answer(request("Switch the second living-room light off."), unused)
    )

    assert answer["success"] is True
    assert answer["route"] == "control-agent+mcp"
    assert answer["answered_by"] == "Deterministic Control Agent + verified Hubitat MCP"
    assert answer.get("model") is None
    assert answer.get("confirmation_required") is not True
    assert fallback.calls == [("Livingroom Light 2", "off")]

    intent = answer["control_intent"]
    target = intent["actions"][0]["target"]
    assert intent["interpreter"] == "deterministic-control-parser"
    assert target == {
        "name_hint": "",
        "room_hint": "Living Room",
        "device_type": "light",
        "ordinal": 2,
        "quantifier": "one",
        "reference": "none",
        "exclusions": [],
    }


def test_prefix_ordinal_wording_from_live_failure_executes_terminally(tmp_path: Path):
    install_language()
    fallback = FakeFallback()
    agent = HomeBrainControlAgent(
        FakeApplication(),
        FakeIndex(),
        fallback,
        alias_path=str(tmp_path / "aliases.json"),
    )

    answer = asyncio.run(
        agent.answer(request("Turn off the second living-room light"), unused)
    )

    assert answer["success"] is True
    assert answer["route"] == "control-agent+mcp"
    assert fallback.calls == [("Livingroom Light 2", "off")]
    assert any(
        item["name"] == "hub_call_device_command" and item["success"] is True
        for item in answer["tools_used"]
    )


def test_entrypoint_installs_postfix_parser_before_control_agent():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "from control_agent_postfix_control import install_postfix_control_intent" in entrypoint
    assert entrypoint.index("install_postfix_control_intent()") < entrypoint.index(
        "control_agent = install_control_agent("
    )
