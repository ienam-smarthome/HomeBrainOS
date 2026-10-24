"""0.18.107: read-only investigations must never become control shortcuts.

Regression based on real HomeBrain 0.18.106 issue:
  'turn on living room light two' -> 25s full-manifest sensitive failure.
A named device can contain fused 'Livingroom' while speech separates
'living room'; numerical words also require canonicalization. Fail closed
for ambiguous requests but ground exact unique light names before rooms.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from control_intent_guard import (
    semantic_control_clause_eligible, unqualified_immediate_clause,
    explicitly_read_only_request,
)
from homebrain_agent import UnifiedMCPAgent
from semantic_agent_core import SemanticAgentCore
from semantic_plan import semantic_plan_from_control_arguments
from semantic_world_model import build_semantic_world
from request_classification import routine_control_arguments
from mcp_agent_orchestrator import _explicit_mutation_request
from test_control_fast_path_guards_0_18_103 import (
    FakeMCP, ScriptedAI, switch_writes,
)

LIGHTS = [
    {
        "id": "7805", "name": "Livingroom Light 1",
        "label": "Livingroom Light 1", "room": "Living Room",
        "capabilities": ["Switch", "SwitchLevel", "Light"],
        "commands": ["on", "off", "setLevel"],
        "attributes": {"switch": "off", "level": 50},
    },
    {
        "id": "7999", "name": "Livingroom Light 2",
        "label": "Livingroom Light 2", "room": "Living Room",
        "capabilities": ["Switch", "SwitchLevel", "Light"],
        "commands": ["on", "off", "setLevel"],
        "attributes": {"switch": "off", "level": 50},
    },
]


class LightMCP(FakeMCP):
    def __init__(self):
        super().__init__()
        self.devices = [dict(d) for d in LIGHTS]


def test_named_spoken_light_outweighs_containing_room_and_numbered_sibling():
    world = build_semantic_world(LIGHTS, max_devices=10)
    utterance = "turn on living room light two"
    plan = semantic_plan_from_control_arguments(routine_control_arguments(utterance))
    assert plan is not None
    grounded = SemanticAgentCore.ground_plan_target(utterance, plan, world)
    assert grounded.target.scope == "device"
    assert grounded.target.name == "Livingroom Light 2"
    assert grounded.target.names == []
    assert "Livingroom Light 1" not in grounded.target.name


@pytest.mark.parametrize(
    ("utterance", "label"),
    [
        ("turn on living room light two", "Livingroom Light 2"),
        ("turn on living room light 2", "Livingroom Light 2"),
        ("turn on Livingroom Light Two", "Livingroom Light 2"),
        ("turn on living room light one", "Livingroom Light 1"),
    ],
)
@pytest.mark.asyncio
async def test_direct_spoken_light_issues_single_target_command_without_bulk_confirmation(
    utterance, label,
):
    mcp, model = LightMCP(), ScriptedAI()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=model)
    response = await agent.process_user_request_result(
        utterance, session_id="spoken-light",
    )
    writes = switch_writes(mcp)
    assert len(writes) == 1
    assert writes[0][1]["args"]["deviceId"] == (
        "7999" if label.endswith("2") else "7805"
    )
    assert writes[0][1]["args"]["command"] == "on"
    assert response.confirmation_required is False
    assert "could not verify the exact device list" not in response.message.lower()
    assert response.metrics["counters"]["semantic_target_grounded"] == 1
    assert model.requests == 0


@pytest.mark.asyncio
async def test_spoken_room_plural_still_requires_bulk_approval():
    mcp, model = LightMCP(), ScriptedAI()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=model)
    response = await agent.process_user_request_result(
        "turn on living room lights", session_id="room-plural",
    )
    assert response.confirmation_required is True
    assert "Livingroom Light 1" in response.message
    assert "Livingroom Light 2" in response.message
    assert switch_writes(mcp) == []
    assert response.metrics["outcome"] == "needs_input"


READ_ONLY_CASES = [
    (
        "Why did Livingroom Light 1 remain ON from approximately 16:29 to "
        "18:29? Investigate sensors, app 4019 and automation logs. "
        "Read-only. Do not modify anything."
    ),
    "Explain why Livingroom Light 1 stayed on. Read-only; do not change anything.",
    "Review the actual device commands used by rule 4019. Do not modify anything.",
    "Identify the rule that turns on Livingroom Light 1, read-only.",
    "Turn on Livingroom Light 2. Read-only; do not change anything.",
]


@pytest.mark.parametrize("prompt", READ_ONLY_CASES)
def test_explicit_read_only_never_enters_immediate_control_authorization(prompt):
    assert explicitly_read_only_request(prompt)
    assert not semantic_control_clause_eligible(prompt)
    assert not unqualified_immediate_clause(prompt)
    assert not _explicit_mutation_request(prompt)


@pytest.mark.asyncio
async def test_original_read_only_history_investigation_reaches_model_without_controls():
    mcp, model = LightMCP(), ScriptedAI()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=model)
    response = await agent.process_user_request_result(
        READ_ONLY_CASES[0], session_id="historical-investigation",
    )
    assert switch_writes(mcp) == []
    assert model.requests > 0
    assert response.metrics["counters"].get("semantic_fastpath_plans", 0) == 0
    assert "sensitive control" not in response.message.lower()


@pytest.mark.parametrize("prompt", [
    "make bedroom one warmer",
    "increase hallway brightness",
    "please dim livingroom light 1",
    "turn off everything in Appliances",
    "turn on living room light two",
    "could you turn on Livingroom Light 2",
])
def test_genuine_direct_commands_remain_semantic_control_candidates(prompt):
    assert semantic_control_clause_eligible(prompt)


@pytest.mark.parametrize("prompt", [
    "Why did the light turn on?",
    "Can you explain why the light stayed on?",
    "Review app 4019's on and off conditions",
    "Investigate the actual behavior of the living room lights",
    "The livingroom light remains on",
])
def test_descriptive_or_investigative_sentences_are_not_semantic_controls(prompt):
    assert not semantic_control_clause_eligible(prompt)
