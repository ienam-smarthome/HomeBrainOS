from __future__ import annotations

import sys
from pathlib import Path

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
