"""Conservative dependency-free token estimates for provider payload budgets.

The estimator is intentionally approximate. It never replaces provider-side
limits or the existing character caps; callers must retain those as a hard
fallback. Profiles only adjust the conservative bytes-per-token assumption for
known model families.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    tokens: int
    utf8_bytes: int
    profile: str
    approximate: bool = True


class ProviderTokenEstimator:
    """Estimate payload tokens without adding a tokenizer dependency."""

    _PROFILE_BYTES_PER_TOKEN = {
        "qwen": 3.2,
        "gemma": 3.4,
        "llama": 3.5,
        "mistral": 3.5,
        "default": 3.2,
    }

    def __init__(self, model_name: str = "") -> None:
        normalized = str(model_name or "").strip().casefold()
        self.model_name = normalized
        self.profile = next(
            (
                family
                for family in ("qwen", "gemma", "llama", "mistral")
                if family in normalized
            ),
            "default",
        )

    @property
    def bytes_per_token(self) -> float:
        return self._PROFILE_BYTES_PER_TOKEN[self.profile]

    def estimate_text(self, content: Any) -> TokenEstimate:
        text = str(content or "")
        utf8_bytes = len(text.encode("utf-8"))
        if not utf8_bytes:
            return TokenEstimate(0, 0, self.profile)
        tokens = max(1, math.ceil(utf8_bytes / self.bytes_per_token))
        return TokenEstimate(tokens, utf8_bytes, self.profile)

    def estimate_messages(self, messages: list[dict[str, Any]]) -> TokenEstimate:
        total_bytes = 0
        total_tokens = 0
        for message in messages:
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
            tool_name = str(message.get("tool_name") or "")
            estimate = self.estimate_text(f"{role}\n{tool_name}\n{content}")
            total_bytes += estimate.utf8_bytes
            # Include a conservative structural allowance per message.
            total_tokens += estimate.tokens + 4
        return TokenEstimate(total_tokens, total_bytes, self.profile)

    def chars_for_token_budget(self, token_budget: int) -> int:
        """Return a conservative character ceiling for a token budget."""

        budget = max(0, int(token_budget))
        return max(0, math.floor(budget * self.bytes_per_token))


__all__ = ["ProviderTokenEstimator", "TokenEstimate"]
