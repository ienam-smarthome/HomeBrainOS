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


def result(data: Any, *, name: str = "hub_list_devices", error: bool = False, text: str = ""):
    return MCPToolResult(
        name=name,
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
):
    states = {"switch": switch, **(extra or {})}
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
    device("2", "Livingroom Light 2", "Living Room", extra={"level": 10}),
    device("3", "Bedroom 1 Light", "Bedroom 1"),
    device("4", "My Floor Lamp", "Bedroom 1"),
    device("5", "Bedroom 2 Light", "Bedroom 2"),
    device("6", "Front Door Lock", "Hallway", extra={"lock": "locked"}),
    device("7", "Standing Fan", "Living Room"),
]


class FakeIndex:
    def __init__(self, devices: list[dict[str, Any]] | None = None):
        self.devices = list(devices or DEVICES)

    async def summary_devices(self, force: bool = False):
        return list(self.devices)

    async def capability_devices(self, capability: str, force: bool = False):
        return list(self.devices) if capability == "Switch" else []


class FakeCommandClient:
    def __init__(self, fallback: "FakeFallback"):
        self.fallback = fallback

    async def get_tool(self, name: str):
        assert name == "hub_call_device_command"
        return SimpleNamespace(
            input_schema={
                "properties": {
                    "deviceId": {},
                    "command": {},
                    "params": {},
                }
            }
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        assert name == "hub_call_device_command"
        self.fallback.raw_commands.append(dict(arguments))
        if arguments.get("command") == "setLevel":
            self.fallback.levels[str(arguments["deviceId"])] = float(arguments["params"][0])
        return result({"success": True}, name=name)

    async def invalidate(self, category: str):
        self.fallback.invalidations.append(category)
        return 1


class FakeFallback:
    def __init__(self, devices: list[dict[str, Any]] | None = None):
        self.devices = list(devices or DEVICES)
        self.calls: list[tuple[str, str]] = []
        self.raw_commands: list[dict[str, Any]] = []
        self.invalidations: list[str] = []
        self.levels = {"2": 10.0}
        self.control_verification_timeout_seconds = 2
        self.control_verification_initial_delay_seconds = 0.01
        self.client = FakeCommandClient(self)

    async def _direct_fresh_devices(self, capability: str | None = None, detailed: bool = False):
        rows = []
        for original in self.devices:
            item = dict(original)
            states = dict(item.get("currentStates") or {})
            device_id = str(item.get("id") or "")
            if device_id in self.levels:
                states["level"] = self.levels[device_id]
            item["currentStates"] = states
            rows.append(item)
        return result({"devices": rows})

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
    def __init__(self, *, ollama_enabled: bool = False):
        self.ollama_enabled = ollama_enabled
        self.ollama = SimpleNamespace()

    def option_bool(self, name: str, default: bool = False):
        return self.ollama_enabled if name == "ollama_enabled" else default


def request(query: str, session_id: str = "test"):
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
    value: float | None = None,
    confidence: float = 0.97,
    model: str | None = "qwen3.5:4b",
):
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command=command,
                value=value,
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


async def unused(_request: Any):
    raise AssertionError("The legacy/Cloud route must not receive a resolved Control Agent plan")


def test_graph_resolves_spoken_typo_room_type_ordinal_and_other_reference():
    graph = ControlDeviceGraph(DEVICES)

    typo = graph.resolve(ControlTargetIntent(name_hint="liiving room light two"))
    ordinal = graph.resolve(
        ControlTargetIntent(room_hint="Living Room", device_type="light", ordinal=2)
    )
    other = graph.resolve(
        ControlTargetIntent(reference="other"),
        context=GraphContext(last_device_ids=("2",), last_candidate_ids=("1", "2")),
    )

    assert [item.id for item in typo.nodes] == ["2"]
    assert typo.method == "unique-alias"
    assert [item.id for item in ordinal.nodes] == ["2"]
    assert ordinal.method == "room-type-ordinal"
    assert [item.id for item in other.nodes] == ["1"]
    assert other.method == "context-other"


def test_graph_resolves_group_with_exclusion_before_execution():
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


