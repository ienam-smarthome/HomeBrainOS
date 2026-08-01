from __future__ import annotations

import sys
from contextvars import ContextVar
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool  # noqa: E402
from tool_registry import classify_tool_effect  # noqa: E402

READ_DIAGNOSTIC_PHRASES = [
    "which switches are on?",
    "why did livingroom light 1 turn off",
    "why is the kitchen light on",
    "did the front door lock change recently",
    "how come the thermostat isn't heating",
    "has the garage door been open long",
    "what happened to the living room light at 9pm",
    "is anything supposed to turn the hallway light off",
    "when did bedroom light 2 last turn on",
    "why does light 1 keep flickering",
]


class DummyMCP:
    pass


class DummyAI:
    async def aclose(self):
        return None


def make_agent() -> UnifiedMCPAgent:
    return UnifiedMCPAgent(DummyMCP(), "key", ai_client=DummyAI())


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", READ_DIAGNOSTIC_PHRASES)
async def test_read_phrasing_is_classified_from_actual_tool_activity(prompt, monkeypatch):
    agent = make_agent()

    async def fake_process(*args, **kwargs):
        agent._record_evidence(
            "hub_read_devices",
            {"tool": "hub_list_device_events"},
            success=True,
            elapsed_ms=1,
            summary="verified read evidence",
            supports_live_claim=True,
            mutates=False,
        )
        return "Verified diagnostic answer"

    monkeypatch.setattr(agent, "_process_user_request", fake_process)
    outcome = await agent.process_user_request_result(prompt, session_id="test")

    assert outcome.request_class == "live-read"
    assert outcome.message == "Verified diagnostic answer"
    assert all(receipt["mutates"] is False for receipt in outcome.evidence)
    assert "I did not execute a Hubitat control tool" not in outcome.message


@pytest.mark.asyncio
async def test_request_class_becomes_write_only_after_mutating_tool_call(monkeypatch):
    agent = make_agent()

    async def fake_process(*args, **kwargs):
        agent._mutation_call_seen.set(True)
        agent._record_evidence(
            "homebrain_control_devices",
            {"command": "off"},
            success=True,
            elapsed_ms=1,
            summary="control completed",
            mutates=True,
        )
        return "Turned off the light."

    monkeypatch.setattr(agent, "_process_user_request", fake_process)
    outcome = await agent.process_user_request_result(
        "turn off livingroom light 1", session_id="test"
    )

    assert outcome.request_class == "write"
    assert outcome.evidence[0]["mutates"] is True


def test_mutation_metadata_is_checked_on_the_requested_tool():
    declared_write = MCPTool(
        "example_write",
        "write",
        {"type": "object"},
        annotations={"mutates": True, "readOnlyHint": False},
    )
    declared_read = MCPTool(
        "example_read",
        "read",
        {"type": "object"},
        annotations={"mutates": False, "readOnlyHint": False},
    )

    assert classify_tool_effect(declared_write, {}).mutates is True
    assert classify_tool_effect(
        declared_read, {"command": "off"}
    ).mutates is False


def test_structured_manage_read_is_not_misclassified_as_a_write():
    gateway = MCPTool(
        "hub_manage_devices",
        "manage devices",
        {"type": "object"},
        annotations={"destructiveHint": True},
    )

    assert classify_tool_effect(
        gateway,
        {"tool": "hub_list_devices", "args": {}},
    ).mutates is False


def test_legacy_text_classifier_no_longer_controls_response_gate():
    source = (APP_DIR / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")

    assert "mutation_requested = _requests_mutation(user_prompt)" not in source
    assert "if mutation_requested and successful_mutations == 0" not in source
    assert "self._mutation_call_seen.get()" in source


def test_legacy_tool_effect_shadow_gate_has_been_removed():
    source = (APP_DIR / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")

    assert "_shadow_tool_effect" not in source
    assert "_MUTATION_TERMS" not in source
    assert "_call_is_mutation" not in source
    assert "def _is_sensitive" not in source
    assert "classify_tool_effect(tool, arguments)" in source


def test_confirmed_pending_actions_remain_mutating_in_source():
    source = (APP_DIR / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    confirmation = source[source.index("async def _resume_confirmation"):source.index("async def process_user_request_result")]

    assert "self._mutation_call_seen.set(True)" in confirmation
    assert "self.executor.execute(" in confirmation
    assert confirmation.count("mutates=True") == 1
