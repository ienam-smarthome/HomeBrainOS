from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_inference import OllamaMCPAgent  # noqa: E402
from webui import render_page  # noqa: E402


def test_expired_failure_becomes_retry_due_instead_of_current_timeout():
    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        inference_failure_ttl_seconds=60,
    )
    agent._inference_cache = (
        time.time() - 120,
        {
            "ready": False,
            "state": "timeout",
            "model": "qwen3.5:9b",
            "message": "Model inference timed out.",
            "error": "timeout",
        },
    )

    status = agent.inference_status()
    assert status["ready"] is None
    assert status["state"] == "retry-due"
    assert status["stale"] is True
    assert "recheck" in status["message"].lower()


def test_probe_recovers_after_expired_failure():
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "ready"}}

    class FakeHTTP:
        async def post(self, *args, **kwargs):
            return FakeResponse()

    agent = OllamaMCPAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        inference_failure_ttl_seconds=10,
    )
    agent._http = FakeHTTP()
    agent._health_cache = (
        time.time(),
        {"online": True, "model": "qwen3.5:9b"},
    )
    agent._inference_cache = (
        time.time() - 20,
        {
            "ready": False,
            "state": "timeout",
            "model": "qwen3.5:9b",
            "message": "Model inference timed out.",
        },
    )

    result = asyncio.run(agent.probe_inference())
    assert result["ready"] is True
    assert result["state"] == "ready"


def test_question_remains_in_input_after_submission():
    page = render_page("Hubitat MCP AI", "0.1.10-alpha")
    assert "input.value=query;" in page
    assert "if(!query)return;input.value='';" not in page
