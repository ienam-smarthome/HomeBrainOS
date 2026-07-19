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
from control_agent_graph import ControlDeviceGraph, GraphContext  # noqa: E402
from control_agent_intent import (  # noqa: E402
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
)
from mcp_client import MCPToolResult  # noqa: E402


def result(data: Any, *, error: bool = False, text: str = "") -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={"isError": error},
        text=text,
        data=data,
        is_error=error,
    )


def device(
    device_id: str,
    label: str,
    room: str,
    *,
    switch: str = "off",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    states = {"switch": switch}
    states.update(extra or {})
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "disabled": False,
        "currentStates": states,
    }


DEVICES = [
    device("1", "Livingroom Light 1", "Living Room"),
    device("2", "Livingroom Light 2", "Living Room"),
    device("3", "Bedroom 1 Light", "Bedroom 1"),
    device("4", "My Floor Lamp", "Bedroom 1"),
    device("5", "Bedroom 2 Light", "Bedroom 2"),
    device("6", "Front Door Lock", "Hallway", extra={"lock": "locked"}),
    device("7", "Standing Fan", "Living Room"),
]


class FakeIndex:
    def __init__(self, devices: list[dict[str, Any]] | None = None) -> None:
        self.devices = list(devices or DEVICES)

    async def summary_devices(self, force: bool = False):
        return list(self.devices)

    async def capability_devices(self, capability: str, force: bool = False):
        if capability == "Switch":
            return list(self.devices)
        return []


class FakeFallback:
    def __init__(self, devices: list[dict[str, Any]] | None = None) -> None:
        self.devices = list(devices or DEVICES)
        self.calls: list[tuple[str, str]] = []
        self.control_verification_timeout_seconds = 2
        self.control_verification_initial_delay_seconds = 0.05
        self.client = SimpleNamespace()

    async def _direct_fresh_devices(self, capability: str | None = None, detailed: bool = False):
        return result({"devices": list(self.devices)})

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
    def __init__(self, *, ollama_enabled: bool = False) -> None:
        self.ollama_enabled = ollama_enabled
        self.ollama = SimpleNamespace()

    def option_bool(self, name: str, default: bool = False) -> bool:
        if name == "ollama_enabled":
            return self.ollama_enabled
        return default


def request(query: str, session_id: str = "test") -> Any:
    return SimpleNamespace(query=query, session_id=session_id, history=[])


def intent(
    command: str,
    *,
    name: str = "",
    room: str = "",
    device_type: str = "",
    ordinal: int | None = None,
    quantifier: str = "one",
    reference: str = "none",
    exclusions: tuple[str, ...] = (),
    confidence: float = 0.97,
    model: str | None = "qwen3.5:4b",
) -> ControlIntent:
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command=command,
                value=None,
                target=ControlTargetIntent(
                    name_hint=name,
                    room_hint=room,
                    device_type=device_type,
                    ordinal=ordinal,
                    quantifier=quantifier,
                    reference=reference,
                    exclusions=exclusions,
                ),
            ),
        ),
        confidence=confidence,
        interpreter="local-ollama-control-intent" if model else "deterministic-control-parser",
        model=model,
    )


def make_agent(tmp_path: Path, devices: list[dict[str, Any]] | None = None):
    application = FakeApplication()
    index = FakeIndex(devices)
    fallback = FakeFallback(devices)
    agent = HomeBrainControlAgent(
        application,
        index,
        fallback,
        alias_path=str(tmp_path / "aliases.json"),
        auto_execute_confidence=0.88,
        block_below_confidence=0.50,
        group_confirmation_size=6,
    )
    return agent, fallback


def test_graph_resolves_real_spoken_typo_to_one_exact_selected_label():
    graph = ControlDeviceGraph(DEVICES)

    resolution = graph.resolve(ControlTargetIntent(name_hint="liiving room light two"))

    assert resolution.resolved is True
    assert [item.label for item in resolution.nodes] == ["Livingroom Light 2"]
    assert resolution.method == "unique-alias"
    assert resolution.confidence == 1.0


def test_graph_resolves_room_type_and_ordinal_without_label_guessing():
    graph = ControlDeviceGraph(DEVICES)

    resolution = graph.resolve(
        ControlTargetIntent(
            room_hint="Living Room",
            device_type="light",
            ordinal=2,
        )
    )

    assert [item.id for item in resolution.nodes] == ["2"]
    assert resolution.method == "room-type-ordinal"


def test_graph_resolves_all_bedroom_lights_and_excludes_floor_lamp():
    graph = ControlDeviceGraph(DEVICES)

    resolution = graph.resolve(
        ControlTargetIntent(
            room_hint="Bedroom",
            device_type="lights",
            quantifier="all",
            exclusions=("floor lamp",),
        )
    )

    assert [item.label for item in resolution.nodes] == [
        "Bedroom 1 Light",
        "Bedroom 2 Light",
    ]


def test_graph_uses_structured_other_reference_without_ai_guessing():
    graph = ControlDeviceGraph(DEVICES)

    resolution = graph.resolve(
        ControlTargetIntent(reference="other"),
        context=GraphContext(
            last_device_ids=("2",),
            last_candidate_ids=("1", "2"),
        ),
    )

    assert [item.id for item in resolution.nodes] == ["1"]
    assert resolution.method == "context-other"


def test_simple_exact_command_stays_deterministic_and_fast():
    interpreter = ControlIntentInterpreter(FakeApplication())

    parsed = interpreter._deterministic_intent("turn off Livingroom Light 2")

    assert parsed is not None
    assert parsed.model is None
    assert parsed.actions[0].command == "off"
    assert parsed.actions[0].target.name_hint == "Livingroom Light 2"


