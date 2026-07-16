from __future__ import annotations

import re

from ollama_agent_quality import QualityNaturalHubitatOllamaAgent


class DeviceResolutionNaturalAgent(QualityNaturalHubitatOllamaAgent):
    """Quality agent that avoids silently using an older Qwen generation."""

    def _preferred_family_model(self, installed_models: list[str]) -> str:
        configured_name = self.model.split(":", 1)[0].lower()
        generation_match = re.match(r"([a-z]+\d+)", configured_name)
        generation = generation_match.group(1) if generation_match else configured_name

        candidates = [
            name
            for name in installed_models
            if name
            and not any(term in name.lower() for term in ("embed", "nomic", "bge"))
            and name.split(":", 1)[0].lower().startswith(generation)
        ]
        if not candidates:
            return self.model

        def size_key(name: str) -> tuple[float, str]:
            match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)b(?:\b|$)", name.lower())
            return (float(match.group(1)) if match else 999.0, name.lower())

        candidates.sort(key=size_key)
        return candidates[0]


__all__ = ["DeviceResolutionNaturalAgent"]
