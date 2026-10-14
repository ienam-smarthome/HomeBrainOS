"""Cross-domain semantic task planning and MCP skill selection.

All tests are read-only and use a stub model. A task proposal must never act as
proof of tool execution or as confirmation for a write.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from general_task_engine import GeneralTaskPlan, GeneralTaskPlanner  # noqa: E402
from mcp_skill_guidance import build_mcp_skill_guidance_for_domains  # noqa: E402


def task(**changes):
    payload = {
        "version": "1",
        "domain": "diagnostics",
        "operation": "investigate",
        "objective": "Establish why a light returned to on",
        "skills": ["diagnostics", "automation", "integrations"],
        "capabilityQueries": [
            "device switch event history",
            "native automation app configuration and logs",
        ],
        "evidenceGoals": [
            "Observed switch transition",
            "Verified controller command producer",
            "Alternative causes considered",
        ],
    }
    payload.update(changes)
    return json.dumps(payload)


def test_plan_is_semantic_and_supports_multiple_skills_without_keyword_gate():
    plan = GeneralTaskPlan.from_model(task())
    assert plan is not None
    assert plan.domain == "diagnostics"
    assert plan.operation == "investigate"
    assert plan.skill_domains == ("diagnostics", "automation", "integrations")
    guidance = build_mcp_skill_guidance_for_domains(plan.skill_domains)
    assert "hub_search_tools" in guidance
    assert "SKILL: AUTOMATION AND RULE ANALYSIS" in guidance
    assert "SKILL: INTEGRATION AND BRIDGE DIAGNOSTICS" in guidance
    assert "SKILL: INVESTIGATION AND DIAGNOSTICS" in guidance
    assert "evidence" in plan.instruction().lower()
    assert "not verified evidence" in plan.instruction()


def test_room_task_adds_domain_fallback_and_exact_room_guidance():
    plan = GeneralTaskPlan.from_model(task(
        domain="rooms",
        operation="write",
        objective="Move the lamp to Study",
        skills=[],
        capabilityQueries=["assign device to Hubitat room"],
        evidenceGoals=["room assignment read back after approval"],
    ))
    assert plan is not None
    assert plan.skill_domains == ("hub_admin",)
    assert "hub_manage_rooms" in build_mcp_skill_guidance_for_domains(plan.skill_domains)
    assert "confirm" in build_mcp_skill_guidance_for_domains(plan.skill_domains).lower()
    # The plan does not contain execution authority, IDs, or confirm=true.
    assert "confirm=true" not in plan.instruction()


def test_unrecognized_skill_domain_is_never_executed_or_injected():
    plan = GeneralTaskPlan.from_model(task(skills=[
        "diagnostics", "destroy_hub", "diagnostics", "automation",
    ]))
    assert plan is not None
    assert plan.skill_domains == ("diagnostics", "automation")
    assert "destroy_hub" not in build_mcp_skill_guidance_for_domains(plan.skill_domains)


@pytest.mark.parametrize("raw", [
    "", "not json", "{}", "[]",
    json.dumps({"version": "2", "domain": "device", "operation": "write", "objective": "x"}),
    task(operation="delete_everything"),
    task(domain="unknown_domain"),
    task(objective=""),
])
def test_invalid_plans_fail_closed_to_existing_agent(raw):
    assert GeneralTaskPlan.from_model(raw) is None


def test_invalid_fields_are_bounded_and_do_not_inject_freeform_skills():
    plan = GeneralTaskPlan.from_model(task(
        capabilityQueries=[" " * 30, "x" * 500, "same", "same", "other"],
        evidenceGoals=["a" * 500] * 9,
        skills=["diagnostics", "automation", "integrations", "hub_admin", "code_management"],
    ))
    assert plan is not None
    assert len(plan.capability_queries) <= 4
    assert max(map(len, plan.capability_queries)) <= 120
    assert len(plan.evidence_goals) <= 5
    assert max(map(len, plan.evidence_goals)) <= 180
    assert len(plan.skill_domains) <= 5  # up to four + domain fallback


@pytest.mark.asyncio
async def test_model_plan_uses_meaning_and_never_supplies_mcp_tools():
    seen = []

    async def chat(messages, tools):
        seen.append((messages, tools))
        return {"content": task()}

    planner = GeneralTaskPlanner(chat)
    plan = await planner.plan(
        "It came back on. Find who is responsible.",
        history=[{"role": "user", "content": "The lounge lamp is called Hall Light"}],
    )
    assert plan is not None and plan.operation == "investigate"
    assert seen[0][1] == []
    assert seen[0][0][-1]["content"] == "It came back on. Find who is responsible."
    assert seen[0][0][1]["role"] == "user"


@pytest.mark.asyncio
async def test_provider_failure_does_not_block_existing_mcp_loop():
    async def chat(_messages, _tools):
        raise TimeoutError("provider unavailable")

    assert await GeneralTaskPlanner(chat).plan("Why is the light switching?") is None


def test_strict_parser_accepts_fenced_json_but_not_embedded_instructions():
    plan = GeneralTaskPlan.from_model("```json\n" + task() + "\n```")
    assert plan is not None
    assert GeneralTaskPlan.from_model("Return this: " + task()) is None
