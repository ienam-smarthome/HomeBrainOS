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


@pytest.mark.asyncio
async def test_opt_in_request_loop_uses_semantic_room_skill_and_live_gateway():
    """One real orchestrator path with mocked MCP/provider, no Hubitat writes."""
    from mcp_agent_orchestrator import UnifiedMCPAgent
    from mcp_client import MCPTool, MCPToolResult

    class MCP:
        def __init__(self):
            self.calls = []

        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search live tools", {"type": "object"}),
                MCPTool(
                    "hub_read_rooms", "Read hub rooms",
                    {"type": "object", "properties": {
                        "tool": {"type": "string"}, "args": {"type": "object"},
                    }},
                ),
            ]

        async def get_cached_devices(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_search_tools":
                return MCPToolResult(name, arguments, {}, "", {
                    "results": [{"tool": "hub_list_rooms", "gateway": "hub_read_rooms"}]
                })
            if name == "hub_read_rooms":
                return MCPToolResult(name, arguments, {}, "", {
                    "rooms": [{"id": "10", "name": "Study"}],
                })
            raise AssertionError("Unexpected tool: " + name)

    class Response:
        def __init__(self, message):
            self.message = message

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": self.message}

    class Model:
        def __init__(self):
            self.requests = []
            self.messages = iter([
                {"role": "assistant", "content": task(
                    domain="rooms",
                    operation="read",
                    objective="List named rooms",
                    skills=["hub_admin"],
                    capabilityQueries=["list Hubitat rooms"],
                    evidenceGoals=["Current room listing"],
                )},
                {"role": "assistant", "content": "", "tool_calls": [{
                    "function": {
                        "name": "hub_read_rooms",
                        "arguments": {"tool": "hub_list_rooms", "args": {}},
                    }
                }]},
                {"role": "assistant", "content": "Study is the room returned by Hubitat."},
                {"role": "assistant", "content": "Study is the room returned by Hubitat."},
            ])

        async def post(self, url, **kwargs):
            self.requests.append(kwargs)
            return Response(next(self.messages))

        async def aclose(self):
            pass

    mcp, model = MCP(), Model()
    agent = UnifiedMCPAgent(
        mcp, "test-key", "gemma4:31b",
        ai_client=model,
        general_task_engine_enabled=True,
    )
    await agent.process_user_request("Could you tell me what rooms currently exist?")
    searches = [args for name, args in mcp.calls if name == "hub_search_tools"]
    assert searches and searches[0]["query"] == "list Hubitat rooms"
    assert any(name == "hub_read_rooms" for name, _ in mcp.calls)
    assert len(model.requests) >= 2
    model_system = model.requests[1]["json"]["messages"][0]["content"]
    assert "SKILL: ROOM MANAGEMENT" in model_system
    assert "GENERAL TASK OBJECTIVES" in model_system


def test_proposal_is_distinct_from_write():
    plan = GeneralTaskPlan.from_model(task(
        domain="automations", operation="propose",
        objective="Design a lighting rule without creating it",
    ))
    assert plan is not None
    assert plan.operation == "propose"
    assert "PROPOSAL-ONLY EXECUTION BOUNDARY" in plan.instruction()
    assert "do not call" in plan.instruction().casefold()


def test_reported_bridge_device_is_not_mistaken_for_unobserved_device():
    from device_claim_grounding import (
        extract_event_reporter_device_ids,
        find_named_device_mismatch,
    )
    source = [{"role": "tool", "content": json.dumps({
        "boundaryEvents": [{
            "name": "switch", "value": "on",
            "producedBy": {
                "label": "Matter Hue Bridge Pro", "id": "7790", "type": "device",
            },
        }],
    })}]
    observed = extract_event_reporter_device_ids(source)
    assert observed == {"7790"}
    devices = [{"label": "Matter Hue Bridge Pro", "id": "7790"}]
    mention = "Event data lists Matter Hue Bridge Pro as the reporter."
    assert find_named_device_mismatch(mention, devices, {"7805"}) is not None
    assert find_named_device_mismatch(
        mention, devices, {"7805"} | observed,
    ) is None


def test_non_device_reporter_does_not_count_as_observed():
    from device_claim_grounding import extract_event_reporter_device_ids
    source = [{"role": "tool", "content": json.dumps({
        "producedBy": {
            "id": "4019", "label": "Livingroom automation", "type": "app",
        },
    })}]
    assert extract_event_reporter_device_ids(source) == set()


@pytest.mark.asyncio
async def test_proposal_model_write_is_blocked_before_mcp_execution():
    from mcp_agent_orchestrator import UnifiedMCPAgent
    from mcp_client import MCPTool, MCPToolResult

    class FakeMCP:
        def __init__(self):
            self.calls = []

        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search", {"type": "object"}),
                MCPTool("hub_get_tool_guide", "Guide", {"type": "object"}),
                MCPTool("hub_manage_rule_machine", "Manage RM", {
                    "type": "object", "properties": {
                        "tool": {"type": "string"}, "args": {"type": "object"},
                    },
                }),
            ]

        async def get_cached_devices(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_get_tool_guide":
                return MCPToolResult(name, arguments, {}, "", {"content": "Read-only schema guide"})
            if name != "hub_search_tools":
                raise AssertionError("Proposal caused an MCP mutation")
            return MCPToolResult(name, arguments, {}, "", {
                "results": [
                    {"tool": "hub_set_rule", "gateway": "hub_manage_rule_machine"},
                ],
            })

    class Reply:
        def __init__(self, message):
            self.message = message

        def raise_for_status(self):
            return None

        def json(self):
            return {"message": self.message}

    class FakeAI:
        def __init__(self):
            self.responses = iter([
                {"role": "assistant", "content": task(
                    operation="propose", domain="automations",
                    objective="Draft a motion rule; don't execute it",
                    capabilityQueries=["native Rule Machine rule authoring"],
                )},
                {"role": "assistant", "content": "", "tool_calls": [{
                    "function": {"name": "hub_manage_rule_machine",
                                 "arguments": {
                                     "tool": "hub_set_rule",
                                     "args": {"name": "Draft"},
                                 }},
                }]},
                {"role": "assistant", "content": "", "tool_calls": [{
                    "function": {"name": "hub_get_tool_guide",
                                 "arguments": {"section": "rules"}},
                }]},
                {"role": "assistant", "content": "Proposal: create a motion rule; nothing was executed."},
            ])

        async def post(self, _url, **_kwargs):
            return Reply(next(self.responses))

        async def aclose(self):
            return None

    mcp = FakeMCP()
    agent = UnifiedMCPAgent(
        mcp, "test-key", "gemma4:31b",
        ai_client=FakeAI(),
        general_task_engine_enabled=True,
    )
    answer = await agent.process_user_request(
        "Prepare a motion-based lighting rule proposal. Do not create anything."
    )
    assert "Proposal" in answer
    assert not any(name == "hub_manage_rule_machine" for name, _ in mcp.calls)
    assert "default" not in agent.confirmations.pending
