from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_hybrid_http import HybridOllamaHTTPClient  # noqa: E402
from ollama_hybrid_profile import resolve_hybrid_profile  # noqa: E402


class RecordedTransport:
    def __init__(self, *, gemini_status: int = 200) -> None:
        self.gemini_status = gemini_status
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        self.requests.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "json": body,
            }
        )
        if request.url.host == "generativelanguage.googleapis.com":
            if self.gemini_status != 200:
                return httpx.Response(
                    self.gemini_status,
                    json={"error": {"message": "quota exceeded"}},
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [{"text": '{"answer":"grounded"}'}],
                            }
                        }
                    ]
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": str(body.get("model") or ""),
                },
                "done": True,
            },
            request=request,
        )


def client_for(transport: RecordedTransport) -> HybridOllamaHTTPClient:
    raw = httpx.AsyncClient(transport=httpx.MockTransport(transport.handler))
    return HybridOllamaHTTPClient(
        local_base_url="http://pc.test:11434",
        cloud_model="gemma4:31b-cloud",
        direct_enabled=True,
        direct_base_url="https://ollama.com",
        direct_api_key="ollama-secret",
        fallback_local_proxy=True,
        gemini_enabled=True,
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        gemini_api_key="gemini-secret",
        gemini_model="gemini-3.6-flash",
        gemini_fallback_ollama_cloud=True,
        client=raw,
    )


def test_gemini_translates_ollama_chat_and_structured_output_without_key_in_url():
    transport = RecordedTransport()
    client = client_for(transport)
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }

    async def scenario():
        response = await client.post(
            "http://pc.test:11434/api/chat",
            json={
                "model": "gemini-3.6-flash",
                "messages": [
                    {"role": "system", "content": "Use only verified evidence."},
                    {"role": "user", "content": "Summarise the home."},
                ],
                "format": schema,
                "options": {"num_predict": 120, "temperature": 0.1},
            },
            timeout=20,
        )
        assert response.json()["message"]["content"] == '{"answer":"grounded"}'
        request = transport.requests[-1]
        assert request["url"].endswith(
            "/v1beta/models/gemini-3.6-flash:generateContent"
        )
        assert "gemini-secret" not in request["url"]
        assert request["headers"]["x-goog-api-key"] == "gemini-secret"
        assert request["json"]["store"] is False
        assert request["json"]["systemInstruction"]["parts"][0]["text"] == (
            "Use only verified evidence."
        )
        assert request["json"]["generationConfig"]["responseJsonSchema"] == schema
        assert client.last_provider() == "Google Gemini"
        await client.aclose()

    asyncio.run(scenario())


def test_gemini_rate_limit_falls_back_to_ollama_cloud():
    transport = RecordedTransport(gemini_status=429)
    client = client_for(transport)

    async def scenario():
        response = await client.post(
            "http://pc.test:11434/api/chat",
            json={
                "model": "gemini-3.6-flash",
                "messages": [{"role": "user", "content": "hello"}],
            },
            timeout=20,
        )
        assert response.json()["message"]["content"] == "gemma4:31b"
        assert [item["url"] for item in transport.requests] == [
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
            "https://ollama.com/api/chat",
        ]
        assert client.last_gemini_error
        assert client.last_provider() == "Ollama Cloud Direct"
        await client.aclose()

    asyncio.run(scenario())


def test_gemini_profile_requires_explicit_enablement_and_api_key():
    disabled = resolve_hybrid_profile(
        {
            "ollama_cloud_model": "gemma4:31b-cloud",
            "gemini_enabled": True,
            "gemini_model": "gemini-3.6-flash",
            "gemini_api_key": "",
        }
    )
    enabled = resolve_hybrid_profile(
        {
            "ollama_cloud_model": "gemma4:31b-cloud",
            "gemini_enabled": True,
            "gemini_model": "gemini-3.6-flash",
            "gemini_api_key": "configured",
        }
    )

    assert disabled["gemini_ready"] is False
    assert disabled["reasoning_model"] == "gemma4:31b-cloud"
    assert enabled["gemini_ready"] is True
    assert enabled["reasoning_model"] == "gemini-3.6-flash"


def test_gemini_configuration_keeps_api_key_secret():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "gemini_enabled: false" in config
    assert 'gemini_model: "gemini-3.6-flash"' in config
    assert "gemini_api_key: password" in config
