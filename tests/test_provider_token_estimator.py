from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from provider_token_estimator import ProviderTokenEstimator  # noqa: E402


def test_empty_text_estimates_zero_tokens() -> None:
    estimate = ProviderTokenEstimator("gemma4:31b").estimate_text("")

    assert estimate.tokens == 0
    assert estimate.utf8_bytes == 0
    assert estimate.profile == "gemma"
    assert estimate.approximate is True


def test_known_model_families_select_stable_profiles() -> None:
    assert ProviderTokenEstimator("qwen3.5:9b").profile == "qwen"
    assert ProviderTokenEstimator("gemma4:31b-cloud").profile == "gemma"
    assert ProviderTokenEstimator("llama3.2:3b").profile == "llama"
    assert ProviderTokenEstimator("mistral-small").profile == "mistral"
    assert ProviderTokenEstimator("unknown-model").profile == "default"


def test_utf8_content_is_counted_by_bytes_not_python_characters() -> None:
    estimator = ProviderTokenEstimator("qwen3.5")
    ascii_estimate = estimator.estimate_text("home")
    unicode_estimate = estimator.estimate_text("家家家家")

    assert unicode_estimate.utf8_bytes > ascii_estimate.utf8_bytes
    assert unicode_estimate.tokens > ascii_estimate.tokens


def test_message_estimate_includes_structural_allowance() -> None:
    estimator = ProviderTokenEstimator("gemma4")
    text = estimator.estimate_text("user\n\nHello")
    messages = estimator.estimate_messages([{"role": "user", "content": "Hello"}])

    assert messages.tokens == text.tokens + 4
    assert messages.profile == "gemma"


def test_character_ceiling_is_non_negative_and_profile_aware() -> None:
    qwen = ProviderTokenEstimator("qwen3")
    llama = ProviderTokenEstimator("llama3")

    assert qwen.chars_for_token_budget(-1) == 0
    assert llama.chars_for_token_budget(100) > qwen.chars_for_token_budget(100)