def test_group_context_and_ordinal_commands_are_reserved_for_structured_ai():
    interpreter = ControlIntentInterpreter(FakeApplication())

    assert interpreter._deterministic_intent(
        "turn off all bedroom lights except the floor lamp"
    ) is None
    assert interpreter._deterministic_intent("turn off the other one") is None
    assert interpreter._deterministic_intent("switch the second lounge light off") is None


def test_control_intent_validation_rejects_unsupported_command():
    payload = {
        "intent": "device_control",
        "actions": [
            {
                "command": "unlock",
                "value": None,
                "target": {
                    "name_hint": "front door",
                    "room_hint": "",
                    "device_type": "lock",
                    "ordinal": None,
                    "quantifier": "one",
                    "reference": "none",
                    "exclusions": [],
                },
            }
        ],
        "confidence": 0.99,
    }

    assert ControlIntentInterpreter.validate_payload(payload, model="qwen3.5:4b") is None


def test_exact_control_executes_verified_fallback_without_cloud(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)
    original_calls = 0

    async def original(_request: Any):
        nonlocal original_calls
        original_calls += 1
        return {"success": False, "message": "should not be used"}

    answer = asyncio.run(
        agent.answer(request("turn off liiving room light two"), original)
    )

    assert original_calls == 0
    assert fallback.calls == [("Livingroom Light 2", "off")]
    assert answer["success"] is True
    assert answer["route"] == "control-agent+mcp"
    assert answer["intent"] == "control-agent-confirmed"
    assert answer["answered_by"] == "Deterministic Control Agent + verified Hubitat MCP"


def test_ambiguous_control_sends_no_command_and_accepts_numbered_follow_up(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def original(_request: Any):
        return {"success": False, "message": "unused"}

    first = asyncio.run(agent.answer(request("turn off livingroom light"), original))

    assert first["success"] is False
    assert first["intent"] == "control-agent-device-choice-required"
    assert fallback.calls == []
    assert first["alternatives"] == ["Livingroom Light 1", "Livingroom Light 2"]

    second = asyncio.run(agent.answer(request("2"), original))

    assert second["success"] is True
    assert fallback.calls == [("Livingroom Light 2", "off")]


def test_local_ai_group_intent_resolves_all_targets_before_first_write(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def interpret(*_args: Any, **_kwargs: Any):
        return (
            intent(
                "off",
                room="Bedroom",
                device_type="light",
                quantifier="all",
                exclusions=("floor lamp",),
            ),
            {"ai_used": True, "ai_model": "qwen3.5:4b"},
        )

    agent.interpreter.interpret = interpret

    async def original(_request: Any):
        raise AssertionError("The Cloud planner must not receive a validated control intent")

    answer = asyncio.run(
        agent.answer(
            request("turn off all bedroom lights except the floor lamp"),
            original,
        )
    )

    assert answer["success"] is True
    assert fallback.calls == [
        ("Bedroom 1 Light", "off"),
        ("Bedroom 2 Light", "off"),
    ]
    assert answer["model"] == "qwen3.5:4b"
    assert answer["answered_by"] == "Local AI intent + deterministic verified Hubitat MCP"


def test_structured_context_supports_turn_it_back_on(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def original(_request: Any):
        raise AssertionError("No legacy route expected")

    first = asyncio.run(agent.answer(request("turn off Livingroom Light 2"), original))
    assert first["success"] is True

    async def interpret(*_args: Any, **_kwargs: Any):
        return intent("on", reference="last"), {
            "ai_used": True,
            "ai_model": "qwen3.5:4b",
        }

    agent.interpreter.interpret = interpret
    second = asyncio.run(agent.answer(request("turn it back on"), original))

    assert second["success"] is True
    assert fallback.calls == [
        ("Livingroom Light 2", "off"),
        ("Livingroom Light 2", "on"),
    ]


def test_sensitive_device_requires_confirmation_and_no_write(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def original(_request: Any):
        raise AssertionError("No legacy route expected")

    answer = asyncio.run(agent.answer(request("turn off Front Door Lock"), original))

    assert answer["success"] is False
    assert answer["intent"] == "control-agent-confirmation-required"
    assert fallback.calls == []
    assert "Sensitive" in str(answer["display"])


def test_explicit_learned_alias_is_persistent_and_removable(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    async def original(_request: Any):
        return {"success": False, "message": "unused"}

    saved = asyncio.run(
        agent.answer(
            request('remember "big light" means "My Floor Lamp"'),
            original,
        )
    )
    assert saved["success"] is True
    assert "Remembered" in saved["message"]

    controlled = asyncio.run(agent.answer(request("turn off big light"), original))
    assert controlled["success"] is True
    assert fallback.calls == [("My Floor Lamp", "off")]

    forgotten = asyncio.run(agent.answer(request("forget alias big light"), original))
    assert forgotten["success"] is True


def test_preflight_blocks_removed_device_before_any_write(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)
    fallback.devices = [item for item in DEVICES if item["id"] != "2"]

    async def original(_request: Any):
        raise AssertionError("No legacy route expected")

    answer = asyncio.run(agent.answer(request("turn off Livingroom Light 2"), original))

    assert answer["success"] is False
    assert answer["intent"] == "control-agent-preflight-blocked"
    assert fallback.calls == []


def test_release_wires_control_agent_v1():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "from control_agent import install_control_agent" in entrypoint
    assert "control_agent = install_control_agent(" in entrypoint
    assert 'RELEASE_VERSION = "0.5.0"' in entrypoint
    assert 'version: "0.5.0"' in config
    assert "control_agent_enabled: true" in config
