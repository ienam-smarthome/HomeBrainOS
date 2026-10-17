"""v0.18.28 — Explicit Claude API, Free default, strict provider isolation."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from anthropic_transport import AnthropicMessagesTransport, convert_messages, convert_tools
from chat_transport import ChatTransport, PaidModelUnavailable
from paid_model_routing import (
    set_request_model_tier, reset_request_model_tier,
    request_model_tier, choose_paid_model,
)
from api_response_builder import build_agent_response
from webui import render_page


class Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class PostClient:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.responses.pop(0))

    async def aclose(self):
        pass


def fixture_tools():
    return [
        {"type": "function", "function": {
            "name": "hub_read_devices", "description": "Read Hubitat device",
            "parameters": {
                "type": "object",
                "properties": {"deviceId": {"type": "string"}},
                "required": ["deviceId"],
            },
        }},
    ]


def test_free_is_default_in_context_api_and_rendered_selector():
    from app import ChatRequest

    assert request_model_tier() == "free"
    assert ChatRequest(query="Why did the light turn on?").model_tier == "free"
    assert ChatRequest(query="Why?", model_tier="claude").model_tier == "claude"
    page = render_page("HomeBrain", "0.18.28")
    assert '<option value="free" selected>' in page
    assert '<option value="claude">' in page
    assert "anthropic API" in page or "Anthropic API" in page
    assert "model_tier:selectedTier" in page
    assert "localStorage.setItem('hmcp_model_tier'" not in page


def test_auto_retains_backward_compatible_hybrid_but_default_is_never_auto_paid():
    assert choose_paid_model([
        {"role": "user", "content": "Investigate why light turned off"}
    ], "hybrid") is None
    token = set_request_model_tier("auto")
    try:
        assert choose_paid_model([
            {"role": "user", "content": "Investigate why light turned off"}
        ], "hybrid") == "deepseek-v4-pro"
    finally:
        reset_request_model_tier(token)


def test_claude_never_maps_to_ollama_paid_model():
    token = set_request_model_tier("claude")
    try:
        assert choose_paid_model([
            {"role": "user", "content": "Investigate why light turned off"}
        ], "paid") is None
    finally:
        reset_request_model_tier(token)


def test_ollama_function_schemas_convert_without_expanding_permissions():
    assert convert_tools(fixture_tools()) == [{
        "name": "hub_read_devices",
        "description": "Read Hubitat device",
        "input_schema": fixture_tools()[0]["function"]["parameters"],
    }]
    assert convert_tools([{"type": "computer", "name": "execute"}]) == []


def test_messages_retain_authenticated_tool_use_ids_and_results():
    system, transcript = convert_messages([
        {"role": "system", "content": "Only read live evidence."},
        {"role": "user", "content": "Check device"},
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "toolu_test123",
            "function": {"name": "hub_read_devices", "arguments": {"deviceId": "7103"}},
        }]},
        {"role": "tool", "tool_name": "hub_read_devices",
         "content": '{"switch":"off"}'},
        {"role": "user", "content": "What does that mean?"},
    ])
    assert system == "Only read live evidence."
    assert transcript[1]["content"][0] == {
        "type": "tool_use", "id": "toolu_test123", "name": "hub_read_devices",
        "input": {"deviceId": "7103"},
    }
    assert transcript[2]["content"][0] == {
        "type": "tool_result", "tool_use_id": "toolu_test123",
        "content": '{"switch":"off"}',
    }
    assert transcript[3]["content"] == "What does that mean?"


def test_host_collected_read_never_becomes_fabricated_tool_provenance():
    _, messages = convert_messages([
        {"role": "tool", "tool_name": "hub_read_devices",
         "content": "Native logs returned 0 entries"},
        {"role": "user", "content": "Why?"},
    ])
    assert "HOST-REPORTED TOOL EVIDENCE" in messages[0]["content"]
    assert "tool_result" not in str(messages)


def test_partial_parallel_tool_results_are_closed_as_errors_in_one_user_turn():
    _, messages = convert_messages([
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "toolu_one", "function": {"name": "read_one", "arguments": {}}},
            {"id": "toolu_two", "function": {"name": "read_two", "arguments": {}}},
        ]},
        {"role": "tool", "tool_name": "read_one", "content": "success"},
        {"role": "user", "content": "Continue with what is verified"},
    ])
    assert len(messages) == 3
    assert len(messages[1]["content"]) == 2
    assert messages[1]["content"][0]["tool_use_id"] == "toolu_one"
    assert messages[1]["content"][1]["tool_use_id"] == "toolu_two"
    assert messages[1]["content"][1]["is_error"] is True


@pytest.mark.asyncio
async def test_claude_is_queried_only_when_selected_and_tool_calls_return_ollama_shape():
    client = PostClient([{
        "content": [
            {"type": "text", "text": "Checking current state."},
            {"type": "tool_use", "id": "toolu_live", "name": "hub_read_devices",
             "input": {"deviceId": "7103"}},
        ],
        "stop_reason": "tool_use",
    }])
    transport = ChatTransport(
        "ollama-secret", "gemma4:31b", client=client,
        claude_api_key="anthropic-secret", claude_model="claude-sonnet-4-6",
        paid_routing_enabled=True,
    )
    tier = set_request_model_tier("claude")
    try:
        response = await transport.chat(
            [{"role": "system", "content": "Read-only."},
             {"role": "user", "content": "Check device 7103"}],
            fixture_tools(),
        )
    finally:
        reset_request_model_tier(tier)
    assert response["content"] == "Checking current state."
    assert response["tool_calls"][0] == {
        "id": "toolu_live",
        "function": {"name": "hub_read_devices", "arguments": {"deviceId": "7103"}},
    }
    assert len(client.calls) == 1
    url, request = client.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert request["headers"]["x-api-key"] == "anthropic-secret"
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in request["headers"]
    assert request["json"]["model"] == "claude-sonnet-4-6"
    assert request["json"]["system"] == "Read-only."
    assert request["json"]["tools"][0]["name"] == "hub_read_devices"


@pytest.mark.asyncio
async def test_non_claude_free_selection_never_contacts_anthropic():
    client = PostClient([{"message": {"role": "assistant", "content": "Free result"}}])
    transport = ChatTransport(
        "ollama-key", client=client, claude_api_key="anthropic-key",
        paid_routing_enabled=True, paid_routing_mode="paid",
    )
    result = await transport.chat([{"role": "user", "content": "Investigate why"}], [])
    assert result["content"] == "Free result"
    assert len(client.calls) == 1
    assert client.calls[0][0] == "https://ollama.com/api/chat"
    assert client.calls[0][1]["json"]["model"] == "gemma4:31b"


@pytest.mark.asyncio
async def test_missing_claude_credentials_fail_closed_without_ollama_fallback():
    client = PostClient()
    transport = ChatTransport("ollama-key", client=client)
    token = set_request_model_tier("claude")
    try:
        with pytest.raises(PaidModelUnavailable, match="Claude API key"):
            await transport.chat([{"role": "user", "content": "Check it"}], [])
    finally:
        reset_request_model_tier(token)
    assert client.calls == []


@pytest.mark.asyncio
async def test_claude_http_failure_does_not_fallback_to_free_or_deepseek():
    class FailingClient:
        def __init__(self):
            self.urls = []

        async def post(self, url, **kwargs):
            self.urls.append(url)
            request = httpx.Request("POST", url)
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError(
                "Rate limited", request=request, response=response,
            )
    client = FailingClient()
    transport = ChatTransport(
        "ollama-key", client=client, claude_api_key="anthropic-key",
        paid_routing_enabled=True,
        local_base_url="http://localhost:11434", local_model_name="qwen3:4b",
    )
    token = set_request_model_tier("claude")
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await transport.chat([{"role": "user", "content": "Explain"}], [])
    finally:
        reset_request_model_tier(token)
    assert client.urls == ["https://api.anthropic.com/v1/messages"]


@pytest.mark.asyncio
async def test_claude_cancellation_propagates_without_retry_or_other_provider():
    class Waiting:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()
            self.urls = []
        async def post(self, url, **kwargs):
            self.urls.append(url)
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise

    client = Waiting()
    transport = ChatTransport(
        "ollama-key", client=client, claude_api_key="anthropic-key",
    )
    token = set_request_model_tier("claude")
    try:
        task = asyncio.create_task(
            transport.chat([{"role": "user", "content": "Investigate"}], [])
        )
        await asyncio.wait_for(client.started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        reset_request_model_tier(token)
    assert client.cancelled.is_set()
    assert len(client.urls) == 1


def test_response_accounting_for_anthropic_paid_rounds():
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="Source read; cause unresolved.", choices=[], evidence=[],
        confirmation_required=False, confirmation_count=0,
        investigation_coverage=None,
        metrics={"outcome": "unresolved", "counters": {"paid_model_requested": 1},
                 "timings_ms": {}, "model_round_details": [
                     {"model": "claude-sonnet-4-6", "provider": "anthropic"},
                     {"model": "claude-sonnet-4-6", "provider": "anthropic"},
                 ]},
    )
    result = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=10, version="0.18.28",
    )
    assert result["model_usage"]["paid_rounds"] == 2
    assert result["model_usage"]["free_rounds"] == 0
    assert result["model_usage"]["charges_controlled_by"] == "anthropic-account"
    assert result["paid_routing"]["used"] is True
    assert result["model"] == "claude-sonnet-4-6"
