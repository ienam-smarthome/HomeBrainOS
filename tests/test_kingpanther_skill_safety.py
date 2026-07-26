from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from kingpanther_skill import KINGPANTHER_SYSTEM_PROMPT  # noqa: E402


def test_runtime_prompt_preserves_destructive_tool_safety_boundaries():
    prompt = KINGPANTHER_SYSTEM_PROMPT

    assert "through a gateway does not relax any of this" in prompt
    assert "hub backup\n  within 24h" in prompt
    assert "hub_shutdown is NOT hub_reboot" in prompt
    assert "manual physical power cycle" in prompt
    assert "hub_delete_device has no undo" in prompt
    assert 'hub_manage_virtual_device with action="delete"' in prompt
    assert "advisory\n  metadata only, not a safety boundary" in prompt


def test_runtime_prompt_requires_live_rule_guidance_and_mentions_loop_guard():
    prompt = KINGPANTHER_SYSTEM_PROMPT

    assert "automatic\n  loop guard" in prompt
    assert "must be re-enabled manually" in prompt
    assert "Do not guess trigger/condition/action JSON shapes from memory" in prompt
    assert "hub_get_tool_guide with the relevant section" in prompt
