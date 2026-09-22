from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_agent_core import SemanticAgentCore  # noqa: E402
from semantic_fast_path import semantic_fast_plan  # noqa: E402
from semantic_plan import (  # noqa: E402
    SemanticAction,
    SemanticPlan,
    SemanticTarget,
    semantic_plan_from_model_text,
)
from semantic_planner import SemanticPlanner, is_semantic_control_candidate  # noqa: E402


def test_semantic_plan_parser_accepts_json_inside_incidental_model_text() -> None:
    plan = semantic_plan_from_model_text(
        'JSON follows: {"version":"1","domain":"device_control","timing":"now",'
        '"target":{"scope":"room","name":"Living Room","kind":"light"},'
        '"action":{"operation":"adjust_level","value":null,"delta":null,'
        '"direction":"increase","magnitude":"default"},'
        '"needs_clarification":false,"clarification_question":"",'
        '"confidence":"high","source":"model"} done'
    )

    assert plan.target is not None
    assert plan.target.scope == "room"
    assert plan.action is not None
    assert plan.action.operation == "adjust_level"
    assert plan.action.direction == "increase"
    assert plan.executable_routine_control is True


def test_adjust_level_derives_direction_from_explicit_delta() -> None:
    action = SemanticAction(operation="adjust_level", delta=-15)
    assert action.direction == "decrease"


def test_semantic_plan_rejects_missing_direction_for_unspecified_relative_step() -> None:
    with pytest.raises(ValueError, match="requires direction"):
        SemanticAction(operation="adjust_level", delta=None)


@pytest.mark.asyncio
async def test_semantic_core_compiles_default_small_and_large_relative_steps() -> None:
    async def unused_chat(_messages, _tools):
        raise AssertionError("direct plan compile should not call chat")

    core = SemanticAgentCore(SemanticPlanner(unused_chat), default_brightness_step=20)
    base = {
        "version": "1",
        "domain": "device_control",
        "timing": "now",
        "target": {"scope": "room", "name": "Living Room", "kind": "light"},
        "needs_clarification": False,
        "clarification_question": "",
        "confidence": "high",
        "source": "model",
    }

    default_plan = SemanticPlan.model_validate({
        **base,
        "action": {
            "operation": "adjust_level",
            "value": None,
            "delta": None,
            "direction": "increase",
            "magnitude": "default",
        },
    })
    small_plan = SemanticPlan.model_validate({
        **base,
        "action": {
            "operation": "adjust_level",
            "value": None,
            "delta": None,
            "direction": "decrease",
            "magnitude": "small",
        },
    })
    large_plan = SemanticPlan.model_validate({
        **base,
        "action": {
            "operation": "adjust_level",
            "value": None,
            "delta": None,
            "direction": "increase",
            "magnitude": "large",
        },
    })

    assert core.compile_control(default_plan)["delta"] == 20
    assert core.compile_control(small_plan)["delta"] == -10
    assert core.compile_control(large_plan)["delta"] == 40


@pytest.mark.asyncio
async def test_semantic_planner_uses_no_tools_and_keeps_wire_details_out_of_prompt() -> None:
    captured = {}

    async def fake_chat(messages, tools):
        captured["messages"] = messages
        captured["tools"] = tools
        return {
            "content": (
                '{"version":"1","domain":"device_control","timing":"now",'
                '"target":{"scope":"room","name":"Living Room","kind":"light"},'
                '"action":{"operation":"adjust_level","value":null,"delta":null,'
                '"direction":"increase","magnitude":"default"},'
                '"needs_clarification":false,"clarification_question":"",'
                '"confidence":"high","source":"model"}'
            )
        }

    planner = SemanticPlanner(fake_chat)
    plan = await planner.plan("make the living room brighter")

    assert plan.action is not None
    assert plan.action.operation == "adjust_level"
    assert captured["tools"] == []
    system = captured["messages"][0]["content"]
    assert "device IDs" in system
    assert "tool names" in system
    assert "hub_call_device_command" not in system
    assert "setLevel" not in system


@pytest.mark.parametrize(
    "prompt",
    [
        "increase living room brightness",
        "make the living room brighter",
        "turn the lights up",
        "dim Bedroom 1",
        "lower hallway brightness a little",
        "set Livingroom Light 2 to 40%",
        "make Bedroom 1 warmer",
        "lower the Living Room temperature",
        "set Bedroom 2 temperature to 20.5 degrees",
    ],
)
def test_semantic_control_candidate_is_paraphrase_broad(prompt: str) -> None:
    assert is_semantic_control_candidate(prompt) is True


