from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_no_tool_after_discovery_is_recoverable():
    assert UnifiedAdaptiveMCPAgent._should_recover_with_inventory(
        "The planner did not execute an MCP tool for a live-home question."
    )
