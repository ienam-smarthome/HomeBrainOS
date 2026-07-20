from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import _uses_conversation_context  # noqa: E402
from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_standalone_inventory_request_does_not_reuse_previous_entity():
    assert _uses_conversation_context("find devices") is False
    assert _uses_conversation_context("Find front door") is False


def test_genuine_followup_keeps_conversation_context():
    assert _uses_conversation_context("What about its battery?") is True
    assert _uses_conversation_context("Check it again") is True


def test_broad_device_request_uses_inventory_policy():
    fake = SimpleNamespace()
    assert UnifiedAdaptiveMCPAgent._is_broad_device_inventory_request(fake, "find devices") is True
    assert UnifiedAdaptiveMCPAgent._is_broad_device_inventory_request(fake, "show all selected devices") is True
    assert UnifiedAdaptiveMCPAgent._is_broad_device_inventory_request(fake, "find front door device") is False
