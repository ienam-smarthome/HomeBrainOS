from __future__ import annotations

import re

from ollama_agent_final_answer import FinalAnswerNaturalAgent
from ollama_agent_fast import OllamaUnavailable


class AdaptiveFinalAnswerAgent(FinalAnswerNaturalAgent):
    """Final-answer agent that never crosses model generations automatically.

    A configured qwen3.5 assistant may use a smaller installed qwen3.5 helper, but
    it will not silently fall back to qwen3:4b. That older helper was responsible
    for the repeated 25-second planner timeouts seen while qwen3.5:9b was healthy.
    """

    def _preferred_family_model(self, installed_models: list[str]) -> str:
        response_family = self.model.split(":", 1)[0].lower()
        candidates = [
            name
            for name in installed_models
            if name
            and name.split(":", 1)[0].lower() == response_family
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
        ]
        if not candidates:
            return self.model

        def size_key(name: str) -> tuple[float, str]:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            return (float(match.group(1)) if match else 999.0, name.lower())

        candidates.sort(key=size_key)
        return candidates[0]


__all__ = ["AdaptiveFinalAnswerAgent", "OllamaUnavailable"]
