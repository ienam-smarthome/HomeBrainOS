from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import httpx
import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from chat_transport import ChatTransport  # noqa: E402
from mcp_client import HubitatMCPClient  # noqa: E402


def load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


@pytest.mark.asyncio
async def test_handler_cancellation_propagates_to_backend_operation(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def operation():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    request_task = asyncio.create_task(
        module.request_coordinator.run("handler-cancel", operation())
    )
    await asyncio.wait_for(started.wait(), timeout=1)

    request_task.cancel("test handler cancellation")
    with pytest.raises(asyncio.CancelledError):
        await request_task

    assert await asyncio.wait_for(cancelled.wait(), timeout=1) is True
    assert "handler-cancel" not in module.request_coordinator._tasks


@pytest.mark.asyncio
async def test_application_shutdown_cancels_all_registered_operations(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    started = [asyncio.Event(), asyncio.Event()]
    cancelled = [asyncio.Event(), asyncio.Event()]

    async def operation(index: int):
        started[index].set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled[index].set()
            raise

    tasks = [
        asyncio.create_task(module.request_coordinator.run(f"session-{index}", operation(index)))
        for index in range(2)
    ]
    await asyncio.gather(*(asyncio.wait_for(event.wait(), timeout=1) for event in started))

    await module.request_coordinator.close()

    for task in tasks:
        with pytest.raises(asyncio.CancelledError):
            await task
    assert all(event.is_set() for event in cancelled)
    assert module.request_coordinator._tasks == {}


class BlockingPostClient:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def post(self, *args, **kwargs):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_ollama_post_cancellation_reaches_http_client():
    client = BlockingPostClient()
    transport = ChatTransport(
        api_key="test-key",
        model_name="test-model",
        client=client,
    )

    chat_task = asyncio.create_task(transport.chat([{"role": "user", "content": "hi"}], []))
    await asyncio.wait_for(client.started.wait(), timeout=1)

    chat_task.cancel("request superseded")
    with pytest.raises(asyncio.CancelledError):
        await chat_task

    assert await asyncio.wait_for(client.cancelled.wait(), timeout=1) is True


class FailingHTTP:
    def __init__(self) -> None:
        self.calls = 0
        self.first_attempt = asyncio.Event()

    async def post(self, url, **kwargs):
        self.calls += 1
        self.first_attempt.set()
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("hub unavailable", request=request)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_mcp_cancellation_during_retry_backoff_prevents_another_attempt():
    client = HubitatMCPClient(
        "http://hub/mcp",
        retry_attempts=3,
        retry_backoff_seconds=5,
    )
    await client._http.aclose()
    fake = FailingHTTP()
    client._http = fake

    request_task = asyncio.create_task(
        client._post({"jsonrpc": "2.0", "method": "tools/list", "params": {}})
    )
    await asyncio.wait_for(fake.first_attempt.wait(), timeout=1)
    await asyncio.sleep(0)

    request_task.cancel("client disconnected")
    with pytest.raises(asyncio.CancelledError):
        await request_task

    assert fake.calls == 1
