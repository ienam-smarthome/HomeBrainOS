from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_planner_control_exits_recover_with_authoritative_inventory():
    recoverable = (
        "The MCP planning stage finished without authoritative home data.",
        "The planner did not execute an MCP tool for a live-home question.",
        "The planner produced a tool request that could not be parsed.",
    )
    assert all(UnifiedAdaptiveMCPAgent._should_recover_with_inventory(value) for value in recoverable)


def test_real_transport_and_auth_failures_are_not_hidden():
    failures = (
        "Ollama is offline",
        "Ollama model timed out after 25 seconds",
        "MCP authentication failed",
    )
    assert not any(UnifiedAdaptiveMCPAgent._should_recover_with_inventory(value) for value in failures)