def test_plural_room_lights_expand_to_group_but_singular_stays_ambiguous(tmp_path: Path):
    devices = [
        device("7046", "Hallway Light 1", "Hallway"),
        device("7037", "Hallway Light 2", "Hallway"),
    ]
    agent, fallback = make_agent(tmp_path, devices)

    plural = asyncio.run(agent.answer(request("turn on hallway lights"), unused))

    assert plural["success"] is True
    assert fallback.calls == [
        ("Hallway Light 1", "on"),
        ("Hallway Light 2", "on"),
    ]
    target = plural["control_plan"]["actions"][0]["target"]
    assert target == {
        "name_hint": "",
        "room_hint": "hallway",
        "device_type": "light",
        "ordinal": None,
        "quantifier": "all",
        "reference": "none",
        "exclusions": [],
    }
    assert plural["control_plan"]["actions"][0]["resolution_method"] == "room-type-group"

    singular_agent, singular_fallback = make_agent(tmp_path / "singular", devices)
    singular = asyncio.run(singular_agent.answer(request("turn on hallway light"), unused))

    assert singular["intent"] == "control-agent-device-choice-required"
    assert singular_fallback.calls == []


def test_exact_plural_device_alias_wins_over_room_group_inference():
    graph = ControlDeviceGraph(
        [
            device("10", "Christmas Lights", "Living Room"),
            device("11", "Christmas Tree Plug", "Living Room"),
        ]
    )
    target = ControlTargetIntent(name_hint="Christmas Lights")

    assert graph.expand_plural_room_group(target) == target
    resolution = graph.resolve(target)
    assert [item.id for item in resolution.nodes] == ["10"]
    assert resolution.method == "unique-alias"


def test_exact_control_stays_deterministic_but_contextual_controls_require_ai():
    interpreter = ControlIntentInterpreter(FakeApplication())

    exact = interpreter._deterministic_intent("turn off Livingroom Light 2")

    assert exact is not None
    assert exact.model is None
    assert exact.actions[0].target.name_hint == "Livingroom Light 2"
    assert interpreter._deterministic_intent(
        "turn off all bedroom lights except the floor lamp"
    ) is None
    assert interpreter._deterministic_intent("turn off the other one") is None
    assert interpreter._deterministic_intent("switch the second lounge light off") is None


def test_schema_rejects_commands_outside_the_control_allowlist():
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


