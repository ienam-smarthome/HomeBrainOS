from __future__ import annotations

from typing import Any

from presenter import display_payload


def hybrid_ollama_help(application: Any) -> dict[str, Any]:
    options = application.OPTIONS
    cloud_model = str(options.get("ollama_cloud_model") or "gemma4:31b-cloud")
    local_model = str(options.get("ollama_local_fallback_model") or "qwen3.5:4b")
    cloud_enabled = bool(options.get("ollama_cloud_enabled", True))

    examples = [
        ("Explain", "Why are three lights on, and is anything unusual?"),
        ("Compare", "Compare the bedroom temperatures and explain the difference."),
        ("Motion + lights", "Find active motion and tell me which nearby lights are off."),
        ("Diagnose", "Why might this device command be failing?"),
        ("Recommend", "Suggest one useful automation for the devices I have."),
        ("Forced AI", "Start a request with ‘Ask Ollama:’ to require AI wording."),
    ]

    return {
        "success": True,
        "route": "system",
        "intent": "ollama-question-guide",
        "message": (
            f"HomeBrain uses {cloud_model} for selected AI explanations and natural "
            f"summaries, while {local_model} performs local MCP planning and retries "
            "Cloud failures. Exact states, lists and controls remain deterministic and "
            "do not consume Ollama Cloud usage."
        ),
        "model": cloud_model if cloud_enabled else local_model,
        "ai_provider": "Hybrid Ollama",
        "display": display_payload(
            "ollama-question-guide",
            "What HomeBrain AI answers",
            subtitle=(
                f"Cloud synthesis: {cloud_model} · Local planner/fallback: {local_model}"
                if cloud_enabled
                else f"Local AI only: {local_model}"
            ),
            metrics=[
                {"label": "Exact live reads", "value": "Hubitat local", "icon": "⚡"},
                {"label": "AI explanations", "value": "Ollama Cloud", "icon": "☁️"},
                {"label": "Cloud fallback", "value": "Local Qwen", "icon": "🖥️"},
            ],
            items=[
                {
                    "icon": "✨",
                    "title": title,
                    "value": "Try it",
                    "subtitle": example,
                }
                for title, example in examples
            ],
            note=(
                "Hubitat MCP remains the source of every device state. Cloud receives "
                "only compact evidence for questions that benefit from AI. Free-plan "
                "limits automatically fall back to the local model."
            ),
        ),
    }


__all__ = ["hybrid_ollama_help"]
