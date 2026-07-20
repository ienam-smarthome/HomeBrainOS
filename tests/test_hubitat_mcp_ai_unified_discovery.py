from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_claude import ClaudeStyleOllamaAgent  # noqa: E402


def test_discovery_only_recovery_message_requires_authoritative_tool():
    message = ClaudeStyleOllamaAgent._authoritative_tool_instruction()
    assert "non-discovery" in message.lower()
    assert "authoritative" in message.lower()
    assert "hub_list_devices" in message
