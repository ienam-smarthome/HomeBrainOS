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

    assert not any(
        name.startswith("ollama_agent_device_resolution.")
        for name in qualified_names
    )
    assert not any(
        name.startswith("ollama_agent_adaptive.")
        for name in qualified_names
    )
    assert not any(
        name.startswith("ollama_agent_final_answer.")
        for name in qualified_names
    )
    assert not any(
        name.startswith("ollama_agent_quality.")
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

    for method_name in (
        "_exact_model_present",
        "_cloud_model_present",
        "health",
        "runtime_status",
        "answer",
        "_chat",
        "_preferred_family_model",
        "_final_answer_chat",
        "_structured_final_chat",
        "_final_only_messages",
        "_extract_final_answer",
        "_strip_thinking_blocks",
        "_looks_like_reasoning",
        "_looks_incomplete",
        "_quality_answer",
        "_resolve_planner_model",
        "_resolve_routine_model",
        "_answer_from_verified_context",
        "_verified_messages",
        "_unreliable_verified_answer",
    ):
        assert method_name in UnifiedAdaptiveMCPAgent.__dict__
