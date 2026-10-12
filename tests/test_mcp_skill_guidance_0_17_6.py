"""Contract tests for the Claude-skill-inspired general MCP workflow."""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_skill_guidance import (  # noqa: E402
    build_mcp_skill_guidance,
    wants_deep_investigation,
)


def test_live_registry_and_guide_are_authoritative_for_all_requests():
    instructions = build_mcp_skill_guidance("What happened at home?")
    assert "hub_search_tools" in instructions
    assert "hub_get_tool_guide" in instructions
    assert "SPECIFIC operation" in instructions
    assert "The installed server" in instructions
    assert "Tool discovery and annotations never authorize a write" in instructions
    assert "Do not replace tool failures with fabricated information" in instructions


def test_multipart_rule_investigation_receives_generic_trigger_condition_action_skill():
    instructions = build_mcp_skill_guidance(
        "Analyse my Rule Machine automation, its triggers and recent errors"
    )
    assert "triggers (start execution)" in instructions
    assert "conditions/required expressions" in instructions
    assert "timestamp-scoped app logs" in instructions
    assert "set_rule_reference" in instructions


def test_control_skill_requires_exact_identity_and_confirmed_mutations():
    instructions = build_mcp_skill_guidance("Unlock garage door and reboot hub")
    assert "Match the actual device identity exactly" in instructions
    assert "Sensitive/destructive" in instructions or "sensitive/destructive" in instructions
    assert "central Read/Write gates" in instructions


def test_deep_reasoning_is_explicit_and_fast_simple_causal_path_remains_available():
    assert wants_deep_investigation("Investigate thoroughly why did Bathroom Light 1 turn on?")
    assert wants_deep_investigation("Deep analysis of scheduled jobs and rules")
    assert wants_deep_investigation("Trace the full cause of this automation")
    assert not wants_deep_investigation("Why did Bathroom Light 1 turn on?")
    assert not wants_deep_investigation("Turn on Bathroom Light 1")



def test_explicit_deep_budget_is_larger_than_investigative_but_bounded():
    from reasoning_policy import reasoning_budget_status, set_reasoning_profile

    set_reasoning_profile("standard")
    standard = reasoning_budget_status()
    set_reasoning_profile("investigative")
    investigative = reasoning_budget_status()
    set_reasoning_profile("deep")
    deep = reasoning_budget_status()
    try:
        assert standard["maxReadCalls"] < investigative["maxReadCalls"] < deep["maxReadCalls"]
        assert deep["maxReadCalls"] <= 18
        assert deep["maxToolRounds"] <= 7
    finally:
        set_reasoning_profile("standard")
