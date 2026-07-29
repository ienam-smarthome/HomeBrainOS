from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


@pytest.mark.asyncio
async def test_new_request_cancels_previous_backend_task(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    first_started = asyncio.Event()
    first_cancelled = asyncio.Event()
    release_second = asyncio.Event()

    async def first_operation():
        first_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            first_cancelled.set()
            raise

    async def second_operation():
        await release_second.wait()
        return "second"

    first = asyncio.create_task(module.request_coordinator.run("session", first_operation()))
    await asyncio.wait_for(first_started.wait(), timeout=1)
    second = asyncio.create_task(module.request_coordinator.run("session", second_operation()))

    await asyncio.wait_for(first_cancelled.wait(), timeout=1)
    release_second.set()

    with pytest.raises(asyncio.CancelledError):
        await first
    assert await asyncio.wait_for(second, timeout=1) == "second"


@pytest.mark.asyncio
async def test_client_disconnect_cancels_backend_task(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    operation_started = asyncio.Event()
    operation_cancelled = asyncio.Event()

    class DisconnectedRequest:
        async def is_disconnected(self):
            return True

    async def operation():
        operation_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            operation_cancelled.set()
            raise

    with pytest.raises(module.HTTPException) as error:
        await module.request_coordinator.run(
            "disconnect-session",
            operation(),
            connection=DisconnectedRequest(),
        )

    assert error.value.status_code == 499
    assert await asyncio.wait_for(operation_started.wait(), timeout=1) is True
    assert await asyncio.wait_for(operation_cancelled.wait(), timeout=1) is True


@pytest.mark.asyncio
async def test_coordinator_cleanup_removes_completed_task(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)

    result = await module.request_coordinator.run("clean-session", asyncio.sleep(0, result=42))

    assert result == 42
    assert "clean-session" not in module.request_coordinator._tasks
