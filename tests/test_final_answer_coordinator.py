from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from final_answer_coordinator import (  # noqa: E402
    DEFAULT_FINAL_ANSWER,
    FINAL_ANSWER_INSTRUCTION,
    FinalAnswerCoordinator,
)


@pytest.mark.asyncio
async def test_final_answer_appends_instruction_and_disables_tools() -> None:
    calls: list[tuple[list[dict[str, object]], list[dict[str, object]]]] = []

    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"role": "assistant", "content": "The lamp is off."}

    original = [
        {"role": "user", "content": "Turn off the lamp"},
        {"role": "tool", "tool_name": "set_switch", "content": "off"},
    ]
    coordinator = FinalAnswerCoordinator(chat)

    answer = await coordinator.answer(original)

    assert answer == "The lamp is off."
    assert original == [
        {"role": "user", "content": "Turn off the lamp"},
        {"role": "tool", "tool_name": "set_switch", "content": "off"},
    ]
    sent_messages, sent_tools = calls[0]
    assert sent_messages[:-1] == original
    assert sent_messages[-1] == {
        "role": "user",
        "content": FINAL_ANSWER_INSTRUCTION,
    }
    assert sent_tools == []


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", None])
async def test_final_answer_uses_stable_fallback_for_empty_content(content) -> None:
    async def chat(_messages, _tools):
        return {"role": "assistant", "content": content}

    coordinator = FinalAnswerCoordinator(chat)

    assert await coordinator.answer([]) == DEFAULT_FINAL_ANSWER


@pytest.mark.asyncio
async def test_final_answer_propagates_provider_cancellation() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def chat(_messages, _tools):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    coordinator = FinalAnswerCoordinator(chat)
    task = asyncio.create_task(coordinator.answer([]))
    await asyncio.wait_for(started.wait(), timeout=1)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.wait_for(cancelled.wait(), timeout=1) is True


@pytest.mark.asyncio
async def test_failed_causal_repair_uses_bounded_source_only_fallback(monkeypatch):
    import final_answer_coordinator as coordinator_module

    calls = []

    async def chat(messages, _tools):
        calls.append(messages)
        return {"role": "assistant", "content":
                "A confident external initiator claim without proof."}

    def invalid(_message, _evidence, *, original_user="", causal=False):
        assert causal
        return "Still unsupported", ["causal_source_attribution"]

    monkeypatch.setattr(coordinator_module, "validate_synthesis", invalid)
    monkeypatch.setattr(
        coordinator_module, "render_failed_causal_synthesis",
        lambda _evidence, _prompt: (
            "The requested state event was observed; "
            "its initiating controller remains unverified."
        ),
    )
    agent = FinalAnswerCoordinator(chat, evidence_supplier=lambda: [])
    answer = await agent.answer([
        {"role": "user",
         "content": "Why did Livingroom Light 1 switch on at 19:55?"}
    ])
    assert len(calls) == 2
    assert "initiating controller remains unverified" in answer
    assert "confident external" not in answer
