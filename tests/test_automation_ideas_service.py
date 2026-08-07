from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_ideas_service import suggest_new_automations  # noqa: E402


DEVICES = [
    {"id": "10", "label": "Hallway Motion", "capabilities": ["MotionSensor"]},
    {"id": "11", "label": "Front Door Lock", "capabilities": ["Lock"]},
]
AUTOMATION_ITEMS = [
    {"name": "Unrelated Rule", "display_name": "Unrelated Rule"},
]


@pytest.mark.asyncio
async def test_suggest_new_automations_returns_model_content_when_grounded():
    captured = {}

    async def fake_chat(messages, tools):
        captured["messages"] = messages
        captured["tools"] = tools
        return {"role": "assistant", "content": "Idea: Away mode using Front Door Lock."}

    result = await suggest_new_automations(fake_chat, AUTOMATION_ITEMS, DEVICES)

    assert result == "Idea: Away mode using Front Door Lock."
    # A plain, non-tool-calling round -- this must never trigger the
    # orchestrator's tool-calling loop or grounding policy.
    assert captured["tools"] == []
    system, user = captured["messages"]
    assert system["role"] == "system"
    assert "never as facts about the current state" in system["content"]
    assert "Hallway Motion" in user["content"]
    assert "Front Door Lock" in user["content"]
    assert "Unrelated Rule" in user["content"]


@pytest.mark.asyncio
async def test_suggest_new_automations_fails_closed_on_chat_error():
    async def failing_chat(messages, tools):
        raise RuntimeError("network down")

    result = await suggest_new_automations(failing_chat, AUTOMATION_ITEMS, DEVICES)

    assert result is None


@pytest.mark.asyncio
async def test_suggest_new_automations_returns_none_with_no_devices():
    async def unreachable_chat(messages, tools):
        raise AssertionError("must not call the model with no devices to ground it")

    result = await suggest_new_automations(unreachable_chat, AUTOMATION_ITEMS, [])

    assert result is None


@pytest.mark.asyncio
async def test_suggest_new_automations_returns_none_for_blank_response():
    async def blank_chat(messages, tools):
        return {"role": "assistant", "content": "   "}

    result = await suggest_new_automations(blank_chat, AUTOMATION_ITEMS, DEVICES)

    assert result is None
