from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import mcp_client as mcp_client_module  # noqa: E402
from mcp_client import HubitatMCPClient  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


class FakeHTTP:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def aclose(self) -> None:
        return None


def json_response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", "http://hubitat.example/mcp"),
    )


def retryable_payload() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }


async def configured_client(outcomes: list[Any], *, backoff: float = 0) -> tuple[HubitatMCPClient, FakeHTTP]:
    client = HubitatMCPClient(
        "http://hubitat.example/mcp",
        retry_attempts=3,
        retry_backoff_seconds=backoff,
    )
    fake = FakeHTTP(outcomes)
    await client._http.aclose()
    client._http = fake
    return client, fake


@pytest.mark.asyncio
async def test_transport_error_retry_records_actual_attempt() -> None:
    client, fake = await configured_client([
        httpx.ConnectError("temporary failure"),
        json_response(200, {"jsonrpc": "2.0", "result": {}}),
    ])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        assert await client._post(retryable_payload()) == {"jsonrpc": "2.0", "result": {}}
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert fake.calls == 2
    assert snapshot["counters"]["mcp_retries"] == 1


@pytest.mark.asyncio
async def test_http_5xx_retry_records_actual_attempt() -> None:
    client, fake = await configured_client([
        json_response(503, {"error": "busy"}),
        json_response(200, {"jsonrpc": "2.0", "result": {}}),
    ])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        await client._post(retryable_payload())
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    assert fake.calls == 2
    assert snapshot["counters"]["mcp_retries"] == 1
    assert {"label": "MCP retries", "value": "1"} in present_request_metrics(snapshot)


@pytest.mark.asyncio
async def test_cancellation_during_backoff_does_not_record_unstarted_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, fake = await configured_client(
        [httpx.ConnectError("temporary failure")],
        backoff=1,
    )
    sleep_started = asyncio.Event()

    async def blocking_sleep(_delay: float) -> None:
        sleep_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(mcp_client_module.asyncio, "sleep", blocking_sleep)
    metrics = RequestMetrics()
    token = metrics.begin()
    task = asyncio.create_task(client._post(retryable_payload()))
    try:
        await asyncio.wait_for(sleep_started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        snapshot = metrics.finish("cancelled")
    finally:
        metrics.reset(token)

    assert fake.calls == 1
    assert snapshot["counters"].get("mcp_retries", 0) == 0