def test_semantic_control_candidate_does_not_capture_unrelated_status_question() -> None:
    assert is_semantic_control_candidate("what is the bathroom temperature") is False



def test_semantic_eval_corpus_covers_paraphrases_safety_and_scheduling() -> None:
    corpus_path = (
        Path(__file__).resolve().parent / "fixtures" / "semantic_control_eval.json"
    )
    cases = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert len(cases) >= 20
    expected = [case["expected"] for case in cases]
    assert any(item.get("operation") == "adjust_level" for item in expected)
    assert any(item.get("operation") == "set_level" for item in expected)
    assert any(item.get("operation") == "adjust_temperature" for item in expected)
    assert any(item.get("operation") == "set_temperature" for item in expected)
    assert any(item.get("domain") == "other" for item in expected)
    assert any(item.get("timing") == "scheduled" for item in expected)
    assert any(item.get("needs_clarification") is True for item in expected)



@pytest.mark.parametrize(
    ("prompt", "operation", "direction", "delta", "magnitude", "kind"),
    [
        ("increase hallway brightness", "adjust_level", "increase", None, "default", "light"),
        ("lower hallway brightness a little", "adjust_level", "decrease", None, "small", "light"),
        ("raise bedroom 1 brightness by 15%", "adjust_level", "increase", 15.0, "default", "light"),
        ("dim bedroom 1 by 10%", "adjust_level", "decrease", -10.0, "default", "light"),
        ("make kitchen much brighter", "adjust_level", "increase", None, "large", "light"),
        ("turn the living room lights up", "adjust_level", "increase", None, "default", "light"),
        ("make bedroom one warmer", "adjust_temperature", "increase", None, "default", "thermostat"),
        ("lower the living room temperature a little", "adjust_temperature", "decrease", None, "small", "thermostat"),
        ("raise Bedroom 1 temperature by half a degree", "adjust_temperature", "increase", 0.5, "default", "thermostat"),
    ],
)
def test_clear_semantic_controls_have_zero_model_plans(
    prompt: str,
    operation: str,
    direction: str,
    delta: float | None,
    magnitude: str,
    kind: str,
) -> None:
    plan = semantic_fast_plan(prompt)

    assert plan is not None
    assert plan.source == "fastpath"
    assert plan.target is not None
    assert plan.target.kind == kind
    assert plan.action is not None
    assert plan.action.operation == operation
    assert plan.action.direction == direction
    assert plan.action.delta == delta
    assert plan.action.magnitude == magnitude


def test_clear_semantic_fast_path_handles_absolute_thermostat_setpoint() -> None:
    plan = semantic_fast_plan("set Bedroom 2 temperature to 20.5 degrees")

    assert plan is not None
    assert plan.source == "fastpath"
    assert plan.target is not None
    assert plan.target.name == "Bedroom 2"
    assert plan.target.kind == "thermostat"
    assert plan.action is not None
    assert plan.action.operation == "set_temperature"
    assert plan.action.value == 20.5


@pytest.mark.parametrize(
    "prompt",
    [
        "how do I increase hallway brightness?",
        "increase hallway brightness tomorrow",
        "make the hallway brighter every evening",
        "set Bedroom 2 temperature to 20.5 degrees at 7pm",
    ],
)
def test_semantic_fast_path_refuses_questions_and_scheduled_requests(prompt: str) -> None:
    assert semantic_fast_plan(prompt) is None


def test_semantic_temperature_action_supports_fractional_setpoints_and_deltas() -> None:
    absolute = SemanticAction(operation="set_temperature", value=20.5)
    relative = SemanticAction(operation="adjust_temperature", delta=-0.5)

    assert absolute.value == 20.5
    assert relative.delta == -0.5
    assert relative.direction == "decrease"


def test_semantic_selection_requires_multiple_canonical_names() -> None:
    target = SemanticTarget(
        scope="selection",
        names=["Hallway Light 1", "Kitchen Light", "hallway light 1"],
        kind="light",
    )

    assert target.name == ""
    assert target.names == ["Hallway Light 1", "Kitchen Light"]

    with pytest.raises(ValueError, match="at least two names"):
        SemanticTarget(scope="selection", names=["Hallway Light 1"], kind="light")


def test_semantic_thermostat_target_is_executable_routine_control() -> None:
    plan = SemanticPlan(
        domain="device_control",
        target=SemanticTarget(
            scope="room",
            name="Bedroom 1",
            kind="thermostat",
        ),
        action=SemanticAction(
            operation="adjust_temperature",
            direction="increase",
        ),
    )

    assert plan.executable_routine_control is True


