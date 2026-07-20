from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_live_data_planner_failures_trigger_authoritative_recovery():
    recoverable = (
        "The MCP planning stage finished without authoritative home data.",
        "The planner did not execute an MCP tool for a live-home question.",
        "The planner produced a tool request that could not be parsed.",
    )
    assert all(UnifiedAdaptiveMCPAgent._should_recover_with_inventory(message) for message in recoverable)


def test_transport_and_model_failures_do_not_masquerade_as_inventory_recovery():
    non_recoverable = (
        "Ollama is offline",
        "Ollama model timed out after 25 seconds",
        "MCP authentication failed",
    )
    assert not any(UnifiedAdaptiveMCPAgent._should_recover_with_inventory(message) for message in non_recoverable)
