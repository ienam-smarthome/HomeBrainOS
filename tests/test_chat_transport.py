from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from chat_transport import ChatTransport  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class PostClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []
        self.closed = False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return FakeResponse(self.payload)

    async def aclose(self):
        self.closed = True


class StreamResponse:
    def __init__(self, lines):
        self.lines = lines

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class StreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_):
        return None


class StreamClient:
    def __init__(self, lines):
        self.response = StreamResponse(lines)
        self.requests = []

    def stream(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return StreamContext(self.response)


@pytest.mark.asyncio
async def test_post_transport_normalizes_model_and_builds_native_request():
    client = PostClient({"message": {"role": "assistant", "content": "ok"}})
    transport = ChatTransport(
        "secret",
        "gemma4:31b-cloud",
        base_url="https://ollama.example/",
        client=client,
    )

    message = await transport.chat(
        [{"role": "user", "content": "hello"}],
        [{"type": "function", "function": {"name": "status"}}],
    )

    url, request = client.requests[0]
    assert message["content"] == "ok"
    assert transport.model_name == "gemma4:31b"
    assert url == "https://ollama.example/api/chat"
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert request["json"]["stream"] is False
    assert request["json"]["model"] == "gemma4:31b"
    assert request["json"]["tools"][0]["function"]["name"] == "status"

    await transport.close()
    assert client.closed is True


@pytest.mark.asyncio
async def test_stream_transport_assembles_content_and_tool_calls():
    client = StreamClient([
        '{"message":{"role":"assistant","content":"Checking "}}',
        '{"message":{"role":"assistant","content":"now","tool_calls":['
        '{"function":{"name":"status","arguments":{}}}]}}',
        '{"done":true}',
    ])
    transport = ChatTransport("secret", "model", client=client)

    message = await transport.chat(
        [{"role": "user", "content": "status"}], []
    )

    assert message["content"] == "Checking now"
    assert message["tool_calls"][0]["function"]["name"] == "status"
    assert client.requests[0][2]["json"]["stream"] is True


@pytest.mark.asyncio
async def test_transport_fails_closed_for_missing_configuration_or_message():
    unconfigured = ChatTransport("", "model", client=PostClient({}))
    with pytest.raises(RuntimeError, match="API key is not configured"):
        await unconfigured.chat([], [])

    missing_message = ChatTransport("key", "model", client=PostClient({}))
    with pytest.raises(RuntimeError, match="no assistant message"):
        await missing_message.chat([], [])


class RoutingPostClient:
    """Records every POST and lets a test fail specific base URLs."""

    def __init__(self, payload, *, fail_urls: set[str] | None = None):
        self.payload = payload
        self.fail_urls = fail_urls or set()
        self.requests = []
        self.closed = False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if url in self.fail_urls:
            raise httpx.ConnectError("connection refused", request=None)
        return FakeResponse(self.payload)

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_local_ollama_is_tried_first_when_configured():
    client = RoutingPostClient({"message": {"role": "assistant", "content": "local answer"}})
    transport = ChatTransport(
        "secret",
        "gemma4:31b-cloud",
        base_url="https://ollama.example",
        client=client,
        local_base_url="http://localhost:11434",
        local_model_name="gemma3:12b",
    )

    message = await transport.chat([{"role": "user", "content": "hi"}], [])

    assert message["content"] == "local answer"
    url, request = client.requests[0]
    assert url == "http://localhost:11434/api/chat"
    assert "Authorization" not in request["headers"]
    assert request["json"]["model"] == "gemma3:12b"
    # Cloud must never be reached when local succeeds.
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_unreachable_local_ollama_falls_back_to_cloud():
    client = RoutingPostClient(
        {"message": {"role": "assistant", "content": "cloud answer"}},
        fail_urls={"http://localhost:11434/api/chat"},
    )
    transport = ChatTransport(
        "secret",
        "gemma4:31b-cloud",
        base_url="https://ollama.example",
        client=client,
        local_base_url="http://localhost:11434",
        local_model_name="gemma3:12b",
    )

    message = await transport.chat([{"role": "user", "content": "hi"}], [])

    assert message["content"] == "cloud answer"
    urls = [url for url, _ in client.requests]
    assert urls == ["http://localhost:11434/api/chat", "https://ollama.example/api/chat"]


@pytest.mark.asyncio
async def test_local_disabled_by_default_goes_straight_to_cloud():
    client = RoutingPostClient({"message": {"role": "assistant", "content": "cloud only"}})
    transport = ChatTransport(
        "secret", "gemma4:31b-cloud", base_url="https://ollama.example", client=client
    )

    assert transport.local_configured is False
    message = await transport.chat([{"role": "user", "content": "hi"}], [])

    assert message["content"] == "cloud only"
    assert len(client.requests) == 1
    assert client.requests[0][0] == "https://ollama.example/api/chat"


@pytest.mark.asyncio
async def test_local_request_carries_keep_alive_and_split_timeout():
    client = RoutingPostClient({"message": {"role": "assistant", "content": "local"}})
    transport = ChatTransport(
        "secret",
        "gemma4:31b-cloud",
        base_url="https://ollama.example",
        client=client,
        local_base_url="http://localhost:11434",
        local_model_name="gemma3:12b",
        local_timeout_seconds=25,
        local_connect_timeout_seconds=2,
        local_keep_alive_seconds=120,
    )

    await transport.chat([{"role": "user", "content": "hi"}], [])

    _, request = client.requests[0]
    assert request["json"]["keep_alive"] == 120
    timeout = request["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 2
    assert timeout.read == 25


@pytest.mark.asyncio
async def test_cloud_request_never_carries_local_keep_alive():
    client = RoutingPostClient({"message": {"role": "assistant", "content": "cloud"}})
    transport = ChatTransport(
        "secret", "gemma4:31b-cloud", base_url="https://ollama.example", client=client
    )

    await transport.chat([{"role": "user", "content": "hi"}], [])

    _, request = client.requests[0]
    assert "keep_alive" not in request["json"]


@pytest.mark.asyncio
async def test_local_unreachable_and_cloud_unconfigured_fails_closed():
    # Local enabled but down, and no cloud API key configured -- must not
    # silently swallow the local failure and return something misleading;
    # it should raise the same fail-closed error the pure-cloud path uses.
    client = RoutingPostClient(
        {"message": {"role": "assistant", "content": "unused"}},
        fail_urls={"http://localhost:11434/api/chat"},
    )
    transport = ChatTransport(
        "",
        "gemma4:31b-cloud",
        base_url="https://ollama.example",
        client=client,
        local_base_url="http://localhost:11434",
        local_model_name="gemma3:12b",
    )

    with pytest.raises(RuntimeError, match="API key is not configured"):
        await transport.chat([{"role": "user", "content": "hi"}], [])

    # The local attempt still happened (and failed) before the cloud
    # fallback correctly refused to proceed without an API key.
    urls = [url for url, _ in client.requests]
    assert urls == ["http://localhost:11434/api/chat"]
