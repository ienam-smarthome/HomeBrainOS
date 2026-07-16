from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_inference import OllamaMCPAgent, OllamaUnavailable  # noqa: E402
from webui import render_page  # noqa: E402


class PendingTask:
    def done(self):
        return False


def test_running_probe_is_reported_as_warming():
    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        inference_probe_timeout_seconds=20,
        inference_warmup_timeout_seconds=90,
    )
    agent._health_cache = (
        time.time(),
        {"online": True, "model": "qwen3.5:9b"},
    )
    agent._inference_probe_task = PendingTask()

    status = agent.inference_status()
    assert status["ready"] is None
    assert status["state"] == "warming"
    assert "warming up" in status["message"].lower()
    assert "warming up" in agent.fallback_reason().lower()


def test_probe_accepts_long_warmup_timeout():
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "ready"}}

    class FakeHTTP:
        async def post(self, url, json, timeout):
            captured["timeout"] = timeout
            return FakeResponse()

    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        inference_probe_timeout_seconds=20,
        inference_warmup_timeout_seconds=90,
    )
    agent._http = FakeHTTP()
    agent._health_cache = (
        time.time(),
        {"online": True, "model": "qwen3.5:9b"},
    )

    result = asyncio.run(
        agent.probe_inference(force=True, timeout_seconds=90)
    )
    assert captured["timeout"] == 90
    assert result["state"] == "ready"


def test_questions_do_not_wait_while_background_warmup_is_running():
    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    agent._inference_probe_task = PendingTask()

    async def run():
        try:
            await agent.answer("Explain why the hallway is active")
        except OllamaUnavailable as exc:
            return str(exc)
        raise AssertionError("Expected warm-up fallback")

    error = asyncio.run(run())
    assert "warming up" in error.lower()


def test_ui_has_warming_status_text():
    page = render_page("Hubitat MCP AI", "0.1.13-alpha")
    assert "model warming up" in page
