from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from history_time_windows import active_history_window_request  # noqa: E402


@pytest.mark.asyncio
async def test_agent_request_binds_prompt_window_and_resets_after_completion(monkeypatch) -> None:
    seen: list[dict | None] = []

    async def fake_process(*args, **kwargs):
        seen.append(active_history_window_request())
        await asyncio.sleep(0)
        return SimpleNamespace(message="ok")

    monkeypatch.setattr(app_module.agent, "process_user_request_result", fake_process)
    request = app_module.ChatRequest(
        prompt="How long was Big lamp on last night?",
        session_id="semantic-window-test",
    )

    outcome = await app_module._agent_request(request)

    assert outcome.message == "ok"
    assert seen == [{"kind": "last_night", "label": "last night"}]
    assert active_history_window_request() is None


@pytest.mark.asyncio
async def test_parallel_agent_requests_keep_semantic_windows_isolated(monkeypatch) -> None:
    seen: dict[str, dict | None] = {}
    release = asyncio.Event()
    entered = 0

    async def fake_process(prompt, history, *, session_id):
        nonlocal entered
        entered += 1
        if entered == 2:
            release.set()
        await release.wait()
        await asyncio.sleep(0)
        seen[session_id] = active_history_window_request()
        return SimpleNamespace(message="ok")

    monkeypatch.setattr(app_module.agent, "process_user_request_result", fake_process)
    last_night = app_module.ChatRequest(
        prompt="How long was Big lamp on last night?",
        session_id="last-night",
    )
    yesterday = app_module.ChatRequest(
        prompt="How long was Big lamp on yesterday?",
        session_id="yesterday",
    )

    await asyncio.gather(
        app_module._agent_request(last_night),
        app_module._agent_request(yesterday),
    )

    assert seen["last-night"] == {"kind": "last_night", "label": "last night"}
    assert seen["yesterday"] == {"kind": "yesterday", "label": "yesterday"}
    assert active_history_window_request() is None
