"""Zero-inference connection diagnostics, HTTP access errors and UI boundaries."""
from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rootfs" / "app"
sys.path.insert(0, str(APP))

from cloud_connection_diagnostics import CloudConnectionDiagnostics  # noqa: E402
from stage6_adaptive_benchmark import _safe_stage6_error  # noqa: E402
from cloud_benchmark import BenchmarkError  # noqa: E402
from webui import render_page  # noqa: E402


def sync(awaitable):
    return asyncio.run(awaitable)


class SafeClient:
    def __init__(self, status=200, error=None):
        self.status = status
        self.error = error
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return httpx.Response(
            self.status,
            request=httpx.Request("GET", url),
            text='{"secret":"private-token-key","included":"private-account-info"}',
        )


class FakePrimaryTransport:
    def __init__(self, status=200, error=None):
        self.api_key = "private-token-key"
        self.base_url = "https://ollama.com"
        self.model_name = "gemma4:31b"
        self.client = SafeClient(status=status, error=error)
        self.cloud_inference_calls = []

    @property
    def configured(self):
        return True

    async def _chat_post(self, *args, **kwargs):
        self.cloud_inference_calls.append((args, kwargs))
        raise AssertionError("diagnostic must never invoke model inference")

    async def close(self):
        return None


@pytest.mark.parametrize("code,category", [
    (200, "account_key_accepted"),
    (401, "unauthorized"),
    (402, "payment_required"),
    (403, "access_denied"),
    (404, "check_endpoint_unavailable"),
    (429, "provider_rate_limited"),
    (503, "provider_server_error"),
    (418, "other_provider_response"),
])
def test_provider_status_code_preserved_without_body_or_credit_details(code, category):
    model = FakePrimaryTransport(code)
    out = sync(CloudConnectionDiagnostics().check(model))
    assert out["http_status"] == code
    assert out["category"] == category
    assert out["model_inference_requests"] == 0
    assert out["no_token_balance_or_account_details_exposed"] is True
    assert out["diagnostic_is_not_chat_authorization_proof"] is True
    assert not model.cloud_inference_calls
    assert len(model.client.calls) == 1
    uri, kwargs = model.client.calls[0]
    assert uri == "https://ollama.com/api/balance"
    assert kwargs["headers"]["Authorization"] == "Bearer private-token-key"
    assert kwargs["follow_redirects"] is False
    assert "private-token-key" not in json.dumps(out)
    assert "private-account-info" not in json.dumps(out)
    if code == 403:
        assert "does not prove the key is invalid" in out["guidance"]


@pytest.mark.parametrize("error,category", [
    (httpx.ReadTimeout("private-token-key"), "connection_timeout"),
    (httpx.ConnectError("private-token-key"), "network_error"),
    (RuntimeError("private-token-key"), "unexpected_error"),
])
def test_network_errors_sanitized_and_no_retries(error, category):
    model = FakePrimaryTransport(error=error)
    result = sync(CloudConnectionDiagnostics().check(model))
    assert result["category"] == category
    assert result["http_status"] is None
    assert "private-token-key" not in json.dumps(result)
    assert len(model.client.calls) == 1
    assert not model.cloud_inference_calls


def test_not_configured_or_nonofficial_endpoint_makes_no_network_request():
    model = FakePrimaryTransport()
    model.base_url = "http://localhost:11434"
    with pytest.raises(BenchmarkError) as exc:
        sync(CloudConnectionDiagnostics().check(model))
    assert exc.value.status == 503
    assert model.client.calls == []
    model.base_url = "https://ollama.com"
    model.api_key = ""
    with pytest.raises(BenchmarkError):
        sync(CloudConnectionDiagnostics().check(model))
    assert model.client.calls == []


def test_limit_and_cooldown_apply_without_model_usage():
    ticks = iter(range(100, 1000, 11))
    checker = CloudConnectionDiagnostics(clock=lambda: next(ticks))
    transport = FakePrimaryTransport()
    for _ in range(6):
        result = sync(checker.check(transport))
        assert result["http_status"] == 200
    with pytest.raises(BenchmarkError) as exc:
        sync(checker.check(transport))
    assert exc.value.status == 429
    assert len(transport.client.calls) == 6
    assert transport.cloud_inference_calls == []


@pytest.mark.parametrize("code,text", [
    (401, "key not accepted"),
    (403, "provider access denied"),
])
def test_stage6_chat_access_rejections_are_distinct_and_safe(code, text):
    request = httpx.Request("POST", "https://ollama.com/api/chat")
    response = httpx.Response(code, request=request, text="private-token-key provider details")
    exc = httpx.HTTPStatusError(
        "private-token-key", request=request, response=response)
    error = _safe_stage6_error(exc, "adaptive evidence selection")
    assert error.status == 502
    assert f"HTTP {code}" in error.detail
    assert text in error.detail
    assert "private-token-key" not in error.detail
    assert "No retry" in error.detail


def test_authenticated_dashboard_route_is_manual_json_same_origin(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "absent.json"))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    model = FakePrimaryTransport()
    monkeypatch.setattr(module.agent, "transport", model)
    with TestClient(module.app) as client:
        assert client.get("/api/cloud-connection/check").status_code == 405
        assert client.post("/api/cloud-connection/check", json={}).status_code == 403
        assert client.post("/api/cloud-connection/check", json={},
                           headers={"X-HomeBrain-Benchmark": "confirmed",
                                    "Origin": "https://malicious.example"}).status_code == 403
        assert model.client.calls == []
        checked = client.post("/api/cloud-connection/check", json={},
                              headers={"X-HomeBrain-Benchmark": "confirmed",
                                       "Origin": "http://testserver"})
        assert checked.status_code == 200, checked.text
        assert checked.json()["category"] == "account_key_accepted"
        assert checked.json()["model_inference_requests"] == 0
        assert len(model.client.calls) == 1
        assert not model.cloud_inference_calls


def test_ui_does_not_auto_prove_ready_or_start_balance_check():
    html = render_page("HomeBrainOS", "0.18.297")
    assert "Check cloud connection (no AI request)" in html
    assert 'id="checkCloudConnection"' in html
    assert "api/cloud-connection/check" in html
    assert "Configured (not yet authenticated)" in html
    assert "No model inference was requested" in html
    assert "output.textContent" in html


def test_publisher_and_device_paths_unaffected():
    for file in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "cloud_connection_diagnostics" not in (APP / file).read_text()
