from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from cancellable_requests import (  # noqa: E402
    ActiveRequestRegistry,
    install_cancellable_ask,
)
from fastpath_ai_handoff import install_fastpath_ai_handoff  # noqa: E402
from ollama_agent_quality import QualityNaturalHubitatOllamaAgent  # noqa: E402
from routing_policy import classify_query  # noqa: E402
from webui import render_page  # noqa: E402


def test_balanced_routing_policy():
    fast = {
        "Turn off Hallway Light 1",
        "Turn off Hallway Lights",
        "Which lights are on?",
        "Which batteries are low?",
        "Show hub CPU and free memory",
        "List devices that are offline or stale",
        "Find devices that need attention",
    }
    verified = {
        "What's happening at home?",
        "What is the weather tomorrow?",
        "Are any lights still on downstairs?",
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


def test_cancellable_route_installs_without_fastapi_response_model_error():
    async def original_ask(_request):
        return {"success": True, "message": "ok"}

    api = FastAPI()

    @api.post("/api/ask")
    async def old_ask():
        return {"success": True}

    application = SimpleNamespace(
        app=api,
        ask=original_ask,
        AskRequest=SimpleNamespace,
    )

    registry = install_cancellable_ask(application)
    matching = [
        route
        for route in api.routes
        if getattr(route, "path", None) == "/api/ask"
        and "POST" in (getattr(route, "methods", set()) or set())
    ]

    assert isinstance(registry, ActiveRequestRegistry)
    assert len(matching) == 1
    assert matching[0].response_model is None


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
        VERSION="0.2.4-alpha",
    )
    wrapped = install_fastpath_ai_handoff(application)
    request = SimpleNamespace(query="Turn off Bedroom Light", history=[])
    answer = asyncio.run(wrapped(request))

    assert answer["route"] == "ollama+mcp"
    assert answer["handoff_from"] == "mcp-fast"
    assert answer["message"] == "Which bedroom light did you mean?"


def test_web_ui_allows_stop_and_replace_request():
    page = render_page("Hubitat MCP AI", "0.2.4-alpha")
    assert "AbortController" in page
    assert "Stop & ask" in page
    assert "X-HMCP-Client" in page
    assert "activeController.abort()" in page
