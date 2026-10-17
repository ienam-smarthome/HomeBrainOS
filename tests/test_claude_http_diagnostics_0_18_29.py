"""Safe, actionable Anthropic HTTP errors without revealing prompt content."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from anthropic_transport import describe_anthropic_http_error


def rejection(status, message, *, error_type="invalid_request_error", retry_after=None):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    resp = httpx.Response(
        status, request=req, headers=headers,
        json={"type": "error", "error": {"type": error_type, "message": message}},
    )
    return httpx.HTTPStatusError("redacted upstream exception", request=req, response=resp)


@pytest.mark.parametrize("status,error_type,expected", [
    (400, "invalid_request_error", "invalid-request"),
    (401, "authentication_error", "authentication"),
    (402, "billing_error", "billing"),
    (403, "permission_error", "permission"),
    (404, "not_found_error", "model-unavailable"),
    (413, "invalid_request_error", "request-too-large"),
    (429, "rate_limit_error", "rate-limit"),
    (500, "api_error", "provider-unavailable"),
    (529, "overloaded_error", "provider-unavailable"),
])
def test_anthropic_http_errors_are_specific_and_never_echo_upstream_body(status, error_type, expected):
    private = "sk-ant-my-real-secret-Key user private email and automation content"
    code, msg, retry, parsed_type, category = describe_anthropic_http_error(
        rejection(status, private, error_type=error_type),
    )
    assert code == status
    assert f"HTTP {status}" in msg
    assert parsed_type == error_type
    assert category == expected
    assert private not in msg
    assert "sk-ant-" not in msg
    assert "No Ollama/Free fallback" in msg
    assert retry is None


@pytest.mark.parametrize("raw,category", [
    ("messages.2.tool_use ids were found without tool_result blocks immediately after", "tool-result-format"),
    ("tools.0.input_schema is invalid: secret sk-ant-abc", "tool-schema"),
    ("messages.4.content.1.text is too long", "message-format"),
    ("Model claude-sonnet-4-6 invalid param", "model-parameter"),
])
def test_400_categorization_is_safe_and_helps_identify_transcript_mismatches(raw, category):
    _, msg, _, _, returned = describe_anthropic_http_error(
        rejection(400, raw),
    )
    assert returned == category
    assert "sk-ant-abc" not in msg
    assert raw not in msg


def test_retry_after_is_only_retained_for_safe_bounded_integer_value():
    _, _, retry, _, _ = describe_anthropic_http_error(
        rejection(429, "limit exceeded", error_type="rate_limit_error", retry_after=19),
    )
    assert retry == "19"
    for raw in ["../../password", "86401", "3 seconds"]:
        _, _, retry, _, _ = describe_anthropic_http_error(
            rejection(429, "limit exceeded", error_type="rate_limit_error", retry_after=raw),
        )
        assert retry is None


def test_malformed_upstream_error_format_is_still_classified_safely():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    res = httpx.Response(400, request=req, text="Private user message: secret")
    exc = httpx.HTTPStatusError("bad", request=req, response=res)
    status, text, _, typ, category = describe_anthropic_http_error(exc)
    assert (status, typ, category) == (400, "unknown", "invalid-request")
    assert "Private user message" not in text


@pytest.mark.parametrize("status,category", [
    (400, "tool-schema"),
    (401, "authentication"),
    (429, "rate-limit"),
])
def test_homebrain_api_exposes_safe_claude_status_without_generic_502(
    monkeypatch, tmp_path, status, category,
):
    import importlib
    from fastapi.testclient import TestClient
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")

    async def reject(_request):
        raise rejection(
            status,
            "tools.0.input_schema includes token sk-ant-secret and address",
            error_type="invalid_request_error" if status == 400
                       else "authentication_error" if status == 401
                       else "rate_limit_error",
        )
    monkeypatch.setattr(module, "_agent_request", reject)

    with TestClient(module.app) as client:
        response = client.post("/api/ask", json={
            "query": "Investigate why Bedroom 1 light switched on yesterday?",
            "session_id": f"http-classification-{status}",
            "model_tier": "claude",
        })
    assert response.status_code == status
    detail = response.json()["detail"]
    assert f"HTTP {status}" in detail
    assert f"category={category}" in detail
    assert "sk-ant-secret" not in detail
    assert "Hubitat and MCP may remain available" not in detail
