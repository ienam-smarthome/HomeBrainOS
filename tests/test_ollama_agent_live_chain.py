from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)

sys.path.insert(0, str(APP_DIR))

from ollama_agent_unified import UnifiedAdaptiveMCPAgent


def test_live_ollama_agent_chain_bypasses_thin_compatibility_layers():
    qualified_names = {
        f"{cls.__module__}.{cls.__name__}"
        for cls in UnifiedAdaptiveMCPAgent.__mro__
    }

    assert (
        "ollama_agent_unified.UnifiedAdaptiveMCPAgent"
        in qualified_names
    )
    assert (
        "ollama_agent_final_answer.FinalAnswerNaturalAgent"
        in qualified_names
    )
    assert (
        "ollama_agent_quality.QualityNaturalHubitatOllamaAgent"
        in qualified_names
    )

    assert not any(
        name.startswith("ollama_agent_device_resolution.")
        for name in qualified_names
    )
    assert not any(
        name.startswith("ollama_agent_resilient.")
        for name in qualified_names
    )


def test_consolidated_methods_are_owned_by_live_classes():
    from ollama_agent_final_answer import FinalAnswerNaturalAgent
    from ollama_agent_inference import OllamaMCPAgent

    assert "_preferred_family_model" in (
        FinalAnswerNaturalAgent.__dict__
    )
    assert "health" in OllamaMCPAgent.__dict__
