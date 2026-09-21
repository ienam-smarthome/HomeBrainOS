from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_agent_core import SemanticAgentCore  # noqa: E402
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
    assert any(item.get("domain") == "other" for item in expected)
    assert any(item.get("timing") == "scheduled" for item in expected)
    assert any(item.get("needs_clarification") is True for item in expected)
