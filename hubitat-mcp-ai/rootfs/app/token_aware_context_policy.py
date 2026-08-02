"""Production context policy that adds conservative token ceilings.

Character limits remain the hard deterministic caps. Provider-aware estimates
may only tighten those caps; they can never increase retained context.
"""

from __future__ import annotations

from model_context_policy import ModelContextPolicy
from provider_token_estimator import ProviderTokenEstimator


class TokenAwareModelContextPolicy(ModelContextPolicy):
    """Apply model-aware advisory ceilings behind existing character limits."""

    def __init__(
        self,
        *,
        model_name: str,
        max_history_messages: int = 8,
        max_history_chars: int = 12000,
        max_tool_context_chars: int = 48000,
        compacted_tool_result_chars: int = 1200,
        history_token_budget: int | None = None,
        tool_context_token_budget: int | None = None,
    ) -> None:
        estimator = ProviderTokenEstimator(model_name)
        raw_history_chars = max(0, int(max_history_chars))
        raw_tool_chars = max(4000, int(max_tool_context_chars))

        history_tokens = (
            max(0, int(history_token_budget))
            if history_token_budget is not None
            else raw_history_chars // 4
        )
        tool_tokens = (
            max(0, int(tool_context_token_budget))
            if tool_context_token_budget is not None
            else raw_tool_chars // 4
        )

        estimated_history_chars = estimator.chars_for_token_budget(history_tokens)
        estimated_tool_chars = estimator.chars_for_token_budget(tool_tokens)

        effective_history_chars = min(raw_history_chars, estimated_history_chars)
        effective_tool_chars = min(raw_tool_chars, max(4000, estimated_tool_chars))

        super().__init__(
            max_history_messages=max_history_messages,
            max_history_chars=effective_history_chars,
            max_tool_context_chars=effective_tool_chars,
            compacted_tool_result_chars=compacted_tool_result_chars,
        )
        self.estimator = estimator
        self.configured_history_chars = raw_history_chars
        self.configured_tool_context_chars = raw_tool_chars
        self.history_token_budget = history_tokens
        self.tool_context_token_budget = tool_tokens


__all__ = ["TokenAwareModelContextPolicy"]
