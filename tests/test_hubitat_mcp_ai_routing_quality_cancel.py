from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from cancellable_requests import ActiveRequestRegistry  # noqa: E402
from fast_fallback_routine import FastFallbackRouter  # noqa: E402
from fastpath_ai_handoff import install_fastpath_ai_handoff  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from ollama_agent_quality import QualityNaturalHubitatOllamaAgent  # noqa: E402
from routing_policy import classify_query  # noqa: E402
from webui import render_page  # noqa: E402


class MotionMCP:
    async def call_tool(self, name, arguments):
        assert name == "hub_list_devices"
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "devices": [
                    {
                        "id": "1",
                        "label": "Kitchen Motion",
                        "currentStates": {"motion": "active"},
                    },
                    {
                        "id": "2",
                        "label": "Hall Motion",
                        "currentStates": {"motion": "inactive"},
                    },
                ]
            },
            is_error=False,
        )

    async def get_tool(self, name):
        return None

    async def supported_arguments(self, name, desired):
        return desired


def test_balanced_routing_policy():
    fast = {
        "Turn off Hallway Light 1",
        "Turn off Hallway Lights",
        "Turn on bedroom one light",
    }
    verified = {
        "What's happening at home?",
        "What is the weather tomorrow?",
        "Are any lights still on downstairs?",
        "Which lights are on?",
        "Which batteries are low?",
        "Which motion sensors are active?",
        "Show hub CPU and free memory",
        "List devices that are offline or stale",
        "Find devices that need attention",
        "List my Hubitat rooms",
    }
    planner = {
        "Why are the hallway lights on?",
        "Compare the bedroom temperatures",
        "Create a rule to turn the hall lights off after ten minutes",
        "Turn off the lights that have no recent motion",
        "Turn them off",
        "Set Bedroom 1 Light to 40%",
    }

    for query in fast:
        assert classify_query(query).route == "mcp-fast", query
    for query in verified:
        assert classify_query(query).route == "ollama-verified", query
    for query in planner:
        assert classify_query(query).route == "ollama-planner", query


def test_active_motion_is_authoritative_routine_evidence():
    answer = asyncio.run(
        FastFallbackRouter(MotionMCP()).answer("Which motion sensors are active?")
    )
    assert answer["success"] is True
    assert answer["intent"] == "fallback-active-motion"
    assert answer["display"]["metrics"][0]["value"] == "1"
    assert "Kitchen Motion" in answer["message"]
    assert "Hall Motion" not in answer["message"]


def test_routine_model_prefers_qwen_family_not_unrelated_llama():
    agent = QualityNaturalHubitatOllamaAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    installed = ["llama3.2:3b", "qwen3:4b", "qwen3.5:9b"]
    assert agent._resolve_routine_model(installed) == "qwen3:4b"
    assert agent._resolve_planner_model(installed) == "qwen3:4b"


def test_routine_model_uses_response_model_when_no_qwen_helper_exists():
    agent = QualityNaturalHubitatOllamaAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    assert agent._resolve_routine_model(["llama3.2:3b", "qwen3.5:9b"]) == "qwen3.5:9b"


def test_verified_answer_rejects_unsupported_home_claims():
    agent = QualityNaturalHubitatOllamaAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    evidence = '{"metrics":[{"label":"Lights on","value":"5"}]}'
    assert agent._unreliable_verified_answer(
        "What's happening at home?",
        "Everything is fine and the hub firmware is current.",
        evidence,
    ) is True
    assert agent._unreliable_verified_answer(
        "What's happening at home?",
        "Five lights are currently on.",
        evidence,
    ) is False


def test_new_request_cancels_previous_for_same_client():
    async def scenario():
        registry = ActiveRequestRegistry()
        first_started = asyncio.Event()
        first_cancelled = asyncio.Event()

        async def first():
            first_started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                first_cancelled.set()
                raise
            return {"message": "first"}

        async def second():
            return {"message": "second"}

        first_task = asyncio.create_task(registry.run("browser-1", first))
        await first_started.wait()
        second_answer = await registry.run("browser-1", second)
        first_result = await asyncio.gather(first_task, return_exceptions=True)

        assert second_answer == {"message": "second"}
        assert first_cancelled.is_set()
        assert isinstance(first_result[0], asyncio.CancelledError)

    asyncio.run(scenario())


def test_unresolved_fast_control_is_handed_to_ai_planner():
    async def original_ask(_request):
        return {
            "success": False,
            "intent": "fallback-ambiguous-device",
            "message": "Closest matches: Bedroom 1 Light, Bedroom 2 Light.",
        }

    class FakeOllama:
        async def answer_with_planner(self, query, history):
            assert "deterministic exact device matcher" in query
            assert "Turn off Bedroom Light" in query
            return {
                "success": True,
                "message": "Which bedroom light did you mean?",
                "intent": "ollama-natural-agent",
            }

    application = SimpleNamespace(
        ask=original_ask,
        ollama=FakeOllama(),
        OPTIONS={"ollama_agent_timeout_seconds": 60},
        VERSION="0.2.3-alpha",
    )
    wrapped = install_fastpath_ai_handoff(application)
    request = SimpleNamespace(query="Turn off Bedroom Light", history=[])
    answer = asyncio.run(wrapped(request))

    assert answer["route"] == "ollama+mcp"
    assert answer["handoff_from"] == "mcp-fast"
    assert answer["message"] == "Which bedroom light did you mean?"


def test_web_ui_allows_stop_and_replace_request():
    page = render_page("Hubitat MCP AI", "0.2.3-alpha")
    assert "AbortController" in page
    assert "Stop & ask" in page
    assert "X-HMCP-Client" in page
    assert "activeController.abort()" in page
