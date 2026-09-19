from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from request_classification import parse_current_time_intent  # noqa: E402


class FakeMCP:
    pass


class FakeAI:
    def __init__(self) -> None:
        self.requests = []

    async def post(self, *_args, **kwargs):
        self.requests.append(kwargs)
        raise AssertionError("current-time questions must not reach the model")

    async def aclose(self) -> None:
        return None


@pytest.mark.parametrize(
    "prompt",
    [
        "what's the time?",
        "What time is it?",
        "current time",
        "Tell me the current time please",
        "time please",
    ],
)
def test_current_time_intent_matches_direct_questions(prompt: str) -> None:
    assert parse_current_time_intent(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "What time did Bedroom 2 Light turn on?",
        "Set the light at 7 pm",
        "What is the timer status?",
        "When was the last motion event?",
    ],
)
def test_current_time_intent_does_not_hijack_other_time_questions(prompt: str) -> None:
    assert parse_current_time_intent(prompt) is False


@pytest.mark.asyncio
async def test_current_time_uses_hub_timezone_without_model_round() -> None:
    ai = FakeAI()
    agent = UnifiedMCPAgent(FakeMCP(), "key", ai_client=ai)

    async def fixed_now(_factory):
        return (
            datetime(2026, 9, 19, 18, 6, tzinfo=ZoneInfo("Europe/London")),
            "Europe/London",
            "hub_get_info_cache",
        )

    agent.hub_timezone.now_in_hub_timezone = fixed_now

    outcome = await agent.process_user_request_result(
        "what's the time?", session_id="current-time-test"
    )

    assert outcome.message == "It's 6:06 PM BST."
    assert outcome.request_class == "live-read"
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0
    assert ai.requests == []
