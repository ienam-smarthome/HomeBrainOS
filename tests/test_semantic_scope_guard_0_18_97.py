"""0.18.97: AI objective wins over natural-language keyword shortcuts.

Read-only host routing remains distinct from read/write authorization. These
tests only use fake models and agents; no Hubitat commands are executed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_investigation_routing import (
    ReadRouteDecision, decide_read_route,
    explicit_whole_hub_report_request, active_request_interpretation,
)
from device_incident_depth import is_connectivity_root_cause_request


def _outcome():
    return SimpleNamespace(
        message="Only actual MCP evidence may establish the fault.",
        route="unified-mcp-agent", request_class="live-read",
        evidence=[], choices=[], confirmation_required=False,
    )


@pytest.mark.asyncio
async def test_keyword_whole_hub_phrase_does_not_override_named_fault(monkeypatch):
    import app
    question = (
        "Investigate why Bedroom 3 Mesh is offline while MQTT is connected. "
        "This is NOT a comprehensive read-only investigation of my entire "
        "Hubitat system: only inspect relevant apps, logs and scheduled jobs. "
        "Do not change anything."
    )
    # Existing lexical classifier is intentionally fooled by the negative.
    assert explicit_whole_hub_report_request(question)
    consulted = []
    async def interpret(_chat, prompt):
        consulted.append(prompt)
        return ReadRouteDecision(
            "model_led", "model_choice", objective="device_connectivity",
            target="Bedroom 3 Mesh", purpose="diagnose stale telemetry",
        )
    async def investigate(*args, **kwargs):
        assert active_request_interpretation(question).objective == "device_connectivity"
        return _outcome()
    async def wrong_audit(*args, **kwargs):
        pytest.fail("Keyword-suggested system audit must not run")
    monkeypatch.setattr(app, "decide_read_route", interpret)
    monkeypatch.setattr(app.agent, "process_user_request_result", investigate)
    monkeypatch.setattr(app, "run_comprehensive_chat_audit", wrong_audit)
    result = await app._agent_request(app.ChatRequest(prompt=question))
    assert result.route == "unified-mcp-agent"
    assert consulted == [question]
    assert active_request_interpretation(question) is None


@pytest.mark.asyncio
async def test_plain_connectivity_why_question_receives_ai_intent(monkeypatch):
    import app
    question = "Why is Bedroom 3 Mesh offline when MQTT reports connected?"
    assert is_connectivity_root_cause_request(question)
    consulted = []
    async def interpret(_chat, prompt):
        consulted.append(prompt)
        return ReadRouteDecision(
            "model_led", "model_choice", objective="device_connectivity",
        )
    async def investigate(*args, **kwargs):
        assert active_request_interpretation(question).objective == "device_connectivity"
        return _outcome()
    monkeypatch.setattr(app, "decide_read_route", interpret)
    monkeypatch.setattr(app.agent, "process_user_request_result", investigate)
    result = await app._agent_request(app.ChatRequest(prompt=question))
    assert result.route == "unified-mcp-agent"
    assert consulted == [question]


@pytest.mark.asyncio
async def test_specialist_fast_path_needs_consistent_objective():
    async def chat_mismatch(messages, tools):
        assert tools == []
        return {"content": '{"route":"system_audit","objective":"device_connectivity"}'}
    q = ("Perform a comprehensive whole system Hubitat audit of every device "
         "and all rules.")
    result = await decide_read_route(chat_mismatch, q)
    assert result.route == "model_led"
    assert result.objective == "device_connectivity"
    assert result.provenance == "host_scope_override"

    async def chat_valid(messages, tools):
        return {"content": '{"route":"system_audit","objective":"system_audit"}'}
    accepted = await decide_read_route(chat_valid, q)
    assert accepted.route == "system_audit"
    assert accepted.objective == "system_audit"


@pytest.mark.asyncio
async def test_missing_or_invalid_objective_does_not_restore_keyword_router():
    async def incomplete(messages, tools):
        return {"content": '{"route":"model_led"}'}
    result = await decide_read_route(
        incomplete,
        "Investigate automation behaviour but do not design a new rule",
    )
    assert result.objective == "general_investigation"

    async def invalid(messages, tools):
        return {"content": '{"route":"system_audit","objective":"make_changes"}'}
    rejected = await decide_read_route(invalid, "Review my whole Hubitat system")
    assert rejected.route == "model_led"
    assert rejected.objective == "general_investigation"


@pytest.mark.asyncio
async def test_exact_system_check_stays_no_model_direct_command():
    calls = []
    async def model(messages, tools):
        calls.append(True)
        raise AssertionError("Direct system check should not consult model")
    selected = await decide_read_route(model, "Run system check")
    assert selected.route == "system_audit"
    assert not calls
