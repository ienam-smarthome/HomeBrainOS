"""Regressions for Ollama Cloud rate limiting (HTTP 429)."""
from __future__ import annotations

from pathlib import Path
import sys

import httpx
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from provider_rate_limit_policy import describe_ollama_rate_limit
from webui import render_page


def _status(code=429, headers=None, body="private-api-token=sensitive"):
    request = httpx.Request("POST", "https://ollama.com/api/chat")
    response = httpx.Response(code, headers=headers or {}, text=body, request=request)
    return httpx.HTTPStatusError("HTTP error with sensitive payload", request=request, response=response)


def test_429_diagnostic_no_credentials_or_provider_payload():
    message, retry = describe_ollama_rate_limit(_status())
    assert retry is None
    assert "Ollama Cloud" in message and "429" in message
    assert "usage credits" in message and "provider queue" in message
    assert "private-api-token" not in message
    assert "sensitive" not in message
    assert "https://ollama.com/api/chat" not in message


@pytest.mark.parametrize("value,expected", [
    ("120", "120"), ("0", None), ("3601", None), ("nan", None),
    ("Wed, 21 Oct 2026 10:00:00 GMT", None), ("10\nX-Token: secret", None),
])
def test_retry_after_accepts_only_bounded_seconds(value, expected):
    detail, retry = describe_ollama_rate_limit(
        _status(headers={"Retry-After":value})
    )
    assert retry == expected
    assert "secret" not in detail
    if expected:
        assert f"{expected} seconds" in detail


def test_other_provider_status_not_mistaken_for_429():
    assert describe_ollama_rate_limit(_status(code=401)) is None
    assert describe_ollama_rate_limit(_status(code=503)) is None


def test_browser_does_not_save_provider_failure_as_assistant_message():
    page = render_page("HomeBrain", "0.17.88")
    assert "const data=await jsonResponse(response);if(!response.ok)throw new Error(" in page


@pytest.mark.asyncio
async def test_api_429_preserves_status_and_safe_message(monkeypatch):
    import app
    async def rejected():
        raise _status(headers={"Retry-After":"90"})
    async def request_op(_):
        return await rejected()
    monkeypatch.setattr(app, "_agent_request", request_op)
    monkeypatch.setitem(app.OPTIONS, "ollama_direct_cloud_enabled", True)
    async def passthrough(key, operation, **kwargs):
        return await operation
    monkeypatch.setattr(app.request_coordinator, "run", passthrough)
    with pytest.raises(HTTPException) as caught:
        await app._answer_result(app.ChatRequest(query="Investigate hallway light activity"))
    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After":"90"}
    assert "Ollama Cloud rejected" in caught.value.detail
    assert "private-api-token" not in caught.value.detail
