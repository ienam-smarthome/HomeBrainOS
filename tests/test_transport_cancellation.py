from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from chat_transport import ChatTransport  # noqa: E402
from mcp_client import HubitatMCPClient  # noqa: E402


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "message": {
                "role": "assistant",
                "content": "replacement complete",
            }
        }


class SupersedingPostClient:
    def __init__(self) -> None:
        self.calls = 0
        self.first_started = asyncio.Event()
        self.first_cancelled = asyncio.Event()

    async def post(self, _url: str, **_kwargs: object) -> FakeResponse:
        self.calls += 1
        if self.calls == 1:
            self.first_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.first_cancelled.set()
                raise
        return FakeResponse()

    async def aclose(self) -> None:
        return None


class BlockingStreamResponse:
    def __init__(self) -> None:
        self.iteration_started = asyncio.Event()
        self.iteration_cancelled = asyncio.Event()

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        self.iteration_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.iteration_cancelled.set()
            raise
        yield ""


class BlockingStreamContext:
    def __init__(self, response: BlockingStreamResponse) -> None:
        self.response = response
        self.exited_with: type[BaseException] | None = None

    async def __aenter__(self) -> BlockingStreamResponse:
        return self.response

    async def __aexit__(self, exc_type, _exc, _tb) -> None:
        self.exited_with = exc_type


class BlockingStreamClient:
    def __init__(self) -> None:
        self.response = BlockingStreamResponse()
        self.context = BlockingStreamContext(self.response)

    def stream(self, *_args: object, **_kwargs: object) -> BlockingStreamContext:
        return self.context

    async def aclose(self) -> None:
        return None


class BlockingMCPHTTP:
    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def post(self, *_args: object, **_kwargs: object):
        self.calls += 1
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise

    async def aclose(self) -> None:
        return None


def load_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


@pytest.mark.asyncio
async def test_superseding_request_cancels_active_ollama_post_and_replacement_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_app(monkeypatch, tmp_path)
    client = SupersedingPostClient()
    transport = ChatTransport("key", client=client)

    first = asyncio.create_task(
        module.request_coordinator.run(
            "transport-session",
            transport.chat([{"role": "user", "content": "first"}], []),
        )
    )
    await asyncio.wait_for(client.first_started.wait(), timeout=1)

    second = asyncio.create_task(
        module.request_coordinator.run(
            "transport-session",
            transport.chat([{"role": "user", "content": "second"}], []),
        )
    )

    await asyncio.wait_for(client.first_cancelled.wait(), timeout=1)
    with pytest.raises(asyncio.CancelledError):
        await first

    result = await asyncio.wait_for(second, timeout=1)
    assert result["content"] == "replacement complete"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_cancelling_ollama_stream_closes_active_stream_context() -> None:
    client = BlockingStreamClient()
    transport = ChatTransport("key", client=client)
    task = asyncio.create_task(
        transport.chat([{"role": "user", "content": "slow stream"}], [])
    )

    await asyncio.wait_for(client.response.iteration_started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.wait_for(client.response.iteration_cancelled.wait(), timeout=1)
    assert client.context.exited_with is asyncio.CancelledError


@pytest.mark.asyncio
async def test_cancelling_mcp_post_propagates_without_retry() -> None:
    client = HubitatMCPClient(
        "http://hubitat.example/mcp",
        retry_attempts=3,
        retry_backoff_seconds=0,
    )
    blocking_http = BlockingMCPHTTP()
    await client._http.aclose()
    client._http = blocking_http

    task = asyncio.create_task(
        client._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }
        )
    )
    await asyncio.wait_for(blocking_http.started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.wait_for(blocking_http.cancelled.wait(), timeout=1)
    assert blocking_http.calls == 1
