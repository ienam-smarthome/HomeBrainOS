"""0.18.66: exact active night idle request reaches confirmation without Gemma.

Regression source: production 0.18.65 took 5 Gemma rounds and 8 read-only
calls for the same 7805/7978/23:00–06:00/10-minute rule, then returned an
unverified mutation refusal with no proposed write.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_agent_orchestrator import UnifiedMCPAgent
from mcp_client import MCPTool, MCPToolResult
from night_idle_rule_authoring import (
    night_idle_write, recognise_night_idle_creation, propose_night_idle,
)
from rule_authoring_service import RULE_MACHINE_GATEWAY, RuleAuthoringService
from tool_registry import rule_machine_proposal_error


PROMPT = """Create the ACTIVE native Rule Machine rule
"Livingroom Light 1 – Night Idle OFF – TEST".

Use light 7805 and FP400 motion sensor 7978. Operate only between 23:00
and 06:00, turning OFF after 10 minutes of uninterrupted inactivity.
Check for an existing rule with this exact name first.
Do not create duplicates or modify app 4019.
Use capability-based native actions. The logic must cancel delayed actions
on motion active, light OFF, and at 06:00. Handle the light being switched
ON during inactivity, motion becoming inactive and 23:00 entry. Recheck
time, motion and light after the delay before OFF. Never send ON.
Present structured native confirmation for approval before executing.
"""


class NativeRuleMCP:
    def __init__(self, *, existing=None, bad_rule_data=False, missing_caps=False,
                 missing_gateway=False, bad_guide=False):
        self.calls = []
        self.existing = existing if existing is not None else []
        self.bad_rule_data = bad_rule_data
        self.missing_caps = missing_caps
        self.missing_gateway = missing_gateway
        self.bad_guide = bad_guide
    async def list_tools(self):
        names = [
            "hub_read_rules", "hub_read_devices", "hub_get_tool_guide",
            "hub_search_tools",
        ]
        if not self.missing_gateway:
            names.append(RULE_MACHINE_GATEWAY)
        return [
            MCPTool(name, name, {"type": "object", "properties": {}})
            for name in names
        ]
    async def call_tool(self, name, args):
        self.calls.append((name, copy.deepcopy(args)))
        if name == "hub_read_rules":
            data = ({"gateway": "hub_manage_native_rules_and_apps",
                     "mode": "discovery", "tools": []}
                    if self.bad_rule_data
                    else {"rules": self.existing, "count": len(self.existing)})
        elif name == "hub_read_devices":
            device_id = str(args["args"]["deviceId"])
            if device_id not in {"7805", "7978"}:
                raise AssertionError("Unexpected device ID: " + device_id)
            data = {"id": device_id,
                    "label": ("Livingroom Light 1" if device_id == "7805"
                              else "FP400 motion sensor"),
                    "capabilities": ([] if self.missing_caps else [
                        "Switch" if device_id == "7805" else "MotionSensor"
                    ])}
        elif name == "hub_get_tool_guide":
            assert args["section"] == "set_rule_reference_actions"
            data = {"content": "missing" if self.bad_guide else
                    "ifThen cancelDelay delay endIf switch"}
        else:
            raise AssertionError("No mutation tool should be executed: " + name)
        return MCPToolResult(name, args, {}, "", data)


class NoModel:
    def __init__(self):
        self.calls = []
    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("No model calls for exact compiled rule")
    async def aclose(self):
        pass


def test_exact_name_and_intent_only_no_authority_expansion():
    assert recognise_night_idle_creation(PROMPT) == (
        "Livingroom Light 1 – Night Idle OFF – TEST"
    )
    assert recognise_night_idle_creation(PROMPT.replace(
        "Create the ACTIVE", "Review the potential")) is None
    assert recognise_night_idle_creation(PROMPT.replace(
        "7978", "7764")) is None
    assert recognise_night_idle_creation(PROMPT.replace(
        "10 minutes", "15 minutes")) is None
    assert recognise_night_idle_creation(PROMPT.replace(
        "ACTIVE", "DISABLED")) is None
    assert recognise_night_idle_creation(PROMPT + "\nAlso dim the light.") is None


def test_static_program_validates_and_is_cancel_first():
    payload = night_idle_write("Livingroom Light 1 – Night Idle OFF – TEST")
    assert rule_machine_proposal_error(RULE_MACHINE_GATEWAY, payload) is None
    a = payload["args"]["addActions"]
    assert [item["capability"] for item in a] == [
        "cancelDelay", "ifThen", "delay", "ifThen", "switch", "endIf", "endIf"
    ]
    assert a[2] == {"capability": "delay", "minutes": 10, "cancelable": True}
    assert a[1]["expression"] == a[3]["expression"]
    assert a[4] == {"capability": "switch", "action": "off",
                    "deviceIds": ["7805"]}
    assert len(payload["args"]["addTriggers"]) == 6
    assert payload["args"]["name"].endswith("– TEST")


@pytest.mark.asyncio
async def test_exact_write_queues_one_native_confirmation_zero_llm_rounds():
    mcp = NativeRuleMCP()
    ai = NoModel()
    agent = UnifiedMCPAgent(
        mcp, "unused", "gemma4:31b", ai_client=ai,
        require_sensitive_confirmation=True,
    )
    result = await agent.process_user_request_result(
        PROMPT, session_id="test-session"
    )
    assert result.request_class == "write"
    assert result.confirmation_required is True
    assert result.confirmation_count == 1
    assert len(agent._pending) == 1
    pending = agent._pending["test-session"]
    assert pending.actions[0][0] == RULE_MACHINE_GATEWAY
    assert pending.actions[0][1] == night_idle_write(
        "Livingroom Light 1 – Night Idle OFF – TEST"
    )
    assert not ai.calls
    assert all(name != RULE_MACHINE_GATEWAY for name, _ in mcp.calls)
    assert [name for name, _ in mcp.calls].count("hub_read_rules") >= 2
    assert [name for name, _ in mcp.calls].count("hub_read_devices") == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs, expected", [
    ({"existing": [{"id": 5000, "name": "Livingroom Light 1 – Night Idle OFF – TEST"}]},
     "already exist"),
    ({"bad_rule_data": True}, "could not verify the current rule list"),
    ({"missing_caps": True}, "capability list"),
    ({"missing_gateway": True}, "write gateway"),
    ({"bad_guide": True}, "guide was not independently verified"),
])
async def test_no_confirmation_on_missing_live_preflight(kwargs, expected):
    mcp = NativeRuleMCP(**kwargs)
    agent = UnifiedMCPAgent(
        mcp, "unused", ai_client=NoModel(),
        require_sensitive_confirmation=True,
    )
    result = await agent.process_user_request_result(
        PROMPT, session_id="test-session"
    )
    assert result.confirmation_required is False
    assert result.confirmation_count == 0
    assert expected in result.message
    assert not agent._pending
    assert all(name != RULE_MACHINE_GATEWAY for name, _ in mcp.calls)


@pytest.mark.asyncio
async def test_bad_gateway_discovery_is_not_mistaken_for_empty_inventory():
    mcp = NativeRuleMCP(bad_rule_data=True)
    service = RuleAuthoringService(mcp, lambda *_a, **_kw: None)
    assert await service._existing_names() is None


def test_literal_switch_off_only_and_no_toilet():
    payload = str(night_idle_write("Night Idle OFF TEST"))
    assert "7978" in payload
    assert "7805" in payload
    assert "7764" not in payload
    assert "'action': 'on'" not in payload