def test_exact_control_executes_verified_mcp_without_cloud(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    answer = asyncio.run(agent.answer(request("turn off liiving room light two"), unused))

    assert answer["success"] is True
    assert answer["route"] == "control-agent+mcp"
    assert answer["answered_by"] == "Deterministic Control Agent + verified Hubitat MCP"
    assert fallback.calls == [("Livingroom Light 2", "off")]


def test_ambiguity_sends_zero_writes_then_numbered_reply_executes_exact_candidate(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    first = asyncio.run(agent.answer(request("turn off livingroom light"), unused))

    assert first["intent"] == "control-agent-device-choice-required"
    assert first["alternatives"] == [
        "Livingroom Light 1 (Hubitat ID 1)",
        "Livingroom Light 2 (Hubitat ID 2)",
    ]
    assert fallback.calls == []

    second = asyncio.run(agent.answer(request("2"), unused))

    assert second["success"] is True
    assert fallback.calls == [("Livingroom Light 2", "off")]


def test_duplicate_label_choice_is_id_aware_and_remembered(tmp_path: Path):
    duplicate_devices = [
        device("20", "Livingroom Light 2", "Living Room"),
        device("21", "Livingroom Light 2", "Living Room"),
    ]
    agent, fallback = make_agent(tmp_path, duplicate_devices)

    first = asyncio.run(agent.answer(request("turn on living room light 2"), unused))

    assert first["intent"] == "control-agent-device-choice-required"
    assert first["alternatives"] == [
        "Livingroom Light 2 (Hubitat ID 20)",
        "Livingroom Light 2 (Hubitat ID 21)",
    ]
    assert "Hubitat ID 20" in first["message"]
    assert fallback.calls == []

    selected = asyncio.run(agent.answer(request("2"), unused))

    assert selected["success"] is True
    assert "device-id:21" in asyncio.run(agent.aliases.all()).values()

    repeated = asyncio.run(agent.answer(request("turn on living room light 2"), unused))

    assert repeated["success"] is True
    assert repeated.get("confirmation_required") is not True
    assert len(fallback.calls) == 2


def test_legacy_label_aliases_remain_compatible():
    graph = ControlDeviceGraph(
        DEVICES,
        learned_aliases={"reading lamp": "Livingroom Light 2"},
    )

    resolution = graph.resolve(ControlTargetIntent(name_hint="reading lamp"))

    assert resolution.resolved is True
    assert [item.id for item in resolution.nodes] == ["2"]


def test_local_ai_group_plan_resolves_every_target_before_first_write(tmp_path: Path):
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
    answer = asyncio.run(
        agent.answer(request("turn off all bedroom lights except the floor lamp"), unused)
    )

    assert answer["success"] is True
    assert fallback.calls == [
        ("Bedroom 1 Light", "off"),
        ("Bedroom 2 Light", "off"),
    ]
    assert answer["answered_by"] == "Local AI intent + deterministic verified Hubitat MCP"


def test_structured_context_supports_turn_it_back_on(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    first = asyncio.run(agent.answer(request("turn off Livingroom Light 2"), unused))
    assert first["success"] is True

    async def interpret(*_args: Any, **_kwargs: Any):
        return intent("on", reference="last"), {"ai_used": True, "ai_model": "qwen3.5:4b"}

    agent.interpreter.interpret = interpret
    second = asyncio.run(agent.answer(request("turn it back on"), unused))

    assert second["success"] is True
    assert fallback.calls == [
        ("Livingroom Light 2", "off"),
        ("Livingroom Light 2", "on"),
    ]


def test_sensitive_plan_requires_yes_and_no_cancels_without_write(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    first = asyncio.run(agent.answer(request("turn off Front Door Lock"), unused))
    assert first["intent"] == "control-agent-confirmation-required"
    assert fallback.calls == []

    cancelled = asyncio.run(agent.answer(request("No"), unused))
    assert cancelled["intent"] == "control-agent-cancelled"
    assert fallback.calls == []

    repeated = asyncio.run(agent.answer(request("turn off Front Door Lock"), unused))
    assert repeated["confirmation_required"] is True
    confirmed = asyncio.run(agent.answer(request("Yes"), unused))

    assert confirmed["success"] is True
    assert confirmed["control_confirmed_by_user"] is True
    assert fallback.calls == [("Front Door Lock", "off")]


def test_set_level_is_sent_and_fresh_level_is_verified(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    answer = asyncio.run(
        agent.answer(request("set Livingroom Light 2 to 40%"), unused)
    )

    assert answer["success"] is True
    assert fallback.raw_commands == [
        {"deviceId": "2", "command": "setLevel", "params": [40]}
    ]
    assert fallback.invalidations == ["devices"]
    assert "40%" in answer["message"]


def test_explicit_alias_persists_controls_and_can_be_removed(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)

    saved = asyncio.run(
        agent.answer(request('remember "big light" means "My Floor Lamp"'), unused)
    )
    controlled = asyncio.run(agent.answer(request("turn off big light"), unused))
    removed = asyncio.run(agent.answer(request("forget alias big light"), unused))

    assert saved["success"] is True
    assert controlled["success"] is True
    assert fallback.calls == [("My Floor Lamp", "off")]
    assert removed["success"] is True


def test_fresh_preflight_blocks_removed_device_before_any_write(tmp_path: Path):
    agent, fallback = make_agent(tmp_path)
    fallback.devices = [item for item in DEVICES if item["id"] != "2"]

    answer = asyncio.run(agent.answer(request("turn off Livingroom Light 2"), unused))

    assert answer["intent"] == "control-agent-preflight-blocked"
    assert fallback.calls == []


def test_release_wires_control_agent_without_feature_test_version_coupling():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "from control_agent import install_control_agent" in entrypoint
    assert "control_agent = install_control_agent(" in entrypoint
    assert "RELEASE_VERSION =" in entrypoint
    assert "control_agent_enabled: true" in config
    assert "control_agent_auto_execute_confidence_percent" in config
