"""Per-round provider latency accounting, no request payloads or secrets.

These are synthetic transport replies. We cannot infer production provider
round times from historical total-only screenshots.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from chat_transport import ChatTransport
from request_metrics import RequestMetrics, record_active_provider_model


class FakeReply:
    def __init__(self, msg):
        self.msg = msg

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": self.msg}


class FakePostClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.sent = []

    async def post(self, url, **kwargs):
        self.sent.append((url, kwargs))
        response = next(self.replies)
        if isinstance(response, Exception):
            raise response
        return FakeReply(response)


@pytest.mark.asyncio
async def test_successful_native_tool_and_final_rounds_are_timed_without_content():
    secret = "prompt-secret-should-not-leak"
    client = FakePostClient([
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "hub_read_devices",
                          "arguments": {"secret": "private-token"}}}
        ]},
        {"role": "assistant", "content": "private-final-response"},
    ])
    transport = ChatTransport(
        "Bearer-key-secret", "gemma4:31b",
        base_url="https://ollama.example", client=client,
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        tools = [{
            "type": "function", "function": {
                "name": "hub_read_devices", "parameters": {"type": "object"}
            }
        }]
        first = await transport.chat(
            [{"role": "user", "content": secret}], tools,
        )
        second = await transport.chat(
            [{"role": "user", "content": secret}], [],
        )
        rows = metrics.snapshot()["model_round_details"]
    finally:
        metrics.reset(token)
    assert first["tool_calls"] and second["content"] == "private-final-response"
    assert len(rows) == 2
    assert all(x["model"] == "gemma4:31b" for x in rows)
    assert all(x["provider"] == "ollama-cloud" for x in rows)
    assert all(type(x["elapsed_ms"]) is int and x["elapsed_ms"] >= 0 for x in rows)
    assert rows[0]["tool_call_count"] == 1
    assert rows[0]["result_kind"] == "tool_calls"
    assert rows[0]["declared_tool_count"] == 1
    assert rows[1]["tool_call_count"] == 0
    assert rows[1]["result_kind"] == "answer"
    assert rows[1]["declared_tool_count"] == 0
    assert "private" not in str(rows)
    assert "secret" not in str(rows)
    assert "hub_read_devices" not in str(rows)
    assert "Bearer-key-secret" not in str(rows)


@pytest.mark.asyncio
async def test_failed_round_does_not_record_a_successful_provider_round():
    client = FakePostClient([RuntimeError("connection failed")])
    transport = ChatTransport(
        "secret", "gemma4:31b",
        base_url="https://ollama.example", client=client,
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        with pytest.raises(RuntimeError):
            await transport.chat([{"role": "user", "content": "test"}], [])
        snapshot = metrics.snapshot()
    finally:
        metrics.reset(token)
    assert snapshot.get("model_round_details") is None


def test_privacy_bounds_and_backwards_compatible_model_metadata():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        record_active_provider_model("gemma4:31b", "ollama-cloud")
        record_active_provider_model(
            "gemma4:31b", "ollama-cloud",
            elapsed_ms=-1,
            tool_call_count=1000,
            declared_tool_count=-1,
        )
        record_active_provider_model(
            "gemma4:31b", "ollama-cloud",
            elapsed_ms=123.6, tool_call_count=0, declared_tool_count=3,
        )
        rows = metrics.snapshot()["model_round_details"]
    finally:
        metrics.reset(token)
    assert rows[0] == {"model": "gemma4:31b", "provider": "ollama-cloud"}
    assert rows[1] == {"model": "gemma4:31b", "provider": "ollama-cloud"}
    assert rows[2] == {
        "model": "gemma4:31b", "provider": "ollama-cloud",
        "elapsed_ms": 124,
        "tool_call_count": 0,
        "result_kind": "answer",
        "declared_tool_count": 3,
    }


def test_model_round_details_cap_and_request_isolation():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        for _ in range(100):
            record_active_provider_model(
                "gemma4:31b", "ollama-cloud",
                elapsed_ms=12.2, tool_call_count=1,
                declared_tool_count=1,
            )
        rows = metrics.snapshot()["model_round_details"]
    finally:
        metrics.reset(token)
    assert len(rows) == 64
    again = metrics.begin()
    try:
        assert metrics.snapshot().get("model_round_details") is None
    finally:
        metrics.reset(again)


def test_both_supported_transports_emit_typed_successful_round_duration():
    transport = (APP / "chat_transport.py").read_text()
    other = (APP / "anthropic_transport.py").read_text()
    assert "record_round(answer)" in transport
    assert "elapsed_ms=(time.monotonic() - round_started) * 1000" in transport
    assert 'tool_call_count=len(calls)' in other
    assert "elapsed_ms=(time.monotonic() - started) * 1000" in other