def test_semantic_core_compiles_temperature_defaults_without_protocol_names() -> None:
    async def unused_chat(_messages, _tools):
        raise AssertionError("compile must not call model")

    core = SemanticAgentCore(
        SemanticPlanner(unused_chat),
        default_brightness_step=20,
        default_temperature_step=1.0,
    )
    base = {
        "domain": "device_control",
        "timing": "now",
        "target": {"scope": "room", "name": "Bedroom 1", "kind": "thermostat"},
        "needs_clarification": False,
        "clarification_question": "",
        "confidence": "high",
        "source": "model",
    }

    warmer = SemanticPlan.model_validate({
        **base,
        "action": {
            "operation": "adjust_temperature",
            "direction": "increase",
            "delta": None,
            "magnitude": "default",
        },
    })
    slightly_cooler = SemanticPlan.model_validate({
        **base,
        "action": {
            "operation": "adjust_temperature",
            "direction": "decrease",
            "delta": None,
            "magnitude": "small",
        },
    })
    absolute = SemanticPlan.model_validate({
        **base,
        "action": {
            "operation": "set_temperature",
            "value": 20.5,
        },
    })

    assert core.compile_control(warmer) == {
        "room": "Bedroom 1",
        "command": "adjust_temperature",
        "device_kind": "thermostat",
        "delta": 1.0,
    }
    assert core.compile_control(slightly_cooler)["delta"] == -0.5
    assert core.compile_control(absolute) == {
        "room": "Bedroom 1",
        "command": "set_temperature",
        "device_kind": "thermostat",
        "setpoint": 20.5,
    }


@pytest.mark.asyncio
async def test_semantic_planner_receives_capability_world_as_non_live_context() -> None:
    captured = {}

    async def fake_chat(messages, tools):
        captured["messages"] = messages
        captured["tools"] = tools
        return {
            "content": (
                '{"version":"1","domain":"device_control","timing":"now",'
                '"target":{"scope":"room","name":"Bedroom 1","kind":"thermostat"},'
                '"action":{"operation":"adjust_temperature","value":null,'
                '"delta":null,"direction":"increase","magnitude":"default"},'
                '"needs_clarification":false,"clarification_question":"",'
                '"confidence":"high","source":"fastpath"}'
            )
        }

    planner = SemanticPlanner(fake_chat)
    plan = await planner.plan(
        "make bedroom one warmer",
        world_context=(
            '{"live_state":false,"rooms":[{"name":"Bedroom 1",'
            '"abilities":["heating_setpoint"],"devices":["Bedroom 1 TRV"]}]}'
        ),
    )

    assert plan.source == "model"
    assert plan.target is not None
    assert plan.target.name == "Bedroom 1"
    assert captured["tools"] == []
    user_context = captured["messages"][1]["content"]
    assert "Capability-grounded home context" in user_context
    assert "NOT live state" in user_context
    assert "Bedroom 1 TRV" in user_context



