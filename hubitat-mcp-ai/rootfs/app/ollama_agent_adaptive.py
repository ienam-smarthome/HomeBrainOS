from __future__ import annotations

import re

from ollama_agent_final_answer import FinalAnswerNaturalAgent
from ollama_agent_fast import OllamaUnavailable


_TARGET_LOCAL_MODEL_BILLIONS = 4.0


class AdaptiveFinalAnswerAgent(FinalAnswerNaturalAgent):
    """Final-answer agent tuned for a 16 GB shared-memory local AI PC.

    A configured Qwen 3.5 assistant may use another installed Qwen 3.5 model, but
    it never crosses model generations automatically. Model selection targets 4B
    rather than blindly choosing the smallest installed model: 0.8B/2B variants
    are faster but materially weaker for natural smart-home explanations, while
    9B is too slow on the GMKtec M6 Ultra for routine interactive responses.
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

        def model_size(name: str) -> float:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            return float(match.group(1)) if match else 999.0

        def preference_key(name: str) -> tuple[float, int, float, str]:
            size = model_size(name)
            # Prefer the exact 4B target. On a tie, avoid going below 4B before
            # choosing a larger model, then prefer the smaller memory footprint.
            distance = abs(size - _TARGET_LOCAL_MODEL_BILLIONS)
            below_target = 1 if size < _TARGET_LOCAL_MODEL_BILLIONS else 0
            return distance, below_target, size, name.lower()

        candidates.sort(key=preference_key)
        return candidates[0]


__all__ = ["AdaptiveFinalAnswerAgent", "OllamaUnavailable"]
