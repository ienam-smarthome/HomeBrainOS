from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from model_context_policy import ModelContextPolicy  # noqa: E402
from token_aware_context_policy import TokenAwareModelContextPolicy  # noqa: E402


def test_token_ceiling_can_only_tighten_character_caps() -> None:
    policy = TokenAwareModelContextPolicy(
        model_name="gemma4:31b",
        max_history_chars=12000,
        max_tool_context_chars=48000,
    )

    assert policy.max_history_chars <= 12000
    assert policy.max_tool_context_chars <= 48000
    assert policy.configured_history_chars == 12000
    assert policy.configured_tool_context_chars == 48000


def test_explicit_large_token_budget_cannot_relax_character_caps() -> None:
    policy = TokenAwareModelContextPolicy(
        model_name="llama3",
        max_history_chars=1000,
        max_tool_context_chars=5000,
        history_token_budget=999999,
        tool_context_token_budget=999999,
    )

    assert policy.max_history_chars == 1000
    assert policy.max_tool_context_chars == 5000


def test_model_profiles_produce_distinct_conservative_limits() -> None:
    qwen = TokenAwareModelContextPolicy(
        model_name="qwen3.5",
        max_history_chars=12000,
        max_tool_context_chars=48000,
    )
    llama = TokenAwareModelContextPolicy(
        model_name="llama3",
        max_history_chars=12000,
        max_tool_context_chars=48000,
    )

    assert qwen.max_history_chars < llama.max_history_chars
    assert qwen.max_tool_context_chars < llama.max_tool_context_chars


def test_base_policy_contract_remains_unchanged() -> None:
    base = ModelContextPolicy(
        max_history_chars=12000,
        max_tool_context_chars=48000,
    )

    assert base.max_history_chars == 12000
    assert base.max_tool_context_chars == 48000
