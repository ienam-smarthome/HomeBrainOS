"""Fast-path regression replay from Claude review (24 Oct 2026).

Uses a scripted model and mock MCP. No live commands or real device changes.
A conditional or explanatory phrase cannot dispatch an immediate switch write.
Sensitive exact controls and room/group writes must be approved.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))
from homebrain_agent import UnifiedMCPAgent
from mcp_client import MCPTool, MCPToolResult
from control_intent_guard import (
    unqualified_immediate_clause, unsafe_control_prompt,
)
from request_classification import (
    routine_control_arguments, parse_immediate_internet_access_intent,
    requests_mutation,
)
from mcp_agent_orchestrator import _explicit_mutation_request

_SW = {
    "capabilities": ["Switch", "Outlet", "PowerMeter", "Refresh"],
    "commands": ["on", "off", "refresh"],
    "attributes": {"switch": "on", "power": 5},
}
DEVICES = [
    {"id": "7105", "label": "Freezer", "name": "Freezer", "room": "Appliances", **_SW},
    {"id": "7886", "label": "Fridge", "name": "Fridge", "room": "Appliances", **_SW},
    {"id": "7107", "label": "Washing Machine", "name": "Washing Machine", "room": "Appliances", **_SW},
    {"id": "4221", "label": "TV", "name": "TV", "room": "Multimedia", **_SW},
    {"id": "6916", "label": "Block Tab-S9-FE", "name": "Block Tab-S9-FE", "room": "Internet",
     "capabilities": ["Switch"], "commands": ["on", "off"], "attributes": {"switch": "on"}},
]

class FakeMCP:
    def __init__(self):
        self.calls = []
        self.devices = [dict(d) for d in DEVICES]
    def peek_device_identities(self):
        return self.devices
    async def get_cached_devices(self, refresh=False):
        return self.devices
    async def list_tools(self):
        return [MCPTool(n, n, {"type": "object"}) for n in
                ("hub_search_tools", "hub_read_devices", "hub_manage_devices")]
    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(name, arguments, {}, "", {"matches": [{"gateway": "hub_manage_devices"}]})
        return MCPToolResult(name, arguments, {}, "ok", {"ok": True, "devices": self.devices})

class _Resp:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload

class ScriptedAI:
    def __init__(self):
        self.requests = 0
    async def post(self, url, **kwargs):
        self.requests += 1
        return _Resp({"message": {"role": "assistant", "content": "MODEL ANSWER"}})
    async def aclose(self):
        return None

def switch_writes(mcp):
    return [
        (n, a) for n, a in mcp.calls
        if n == "hub_manage_devices"
        and (a.get("args") or a).get("command") in {"on", "off", "toggle"}
    ]

async def make():
    mcp, model = FakeMCP(), ScriptedAI()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=model)
    return agent, mcp, model

NOT_AN_IMMEDIATE_WRITE = [
    "turn off the freezer when I say so",
    "turn off the freezer unless it's full",
    "turn off the freezer if it uses more than 5W",
    "turn off the freezer after I confirm",
    "turn off the freezer?",
    "turn off the freezer, actually no wait",
    "turn on the TV and tell me its power draw",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", NOT_AN_IMMEDIATE_WRITE)
async def test_conditional_deferred_questions_and_compounds_do_not_execute(prompt):
    agent, mcp, model = await make()
    await agent.process_user_request(prompt, session_id="control-test")
    assert switch_writes(mcp) == []
    assert not _explicit_mutation_request(prompt)
    assert routine_control_arguments(prompt) is None

READS_MUST_REACH_MODEL = [
    "Allow me to understand why the dehumidifier is off",
    "Enable me to see which rules turn off Bedroom 3 Mesh",
    "don't turn off the freezer, just tell me its power",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", READS_MUST_REACH_MODEL)
async def test_explanatory_leads_reach_model_not_internet_control(prompt):
    agent, mcp, model = await make()
    await agent.process_user_request(prompt, session_id="control-test")
    assert model.requests > 0
    assert switch_writes(mcp) == []
    assert parse_immediate_internet_access_intent(prompt) is None

@pytest.mark.asyncio
async def test_bulk_room_control_stages_instead_of_switching_freezer_or_fridge():
    agent, mcp, _model = await make()
    result = await agent.process_user_request_result(
        "turn off everything in Appliances", session_id="control-test",
    )
    assert switch_writes(mcp) == []
    assert result.confirmation_required is True
    assert "Freezer" in result.message and "Fridge" in result.message
    assert "Washing Machine" in result.message

@pytest.mark.asyncio
async def test_freezer_exact_command_needs_explicit_confirmation_then_executes():
    agent, mcp, _ = await make()
    first = await agent.process_user_request_result(
        "turn off the freezer", session_id="control-test",
    )
    assert first.confirmation_required
    assert switch_writes(mcp) == []
    await agent.process_user_request("confirm", session_id="control-test")
    assert len(switch_writes(mcp)) == 1

@pytest.mark.asyncio
async def test_confirmation_rejects_changed_resolved_device_identity():
    agent, mcp, _ = await make()
    result = await agent.process_user_request_result(
        "turn off the freezer", session_id="control-test",
    )
    assert result.confirmation_required
    mcp.devices[0]["id"] = "9999"
    response = await agent.process_user_request("confirm", session_id="control-test")
    assert "changed" in str(response).lower()
    assert switch_writes(mcp) == []

@pytest.mark.asyncio
async def test_unrelated_turn_cancels_staged_sensitive_action():
    agent, mcp, _ = await make()
    first = await agent.process_user_request_result(
        "turn off the freezer", session_id="control-test",
    )
    assert first.confirmation_required
    await agent.process_user_request("tell me the TV power", session_id="control-test")
    await agent.process_user_request("confirm", session_id="control-test")
    assert switch_writes(mcp) == []

@pytest.mark.asyncio
async def test_normal_single_device_direct_control_still_fast():
    agent, mcp, model = await make()
    await agent.process_user_request("turn off the washing machine", session_id="control-test")
    assert len(switch_writes(mcp)) == 1
    assert model.requests == 0

def test_parser_never_infers_authority_from_conditional_or_question():
    assert unqualified_immediate_clause("turn on TV")
    assert not unsafe_control_prompt("Turn on TV")
    for question in NOT_AN_IMMEDIATE_WRITE:
        assert not unqualified_immediate_clause(question)
        assert unsafe_control_prompt(question)
    for text in READS_MUST_REACH_MODEL:
        assert not requests_mutation(text)
