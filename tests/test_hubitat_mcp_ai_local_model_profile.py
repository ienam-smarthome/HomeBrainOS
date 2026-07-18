from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_adaptive import AdaptiveFinalAnswerAgent  # noqa: E402


def _agent(configured: str = "qwen3.5:9b") -> AdaptiveFinalAnswerAgent:
    agent = object.__new__(AdaptiveFinalAnswerAgent)
    agent.model = configured
    return agent


def test_local_model_selection_targets_qwen35_4b_not_smallest_model():
    selected = _agent()._preferred_family_model(
        [
            "qwen3.5:0.8b",
            "qwen3.5:2b",
            "qwen3.5:4b",
            "qwen3.5:9b",
        ]
    )

    assert selected == "qwen3.5:4b"


def test_local_model_selection_uses_9b_when_4b_is_not_installed():
    assert _agent()._preferred_family_model(["qwen3.5:9b"]) == "qwen3.5:9b"


def test_local_model_selection_does_not_cross_qwen_generations():
    selected = _agent()._preferred_family_model(
        ["qwen3:4b", "qwen3.5:9b", "gemma3:4b"]
    )

    assert selected == "qwen3.5:9b"


def test_addon_defaults_use_responsive_4b_profile():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert "version: '0.4.10-alpha'" in config
    assert 'ollama_model: "qwen3.5:4b"' in config
    assert "ollama_planner_timeout_seconds: 20" in config
    assert "ollama_routine_response_timeout_seconds: 15" in config
    assert "ollama_quick_insight_timeout_seconds: 15" in config
    assert "ollama_num_ctx: 2048" in config
    assert "ollama_max_tool_rounds: 2" in config


def test_windows_setup_script_disables_thinking_and_uses_2k_context():
    script = (ROOT / "scripts" / "install-homebrain-qwen35-4b.ps1").read_text(
        encoding="utf-8"
    )

    assert "$model = 'qwen3.5:4b'" in script
    assert "think = $false" in script
    assert "num_ctx = 2048" in script
    assert "Start-Process" in script
    assert "2>$null" not in script
    assert "Thinking disabled: confirmed." in script
