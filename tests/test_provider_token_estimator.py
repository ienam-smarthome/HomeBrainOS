from __future__ import annotations

import math
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


def test_character_ceiling_is_more_conservative_than_the_raw_byte_budget() -> None:
    """chars_for_token_budget() must not treat a UTF-8 byte budget as a
    literal Python character count -- non-ASCII text can run 2-4 bytes per
    character, so a naive 1:1 mapping would let truncated non-ASCII-heavy
    text exceed the intended token budget in real UTF-8 bytes.
    """

    estimator = ProviderTokenEstimator("qwen3")
    token_budget = 1000
    raw_byte_budget = math.floor(token_budget * estimator.bytes_per_token)

    char_ceiling = estimator.chars_for_token_budget(token_budget)

    # The naive (pre-fix) behaviour returned the raw byte budget itself as
    # the character ceiling -- a 1:1 byte-to-char mapping that only holds
    # for pure ASCII text. The fixed estimate must be strictly smaller so
    # that non-ASCII-heavy text (2+ bytes/char) has a safety margin instead
    # of silently being allowed to exceed the intended token budget.
    assert char_ceiling < raw_byte_budget
    assert char_ceiling == math.floor(raw_byte_budget / estimator._MIN_BYTES_PER_CHAR)


def test_character_ceiling_scales_with_token_budget() -> None:
    estimator = ProviderTokenEstimator("mistral")

    assert estimator.chars_for_token_budget(0) == 0
    assert estimator.chars_for_token_budget(200) > estimator.chars_for_token_budget(100)
