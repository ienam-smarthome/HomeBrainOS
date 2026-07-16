from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from ollama_agent_resilient import OllamaMCPAgent  # noqa: E402
from request_router import run_fast_path  # noqa: E402


class SuccessfulFallback:
    def __init__(self):
        self.calls = 0

    async def answer(self, query):
        self.calls += 1
        return {
            "success": True,
            "message": "Hub health returned.",
            "display": {"kind": "hub-health", "title": "Hub C8 Pro"},
        }


class FakeOllama:
    def __init__(self):
        self.answer_calls = 0
        self.health_calls = 0

    async def answer(self, query, history):
        self.answer_calls += 1
        raise AssertionError("Ollama must not run for a recognised fast-path request")

    async def health(self, force=False):
        self.health_calls += 1
        return {"online": False, "error": "offline"}


class RetryFallback:
    def __init__(self):
        self.calls = 0

    async def answer(self, query):
        self.calls += 1
        if self.calls == 1:
            return {"success": False, "message": "temporary MCP failure"}
        return {"success": True, "message": "retry succeeded"}


def test_fast_path_returns_before_ollama_and_does_not_repeat_fallback(monkeypatch):
    fake_fallback = SuccessfulFallback()
    fake_ollama = FakeOllama()

    monkeypatch.setattr(app_module, "fallback", fake_fallback)
    monkeypatch.setattr(app_module, "ollama", fake_ollama)
    monkeypatch.setitem(app_module.OPTIONS, "fallback_enabled", True)
    monkeypatch.setitem(app_module.OPTIONS, "fast_path_enabled", True)
    monkeypatch.setitem(app_module.OPTIONS, "ollama_enabled", True)
    monkeypatch.setitem(app_module.OPTIONS, "mcp_timeout_seconds", 2)

    answer = asyncio.run(
        app_module.ask(
            app_module.AskRequest(query="Check the hub health status")
        )
    )

    assert answer["route"] == "mcp-fast"
    assert answer["success"] is True
    assert fake_fallback.calls == 1
    assert fake_ollama.answer_calls == 0


def test_fast_path_retries_one_transient_mcp_failure_only():
    fallback = RetryFallback()
    answer = asyncio.run(
        run_fast_path(
            "Check the hub health status",
            fallback,
            timeout_seconds=2,
            retries=1,
        )
    )

    assert answer["success"] is True
    assert answer["fast_path_attempts"] == 2
    assert fallback.calls == 2


def test_offline_ollama_result_is_cached_for_following_requests():
    class FailingHTTP:
        def __init__(self):
            self.calls = 0

        async def get(self, *args, **kwargs):
            self.calls += 1
            raise TimeoutError("offline")

    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        health_timeout_seconds=0.01,
    )
    agent._http = FailingHTTP()

    first = asyncio.run(agent.health())
    second = asyncio.run(agent.health())

    assert first["online"] is False
    assert second["online"] is False
    assert agent._http.calls == 1
