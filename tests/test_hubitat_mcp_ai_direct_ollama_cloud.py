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

from ollama_hybrid_http import HybridOllamaHTTPClient, direct_model_name  # noqa: E402


class RecordedTransport:
    def __init__(self, *, local_online: bool = True, direct_online: bool = True) -> None:
        self.local_online = local_online
        self.direct_online = direct_online
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body: dict[str, Any] = {}
        if request.content:
            body = json.loads(request.content.decode("utf-8"))
        self.requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "json": body,
            }
        )

        direct = request.url.host == "ollama.com"
        if direct and not self.direct_online:
            return httpx.Response(503, json={"error": "cloud unavailable"}, request=request)
        if not direct and not self.local_online:
            raise httpx.ConnectError("PC Ollama is offline", request=request)

        if request.url.path == "/api/tags":
            models = (
                [{"name": "gemma4:31b", "model": "gemma4:31b"}]
                if direct
                else [{"name": "qwen3.5:4b", "model": "qwen3.5:4b"}]
            )
            return httpx.Response(200, json={"models": models}, request=request)

        model = str(body.get("model") or "")
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": model}, "done": True},
            request=request,
        )


def client_for(transport: RecordedTransport, *, direct_enabled: bool = True):
    raw = httpx.AsyncClient(transport=httpx.MockTransport(transport.handler))
    return HybridOllamaHTTPClient(
        local_base_url="http://pc.test:11434",
        cloud_model="gemma4:31b-cloud",
        direct_enabled=direct_enabled,
        direct_base_url="https://ollama.com/api",
        direct_api_key="secret-test-key",
        fallback_local_proxy=True,
        client=raw,
    )


def test_direct_model_name_strips_only_the_cloud_suffix():
    assert direct_model_name("gemma4:31b-cloud") == "gemma4:31b"
    assert direct_model_name("gemma4:31b-cloud", "gemma4:27b") == "gemma4:27b"
    assert direct_model_name("qwen3.5:4b") == "qwen3.5:4b"


def test_cloud_chat_uses_direct_host_bearer_auth_and_direct_model_name():
    transport = RecordedTransport(local_online=False, direct_online=True)
    client = client_for(transport)

    response = asyncio.run(
        client.post(
            "http://pc.test:11434/api/chat",
            json={
                "model": "gemma4:31b-cloud",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=10,
        )
    )

    assert response.status_code == 200
    request = transport.requests[-1]
    assert request["url"] == "https://ollama.com/api/chat"
    assert request["headers"]["authorization"] == "Bearer secret-test-key"
    assert request["json"]["model"] == "gemma4:31b"
    assert "keep_alive" not in request["json"]
    assert client.last_provider() == "Ollama Cloud Direct"
    asyncio.run(client.aclose())


def test_local_model_requests_stay_on_the_pc_without_cloud_authentication():
    transport = RecordedTransport(local_online=True, direct_online=True)
    client = client_for(transport)

    response = asyncio.run(
        client.post(
            "http://pc.test:11434/api/chat",
            json={"model": "qwen3.5:4b", "messages": [], "stream": False},
            timeout=10,
        )
    )

    assert response.status_code == 200
    request = transport.requests[-1]
    assert request["url"] == "http://pc.test:11434/api/chat"
    assert "authorization" not in request["headers"]
    assert request["json"]["model"] == "qwen3.5:4b"
    assert client.last_provider() == "Local Ollama"
    asyncio.run(client.aclose())


def test_health_works_from_direct_cloud_when_the_pc_is_offline():
    transport = RecordedTransport(local_online=False, direct_online=True)
    client = client_for(transport)

    response = asyncio.run(
        client.get("http://pc.test:11434/api/tags", timeout=3)
    )
    payload = response.json()
    names = [item["name"] for item in payload["models"]]

    assert "gemma4:31b" in names
    # The compatibility alias lets existing HomeBrain model-selection code continue
    # using the saved local proxy tag while the HTTP transport rewrites it directly.
    assert "gemma4:31b-cloud" in names
    assert client.local_tags_online is False
    assert client.direct_tags_online is True
    assert client.last_provider() == "Ollama Cloud Direct"
    asyncio.run(client.aclose())


def test_direct_failure_retries_the_signed_in_local_cloud_proxy():
    transport = RecordedTransport(local_online=True, direct_online=False)
    client = client_for(transport)

    response = asyncio.run(
        client.post(
            "http://pc.test:11434/api/chat",
            json={"model": "gemma4:31b-cloud", "messages": [], "stream": False},
            timeout=10,
        )
    )

    assert response.status_code == 200
    assert [item["url"] for item in transport.requests] == [
        "https://ollama.com/api/chat",
        "http://pc.test:11434/api/chat",
    ]
    assert transport.requests[-1]["json"]["model"] == "gemma4:31b-cloud"
    assert client.last_provider() == "Ollama Cloud via local Ollama"
    assert client.last_direct_error
    asyncio.run(client.aclose())


def test_direct_cloud_api_key_is_declared_as_a_password_setting():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "ollama_direct_cloud_api_key: password" in config
    assert 'version: "0.6.3"' in config
    assert 'RELEASE_VERSION = "0.6.3"' in entrypoint
    assert 'options.get("ollama_direct_cloud_api_key")' in entrypoint
