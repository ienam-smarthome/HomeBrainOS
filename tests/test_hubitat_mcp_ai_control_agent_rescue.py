from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_capability_filter import install_control_graph_capability_filter  # noqa: E402
from control_agent_intent import (  # noqa: E402
    ControlActionIntent,
    ControlIntent,
    ControlTargetIntent,
)
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
    device("701", "Livingroom Light 1", "Living Room", {"switch": "on"}),
    device("702", "Livingroom Light 2", "Living Room", {"switch": "on"}),
    device("703", "Bedroom 1 Light", "Bedroom 1", {"switch": "on", "level": 80}),
    device("704", "FP2 Bedroom 3 Lux", "Bedroom 3", {"illuminance": 12}),
]


class FakeApplication:
    def __init__(self, *, rescue_enabled: bool = True, ollama_enabled: bool = True) -> None:
        self.rescue_enabled = rescue_enabled
        self.ollama_enabled = ollama_enabled
        self.ollama = SimpleNamespace()

    def option_bool(self, name: str, default: bool = False) -> bool:
        if name == "control_agent_ai_rescue_enabled":
            return self.rescue_enabled
        if name == "ollama_enabled":
            return self.ollama_enabled
        return default


class FakeIndex:
    async def summary_devices(self, force: bool = False):
        return list(DEVICES)


class FakeFallback:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.client = SimpleNamespace()

    async def _direct_fresh_devices(self, capability: str | None = None, detailed: bool = False):
        assert capability == "Switch"
        return result({"devices": [item for item in DEVICES if "switch" in item["currentStates"]]})

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
            "tools_used": [{"name": "hub_call_device_command", "success": True}],
        }


def request(query: str):
    return SimpleNamespace(query=query, session_id="rescue-test", history=[])


async def forbidden_original(_request: Any):
    raise AssertionError("A supported control must not fall through to the legacy planner")


def malformed_intent() -> ControlIntent:
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command="off",
                value=None,
                target=ControlTargetIntent(name_hint="Living room light too please"),
            ),
        ),
        confidence=1.0,
        interpreter="deterministic-control-parser",
    )


def rescued_intent() -> ControlIntent:
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command="off",
                value=None,
                target=ControlTargetIntent(name_hint="Livingroom Light 2"),
            ),
        ),
        confidence=0.97,
        interpreter="local-ollama-control-intent",
        model="qwen3.5:4b",
    )


def make_agent(tmp_path: Path, *, rescue_enabled: bool = True):
    install_control_graph_capability_filter()
    app = FakeApplication(rescue_enabled=rescue_enabled)
    fallback = FakeFallback()
    agent = RescueControlAgent(
        app,
        FakeIndex(),
        fallback,
        alias_path=str(tmp_path / "aliases.json"),
        intent_timeout_seconds=2,
    )
    return agent, fallback


def test_failed_deterministic_resolution_gets_one_local_ai_rescue_and_executes_once(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)
    rescue_calls = 0

    async def interpret(_self, _query, **_kwargs):
        return malformed_intent(), {"interpreter": "deterministic-control-parser", "ai_used": False}

    async def rescue(_self, _query, **_kwargs):
        nonlocal rescue_calls
        rescue_calls += 1
        return rescued_intent(), {
            "ai_used": True,
            "ai_model": "qwen3.5:4b",
            "ai_provider": "Local Ollama control interpreter",
            "ai_success": True,
        }

    agent.interpreter.interpret = MethodType(interpret, agent.interpreter)
    agent.interpreter._interpret_with_ai = MethodType(rescue, agent.interpreter)

    answer = asyncio.run(
        agent.answer(request("turn off living room light too please"), forbidden_original)
    )

    assert answer["success"] is True
    assert fallback.calls == [("Livingroom Light 2", "off")]
    assert rescue_calls == 1
    assert answer["control_rescue_used"] is True
    assert answer["control_ai_rescue"]["accepted"] is True
    assert answer["control_intent"]["actions"][0]["target"]["name_hint"] == "Livingroom Light 2"
    assert answer["model"] == "qwen3.5:4b"
    assert answer["answered_by"] == "Local AI intent + deterministic verified Hubitat MCP"


def test_exact_resolved_control_stays_fast_and_never_calls_ai_rescue(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def forbidden_rescue(_self, _query, **_kwargs):
        raise AssertionError("AI rescue must not run for an exact resolved control")

    agent.interpreter._interpret_with_ai = MethodType(forbidden_rescue, agent.interpreter)

    answer = asyncio.run(
        agent.answer(request("turn off Bedroom 1 Light"), forbidden_original)
    )

    assert answer["success"] is True
    assert fallback.calls == [("Bedroom 1 Light", "off")]
    assert "control_ai_rescue" not in answer
    assert answer["answered_by"] == "Deterministic Control Agent + verified Hubitat MCP"


def test_unimproved_ai_rescue_does_not_write_or_override_original_clarification(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def interpret(_self, _query, **_kwargs):
        return malformed_intent(), {"interpreter": "deterministic-control-parser", "ai_used": False}

    async def unchanged(_self, _query, **_kwargs):
        return malformed_intent(), {
            "ai_used": True,
            "ai_model": "qwen3.5:4b",
            "ai_success": True,
        }

    agent.interpreter.interpret = MethodType(interpret, agent.interpreter)
    agent.interpreter._interpret_with_ai = MethodType(unchanged, agent.interpreter)

    answer = asyncio.run(
        agent.answer(request("turn off living room light too please"), forbidden_original)
    )

    assert answer["success"] is False
    assert fallback.calls == []
    assert answer["confirmation_required"] is True
    assert answer["control_ai_rescue"]["attempted"] is True
    assert answer["control_ai_rescue"]["accepted"] is False
    assert "FP2 Bedroom 3 Lux" not in answer["alternatives"]


def test_rescue_can_be_disabled_without_affecting_safe_clarification(tmp_path: Path):
    agent, fallback = make_agent(tmp_path, rescue_enabled=False)

    async def interpret(_self, _query, **_kwargs):
        return malformed_intent(), {"interpreter": "deterministic-control-parser", "ai_used": False}

    async def forbidden_rescue(_self, _query, **_kwargs):
        raise AssertionError("Disabled AI rescue must not call the model")

    agent.interpreter.interpret = MethodType(interpret, agent.interpreter)
    agent.interpreter._interpret_with_ai = MethodType(forbidden_rescue, agent.interpreter)

    answer = asyncio.run(
        agent.answer(request("turn off living room light too please"), forbidden_original)
    )

    assert answer["success"] is False
    assert fallback.calls == []
    assert answer["control_ai_rescue"]["attempted"] is False
    assert "disabled" in answer["control_ai_rescue"]["reason"].lower()


def test_release_wires_rescue_agent_and_capability_filtered_graph():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "from control_agent_rescue import install_control_agent" in entrypoint
    assert "control_agent_ai_rescue_enabled: true" in config
    assert "install_control_graph_capability_filter()" in (
        APP_DIR / "control_agent_combined_level.py"
    ).read_text(encoding="utf-8")
