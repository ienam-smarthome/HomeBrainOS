from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_hybrid_http import HybridOllamaHTTPClient  # noqa: E402
from semantic_read_pipeline import install_semantic_read_pipeline  # noqa: E402


class SemanticTransport:
    def __init__(self, *, local_online: bool, direct_online: bool) -> None:
        self.local_online = local_online
        self.direct_online = direct_online
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        self.requests.append(
            {
                "url": str(request.url),
                "model": str(body.get("model") or ""),
                "headers": dict(request.headers),
            }
        )
        direct = request.url.host == "ollama.com"
        if direct and not self.direct_online:
            return httpx.Response(503, json={"error": "cloud unavailable"}, request=request)
        if not direct and not self.local_online:
            raise httpx.ConnectError("PC Ollama is offline", request=request)

        intent = {
            "intent": "metric_comparison",
            "metric": "power",
            "operation": "max",
            "group_by": "device",
            "scope_kind": "all",
            "scope_name": "",
            "entity_names": [],
            "top_n": 1,
            "confidence": 0.98,
        }
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": json.dumps(intent)},
                "done": True,
            },
            request=request,
        )


class FakeApplication:
    def __init__(self, transport: SemanticTransport) -> None:
        raw = httpx.AsyncClient(transport=httpx.MockTransport(transport.handler))
        hybrid = HybridOllamaHTTPClient(
            local_base_url="http://pc.test:11434",
            cloud_model="gemma4:31b-cloud",
            direct_enabled=True,
            direct_base_url="https://ollama.com",
            direct_api_key="secret-test-key",
            fallback_local_proxy=True,
            client=raw,
        )
        self.ollama = SimpleNamespace(
            _http=hybrid,
            base_url="http://pc.test:11434",
            planner_model="qwen3.5:4b",
            local_fallback_model="qwen3.5:4b",
            cloud_model="gemma4:31b-cloud",
            cloud_enabled=True,
            keep_alive="30m",
        )
        self.OPTIONS = {
            "semantic_intent_enabled": True,
            "semantic_intent_cloud_fallback_enabled": True,
            "semantic_intent_cloud_timeout_seconds": 12,
        }
        self.original_ask_calls = 0

        async def original_ask(_request: Any) -> dict[str, Any]:
            self.original_ask_calls += 1
            return {"success": False, "message": "unexpected general fallback"}

        self.ask = original_ask

    def option_bool(self, name: str, default: bool = False) -> bool:
        value = self.OPTIONS.get(name, default)
        return bool(value)


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, str]] = []

    async def execute(self, intent: Any, *, query: str) -> dict[str, Any]:
        self.calls.append((intent, query))
        return {
            "success": True,
            "message": "Fridge is using the most power at 89 W.",
            "intent": "semantic-power-max",
        }


def test_semantic_read_retries_direct_cloud_when_local_pc_is_offline():
    transport = SemanticTransport(local_online=False, direct_online=True)
    application = FakeApplication(transport)
    executor = FakeExecutor()
    classifier = install_semantic_read_pipeline(
        application,
        executor,
        timeout_seconds=5,
        cache_ttl_seconds=60,
    )

    answer = asyncio.run(
        application.ask(
            SimpleNamespace(
                query="Which device is using the most power right now?",
                history=[],
            )
        )
    )

    assert classifier is not None
    assert application.original_ask_calls == 0
    assert len(executor.calls) == 1
    assert answer["route"] == "semantic+mcp"
    assert answer["model"] == "gemma4:31b-cloud"
    assert answer["ai_provider"] == "Ollama Cloud Direct"
    attempts = answer["semantic_classifier"]["ai_attempts"]
    assert attempts[0]["model"] == "qwen3.5:4b"
    assert attempts[0]["success"] is False
    assert attempts[1]["model"] == "gemma4:31b-cloud"
    assert attempts[1]["success"] is True
    assert [item["url"] for item in transport.requests] == [
        "http://pc.test:11434/api/chat",
        "https://ollama.com/api/chat",
    ]
    assert transport.requests[-1]["model"] == "gemma4:31b"
    assert transport.requests[-1]["headers"]["authorization"] == "Bearer secret-test-key"
    asyncio.run(application.ollama._http.aclose())


def test_semantic_read_keeps_local_classifier_when_pc_is_available():
    transport = SemanticTransport(local_online=True, direct_online=True)
    application = FakeApplication(transport)
    executor = FakeExecutor()
    install_semantic_read_pipeline(application, executor, timeout_seconds=5)

    answer = asyncio.run(
        application.ask(
            SimpleNamespace(
                query="Which device is using the most power right now?",
                history=[],
            )
        )
    )

    assert answer["model"] == "qwen3.5:4b"
    assert answer["ai_provider"] == "Local Ollama"
    assert len(transport.requests) == 1
    assert transport.requests[0]["url"] == "http://pc.test:11434/api/chat"
    asyncio.run(application.ollama._http.aclose())
