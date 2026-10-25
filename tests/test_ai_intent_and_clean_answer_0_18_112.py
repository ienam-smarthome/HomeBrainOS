"""0.18.112: AI-interpreted root-cause task must not become inventory.

Uses pure simulated evidence and code contracts only; no Hubitat activity.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_checkpoint import is_investigative_question
from causal_timeline import has_explicit_focal_clock
from ai_investigation_routing import ReadRouteDecision, set_request_interpretation, reset_request_interpretation
from adaptive_investigation_policy import model_led_investigation_request
from shared_investigation_completion import apply_shared_investigation_completion

QUESTION = (
    "Why does Livingroom Light 1 sometimes stay ON when nobody is in the room? "
    "Investigate its actual controlling automation, configured sensors, "
    "inactivity timers and relevant recorded activity. "
    "Identify the most likely cause using verified evidence. "
    "Read-only. Do not change anything."
)


def test_open_ended_root_cause_qualifies_for_ai_interpretation():
    app = (APP / "app.py").read_text(encoding="utf-8")
    assert is_investigative_question(QUESTION)
    assert not has_explicit_focal_clock(QUESTION)
    assert "or (is_investigative_question(request.message)" in app
    assert "and not has_explicit_focal_clock(request.message))" in app


def test_interpreted_purpose_reaches_read_only_model_tool_plan():
    source = (APP / "mcp_agent_orchestrator.py").read_text(encoding="utf-8")
    assert "investigative_ai_objective = bool(" in source
    assert "None if (investigative_ai_objective or diagnostic_objective)" in source
    assert "else _device_inventory_arguments(user_prompt)" in source
    assert "AI-INTERPRETED READ-ONLY TASK (ADVISORY)" in source
    assert 'str(interpreted.purpose or "answer the user' in source
    assert "a final answer to a causal investigation" in source
    assert "catalog.activate_investigation_read_view" in source
    token = set_request_interpretation(
        QUESTION, ReadRouteDecision("model_led", "model_choice",
            objective="general_investigation", target="Livingroom Light 1",
            purpose="explain why light stays on, verify controlling automation")
    )
    try:
        assert model_led_investigation_request(QUESTION)
    finally:
        reset_request_interpretation(token)


def test_completeness_is_structured_technical_detail_not_visible_answer():
    result = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="17 Living Room devices: motion sensors and lights.",
        evidence=[{
            "tool": "homebrain_device_inventory",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"group": "Living Room"},
            "details": {"count": 17}
        }],
        metrics={"outcome": "unresolved", "counters": {}, "timings_ms": {}},
        investigation_coverage=None,
    )
    classified = apply_shared_investigation_completion(result, QUESTION)
    assert "Investigation completeness" not in classified.message
    assert "unchecked source classes" not in classified.message
    assert classified.investigation_coverage["status"] == "partial-evidence"
    assert classified.investigation_coverage["limitations"]
    assert classified.investigation_coverage["presentation"] == "technical-only"
    assert classified.message.startswith("17 Living Room devices")


def test_regular_live_state_reply_is_not_turned_into_diagnostic():
    text = "Is Livingroom Light 1 currently ON or OFF?"
    assert not has_explicit_focal_clock(text)
    assert not is_investigative_question(text)

def test_open_ended_route_integration_uses_ai_before_agent(monkeypatch):
    import asyncio
    import app as api

    calls = []
    class FakeAgent:
        async def _chat(self, messages, tools):
            raise AssertionError("Route should use patched single AI interpreter")

        async def process_user_request_result(self, prompt, history, *, session_id):
            calls.append(("agent", prompt))
            from ai_investigation_routing import active_request_interpretation
            interpretation = active_request_interpretation(prompt)
            assert interpretation is not None
            assert interpretation.objective == "general_investigation"
            return SimpleNamespace(
                request_class="live-read", route="unified-mcp-agent",
                evidence=[], investigation_coverage=None,
                interpreted_intent=None, message="Insufficient evidence to establish cause."
            )

    async def choose(_chat, question):
        calls.append(("ai_interpreter", question))
        return ReadRouteDecision(
            "model_led", "model_choice",
            objective="general_investigation", target="Livingroom Light 1",
            purpose="investigate controlling automation and OFF logic",
        )

    monkeypatch.setattr(api, "agent", FakeAgent())
    monkeypatch.setattr(api, "decide_read_route", choose)
    result = asyncio.run(api._agent_request(api.ChatRequest(query=QUESTION)))
    assert [name for name, _ in calls] == ["ai_interpreter", "agent"]
    assert result.interpreted_intent["objective"] == "general_investigation"
    assert result.interpreted_intent["target"] == "Livingroom Light 1"
