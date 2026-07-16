from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_fast import OllamaUnavailable  # noqa: E402
from ollama_agent_final_answer import FinalAnswerNaturalAgent  # noqa: E402


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class CapturingHTTP:
    def __init__(self, body):
        self.body = body
        self.payload = None

    async def post(self, _url, *, json, timeout):
        self.payload = json
        return FakeResponse(self.body)



def make_agent() -> FinalAnswerNaturalAgent:
    return FinalAnswerNaturalAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
        planner_model="qwen3:4b",
        routine_model="qwen3:4b",
    )


def test_structured_final_answer_is_unwrapped_and_thinking_removed():
    agent = make_agent()
    http = CapturingHTTP(
        {
            "done": True,
            "done_reason": "stop",
            "message": {
                "role": "assistant",
                "thinking": "private chain of thought",
                "content": '{"answer":"Three lights are on, and two batteries are low."}',
            },
        }
    )
    agent._http = http

    body = asyncio.run(
        agent._chat(
            model="qwen3:4b",
            messages=[
                {"role": "system", "content": "Use verified Hubitat evidence."},
                {"role": "user", "content": "What's happening at home?"},
            ],
            tools=None,
            timeout_seconds=20,
            num_ctx=2048,
            num_predict=120,
            temperature=0.2,
        )
    )

    assert body["message"]["content"] == (
        "Three lights are on, and two batteries are low."
    )
    assert "thinking" not in body["message"]
    assert http.payload["think"] is False
    assert http.payload["format"]["required"] == ["answer"]
    assert http.payload["options"]["temperature"] == 0
    assert "/no_think" in http.payload["messages"][0]["content"]


def test_reasoning_leak_is_rejected_even_inside_valid_json():
    body = {
        "done_reason": "stop",
        "message": {
            "content": (
                '{"answer":"Okay, the user asked what is happening. '
                'First, I need to parse the evidence."}'
            )
        },
    }
    with pytest.raises(OllamaUnavailable, match="internal reasoning"):
        FinalAnswerNaturalAgent._extract_final_answer(body, require_json=True)


def test_truncated_final_answer_is_rejected():
    body = {
        "done_reason": "length",
        "message": {"content": '{"answer":"The active rules are"}'},
    }
    with pytest.raises(OllamaUnavailable, match="truncated"):
        FinalAnswerNaturalAgent._extract_final_answer(body, require_json=True)


def test_previous_leaked_reasoning_is_removed_from_history():
    messages = FinalAnswerNaturalAgent._final_only_messages(
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is the weather?"},
            {
                "role": "assistant",
                "content": "The user asked about weather. Let me parse the evidence.",
            },
            {"role": "user", "content": "And tomorrow?"},
        ]
    )

    assert all(
        "let me parse" not in str(item.get("content") or "").lower()
        for item in messages
    )
    assert messages[-1]["content"] == "And tomorrow?"
    assert "/no_think" in messages[0]["content"]


def test_plain_compatibility_output_strips_think_block():
    body = {
        "done_reason": "stop",
        "message": {
            "content": (
                "<think>I should inspect the evidence.</think>"
                "The weather is clear at 22°C with no rain expected."
            )
        },
    }
    assert FinalAnswerNaturalAgent._extract_final_answer(
        body,
        require_json=False,
    ) == "The weather is clear at 22°C with no rain expected."