@pytest.mark.asyncio
async def test_semantic_core_prefers_explicit_room_without_provider_round() -> None:
    async def fake_chat(_messages, _tools):
        raise AssertionError("clear relative brightness should bypass provider")

    world = json.dumps({
        "live_state": False,
        "rooms": [{
            "name": "Hallway",
            "abilities": ["brightness", "switch"],
            "devices": ["Hallway Light 1", "Hallway Light 2"],
        }],
        "devices": [
            {
                "name": "Hallway dimmer",
                "room": "Unassigned",
                "kinds": ["sensor"],
                "abilities": ["battery"],
            },
            {
                "name": "Hallway Light 1",
                "room": "Hallway",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
            {
                "name": "Hallway Light 2",
                "room": "Hallway",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
        ],
    })

    core = SemanticAgentCore(SemanticPlanner(fake_chat))
    plan = await core.plan_control(
        "increase hallway brightness",
        world_context=world,
    )

    assert plan is not None
    assert plan.target is not None
    assert plan.target.scope == "room"
    assert plan.target.name == "Hallway"
    assert core.compile_control(plan) == {
        "room": "Hallway",
        "command": "adjust_level",
        "device_kind": "light",
        "delta": 20,
    }


@pytest.mark.asyncio
async def test_semantic_core_host_grounds_two_explicit_devices_as_selection() -> None:
    async def fake_chat(_messages, _tools):
        raise AssertionError("clear multi-device brightness should bypass provider")

    world = json.dumps({
        "live_state": False,
        "rooms": [
            {
                "name": "Hallway",
                "abilities": ["brightness", "switch"],
                "devices": ["Hallway Light 1"],
            },
            {
                "name": "Kitchen",
                "abilities": ["brightness", "switch"],
                "devices": ["Kitchen Light"],
            },
        ],
        "devices": [
            {
                "name": "Hallway Light 1",
                "room": "Hallway",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
            {
                "name": "Kitchen Light",
                "room": "Kitchen",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
        ],
    })

    core = SemanticAgentCore(SemanticPlanner(fake_chat))
    plan = await core.plan_control(
        "make Hallway Light 1 and Kitchen Light brighter",
        world_context=world,
    )

    assert plan is not None
    assert plan.target is not None
    assert plan.target.scope == "selection"
    assert plan.target.name == ""
    assert plan.target.names == ["Hallway Light 1", "Kitchen Light"]
    assert core.compile_control(plan) == {
        "device_names": ["Hallway Light 1", "Kitchen Light"],
        "command": "adjust_level",
        "device_kind": "light",
        "delta": 20,
    }


@pytest.mark.asyncio
async def test_semantic_core_normalizes_spoken_room_numbers_for_host_grounding() -> None:
    async def forbidden_chat(_messages, _tools):
        raise AssertionError("clear thermostat request should bypass provider")

    world = json.dumps({
        "live_state": False,
        "rooms": [{
            "name": "Bedroom 1",
            "abilities": ["heating_setpoint", "temperature", "switch"],
            "devices": ["Bedroom 1 TRV"],
        }],
        "devices": [{
            "name": "Bedroom 1 TRV",
            "room": "Bedroom 1",
            "kinds": ["thermostat"],
            "abilities": ["heating_setpoint", "temperature", "switch"],
        }],
    })

    core = SemanticAgentCore(SemanticPlanner(forbidden_chat))
    plan = await core.plan_control(
        "make bedroom one warmer",
        world_context=world,
    )

    assert plan is not None
    assert plan.target is not None
    assert plan.target.scope == "room"
    assert plan.target.name == "Bedroom 1"
    assert core.compile_control(plan) == {
        "room": "Bedroom 1",
        "command": "adjust_temperature",
        "device_kind": "thermostat",
        "delta": 1.0,
    }


@pytest.mark.asyncio
async def test_semantic_core_fastpath_multi_device_is_host_grounded_without_model() -> None:
    async def forbidden_chat(_messages, _tools):
        raise AssertionError("explicit switch control should remain zero-model")

    world = json.dumps({
        "live_state": False,
        "rooms": [],
        "devices": [
            {
                "name": "Hallway Light 1",
                "room": "Hallway",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
            {
                "name": "Kitchen Light",
                "room": "Kitchen",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
        ],
    })

    core = SemanticAgentCore(SemanticPlanner(forbidden_chat))
    plan = await core.plan_control(
        "turn off Hallway Light 1 and Kitchen Light",
        world_context=world,
    )

    assert plan is not None
    assert plan.source == "fastpath"
    assert plan.target is not None
    assert plan.target.scope == "selection"
    assert plan.target.names == ["Hallway Light 1", "Kitchen Light"]
    assert core.compile_control(plan) == {
        "device_names": ["Hallway Light 1", "Kitchen Light"],
        "command": "off",
        "device_kind": "auto",
    }


@pytest.mark.asyncio
async def test_semantic_core_preserves_explicit_full_device_name_over_room_name() -> None:
    async def fake_chat(_messages, _tools):
        return {
            "content": (
                '{"version":"1","domain":"device_control","timing":"now",'
                '"target":{"scope":"device","name":"Hallway Light 1","kind":"light"},'
                '"action":{"operation":"set_level","value":70,"delta":null,'
                '"direction":null,"magnitude":"default"},'
                '"needs_clarification":false,"clarification_question":"",'
                '"confidence":"high","source":"model"}'
            )
        }

    world = json.dumps({
        "live_state": False,
        "rooms": [{
            "name": "Hallway",
            "abilities": ["brightness", "switch"],
            "devices": ["Hallway Light 1", "Hallway Light 2"],
        }],
        "devices": [
            {
                "name": "Hallway Light 1",
                "room": "Hallway",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
            {
                "name": "Hallway Light 2",
                "room": "Hallway",
                "kinds": ["light"],
                "abilities": ["brightness", "switch"],
            },
        ],
    })

    core = SemanticAgentCore(SemanticPlanner(fake_chat))
    plan = await core.plan_control(
        "set Hallway Light 1 to 70%",
        world_context=world,
    )

    assert plan is not None
    assert plan.target is not None
    assert plan.target.scope == "device"
    assert plan.target.name == "Hallway Light 1"
