from __future__ import annotations

import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from model_context_policy import ModelContextPolicy  # noqa: E402


def test_history_keeps_newest_messages_inside_shared_character_budget():
    policy = ModelContextPolicy(
        max_history_messages=4,
        max_history_chars=110,
    )
    history = [
        {
            "role": "assistant" if index % 2 else "user",
            "content": f"{index:02d}" + "x" * 38,
        }
        for index in range(10)
    ]

    bounded = policy.history(history)

    assert len(bounded) == 3
    assert bounded[-1]["content"].startswith("09")
    assert bounded[0]["content"].startswith("07")
    assert bounded[0]["content"].endswith("[earlier history truncated]")
    assert sum(len(item["content"]) for item in bounded) <= 110
    assert history[7]["content"] == "07" + "x" * 38


def test_history_accepts_model_dump_items_and_normalises_roles():
    class Message:
        def __init__(self, role: str, text: str) -> None:
            self.role = role
            self.text = text

        def model_dump(self):
            return {"role": self.role, "text": self.text}

    policy = ModelContextPolicy()

    assert policy.history([
        Message("model", "answer"),
        Message("unexpected", "question"),
    ]) == [
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "question"},
    ]


def test_zero_history_budget_disables_prior_conversation():
    assert ModelContextPolicy(
        max_history_messages=0,
    ).history([{"role": "user", "content": "ignored"}]) == []
    assert ModelContextPolicy(
        max_history_chars=0,
    ).history([{"role": "user", "content": "ignored"}]) == []


def test_tool_context_compacts_oldest_results_without_mutating_input():
    policy = ModelContextPolicy(
        max_tool_context_chars=4000,
        compacted_tool_result_chars=500,
    )
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "original question"},
        {"role": "tool", "tool_name": "first", "content": "a" * 2500},
        {"role": "tool", "tool_name": "second", "content": "b" * 2500},
        {"role": "tool", "tool_name": "latest", "content": "c" * 1000},
    ]

    bounded = policy.bounded_messages(messages)
    tool_messages = [item for item in bounded if item["role"] == "tool"]

    assert sum(len(item["content"]) for item in tool_messages) <= 4000
    assert json.loads(tool_messages[0]["content"])["context_compacted"] is True
    assert tool_messages[-1]["content"] == "c" * 1000
    assert messages[2]["content"] == "a" * 2500


def test_compacted_content_is_valid_labelled_json_at_normal_size():
    compacted = ModelContextPolicy.compact_tool_content("x" * 1000, 300)
    payload = json.loads(compacted)

    assert len(compacted) <= 300
    assert payload["context_compacted"] is True
    assert payload["original_chars"] == 1000
    assert payload["result_excerpt"]


def test_context_limits_are_sanitised_once_by_policy():
    policy = ModelContextPolicy(
        max_history_messages=-1,
        max_history_chars=-1,
        max_tool_context_chars=10,
        compacted_tool_result_chars=9999,
    )

    assert policy.max_history_messages == 0
    assert policy.max_history_chars == 0
    assert policy.max_tool_context_chars == 4000
    assert policy.compacted_tool_result_chars == 2000
