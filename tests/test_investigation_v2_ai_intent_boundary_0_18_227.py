"""Native V2 delegates intent to the model, not keyword matching.

A model-selected navigation-only handoff is never an MCP command. The actual
READ manifest/effect guard still protects every tool, even when the AI errs.
Legacy V2 retains explicit write preflight for A/B compatibility.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from control_intent_guard import independent_affirmative_mutation_clause
from investigation_v2.intent_boundary import incompatible_v2_control_request
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_intent_handoff import NAME as HANDOFF_NAME
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, MANAGE,
)

TOKEN = "v2-model-intent-admission-123456789"
QUESTION = (
    "Investigate why Bedroom 3 Mesh stopped communicating on 12 October 2026. "
    "Correlate the power-saving rule's OFF command with subsequent lastSeen, "
    "switch-state and health-status events, including exact timestamps. "
    "Inspect available rule actions and execution logs, distinguish "
    "confirmed Hubitat events from actual physical device behaviour, "
    "and explain the most likely cause and remaining uncertainty. "
    "Read only; change nothing."
)


def _api(monkeypatch, tmp_path):
    cfg = tmp_path / "model_intent_options.json"
    cfg.write_text(json.dumps({
        "investigation_v2_testing_enabled": True,
        "investigation_v2_test_token": TOKEN,
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }))
    monkeypatch.setenv("CONFIG_PATH", str(cfg))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def _post(client, question, mode="native_reads"):
    return client.post(
        "/api/v2/test", json={
            "question": question, "explicit_opt_in": True,
            "agent_mode": mode,
        }, headers={
            "X-HomeBrain-V2-Test-Token": TOKEN,
            "X-HomeBrain-V2-Request": "read-only",
        },
    )


def test_screenshot_never_mistaken_for_an_independent_write():
    assert not independent_affirmative_mutation_clause(QUESTION)
    assert not incompatible_v2_control_request(QUESTION)
    for sentence in (
        "Review the switch-state and health-status events, read only.",
        "Compare app OFF command, switch-state and rule execution.",
        "Inspect on/off history and switch-level changes. Change nothing.",
        "Review historical switch-on and switch-off events.",
    ):
        assert not independent_affirmative_mutation_clause(sentence), sentence
        assert not incompatible_v2_control_request(sentence), sentence


@pytest.mark.parametrize("question", [
    "Turn Livingroom Light 2 off.",
    "Please switch Bedroom 3 Mesh on.",
    "Check current status. Then switch Bedroom 3 Mesh off.",
    "Investigate the light, then switch it off.",
    "Read only. Now reboot the Hubitat hub.",
    "Inspect first; disable the power-saving rule.",
])
def test_real_independent_actions_still_have_negative_legacy_gate(question):
    assert incompatible_v2_control_request(question), question


@pytest.mark.asyncio
async def test_model_has_handoff_option_in_first_planning_call_without_mcp_reads():
    mcp = FakeMCP([READ_DIAG, MANAGE])
    executor = FakeExecutor(mcp, [])
    calls = []
    async def interpret(messages, tools):
        calls.append((messages, tools))
        names = [x["function"]["name"] for x in tools]
        assert HANDOFF_NAME in names
        assert "hub_manage_rules" not in names
        return {"tool_calls": [{"function": {
            "name": HANDOFF_NAME, "arguments": {}}}]}
    result = await run_native_read_agent(
        question="Switch my bedroom light off.",
        chat=interpret, mcp=mcp, executor=executor,
        max_rounds=2, max_reads=2)
    assert len(calls) == 1
    assert executor.calls == []
    assert result["answer_mode"] == "v2_control_handoff"
    assert result["native_diagnostics"]["reads_executed"] == 0
    assert result["native_diagnostics"]["no_hubitat_writes"] is True
    assert "main Ask/Chat" in result["answer"]["text"]


@pytest.mark.asyncio
async def test_ai_interprets_full_historical_question_and_can_choose_read_tool():
    mcp = FakeMCP([READ_DIAG, MANAGE])
    executor = FakeExecutor(mcp, [{"freeMemory": 860, "uptime": "2d"}])
    calls = 0
    async def interpret(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            assert HANDOFF_NAME in [x["function"]["name"] for x in tools]
            assert QUESTION in messages[1]["content"]
            return {"tool_calls": [{"function": {
                "name": "hub_read_diagnostics",
                "arguments": {"tool": "hub_get_metrics", "args": {}}}}]}
        return {"content": '{"claims":[]}'}
    result = await run_native_read_agent(
        question=QUESTION, chat=interpret, mcp=mcp, executor=executor,
        max_rounds=2, max_reads=2)
    assert calls == 2
    assert result["answer_mode"] == "native_mcp_investigation"
    assert result["native_diagnostics"]["successful_reads"] == 1
    assert executor.calls[0][1]["tool"] == "hub_get_metrics"


def test_http_native_question_reaches_model_instead_of_pre_ai_keyword_gate(
        monkeypatch, tmp_path):
    module = _api(monkeypatch, tmp_path)
    seen = []
    async def fake_native(*, question, **kwargs):
        seen.append(question)
        return {
            "answer_mode": "native_mcp_investigation",
            "answer": {"text": "Read-only model-led investigation admitted."},
            "report": {"text": "Read-only evidence retained."},
            "native_diagnostics": {
                "reads_executed": 0, "successful_reads": 0},
            "resolved_devices": [],
            "resolution_method": "model_native_mcp_reads",
        }
    monkeypatch.setattr(module, "run_native_read_agent", fake_native)
    with TestClient(module.app) as client:
        response = _post(client, QUESTION)
    assert response.status_code == 200, response.text
    assert seen == [QUESTION]


def test_http_real_control_uses_model_navigation_and_not_gateway(
        monkeypatch, tmp_path):
    module = _api(monkeypatch, tmp_path)
    seen = []
    async def fake_native(*, question, **kwargs):
        seen.append(question)
        return {
            "answer_mode": "v2_control_handoff",
            "answer": {
                "text": "This request asks HomeBrain to change Hubitat state. "
                        "No Hubitat command was sent. Use HomeBrain's "
                        "main Ask/Chat interface for the action."},
            "native_diagnostics": {
                "reads_executed": 0,
                "no_hubitat_writes": True,
                "request_interpretation_source": "native_model_tool_choice",
            },
        }
    monkeypatch.setattr(module, "run_native_read_agent", fake_native)
    with TestClient(module.app) as client:
        response = _post(client, "Turn Bedroom 3 Mesh off.")
    assert seen == ["Turn Bedroom 3 Mesh off."]
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "v2_control_not_supported"
    assert response.json()["detail"]["interpretation"] == (
        "model_selected_control_handoff")
    assert response.json()["detail"]["reads_executed"] == 0
