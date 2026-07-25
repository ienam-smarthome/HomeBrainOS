from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import entrypoint_core  # noqa: E402
from ollama_agent_claude import ClaudeStyleOllamaAgent  # noqa: E402
from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_final_runtime_agent_is_unified_adaptive_agent():
    """The request-serving Ollama object must be the unified implementation."""
    agent = entrypoint_core.application.ollama

    assert type(agent) is UnifiedAdaptiveMCPAgent
    assert entrypoint_core.application.ollama is agent


def test_temporary_claude_agent_is_not_the_final_runtime_object():
    """app.py may construct a legacy base agent, but it must be replaced."""
    agent = entrypoint_core.application.ollama

    # UnifiedAdaptiveMCPAgent inherits through the Claude-style chain, so an
    # isinstance check is insufficient. The exact runtime class is intentional.
    assert isinstance(agent, ClaudeStyleOllamaAgent)
    assert type(agent) is not ClaudeStyleOllamaAgent
