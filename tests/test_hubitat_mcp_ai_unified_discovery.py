from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_unified_prompt_requires_authoritative_call_after_discovery():
    fake = SimpleNamespace()
    fake_parent = (
        "For every live-home question, call a relevant MCP tool. "
        "Use hub_search_tools when the correct tool is unclear."
    )

    class PromptAgent(UnifiedAdaptiveMCPAgent):
        pass

    # Exercise the wording contract without constructing network clients.
    prompt = UnifiedAdaptiveMCPAgent._planner_prompt
    assert callable(prompt)
    source_terms = (
        "discovery is never the final step",
        "hub_list_devices",
        "authoritative home data",
    )
    # The method depends on super(), so inspect its code constants for the contract.
    constants = " ".join(str(value) for value in prompt.__code__.co_consts)
    assert all(term in constants for term in source_terms)


def test_inventory_tools_are_prioritised_in_visible_catalogue():
    fake_agent = SimpleNamespace(unified_tool_limit=48)
    tools = [
        SimpleNamespace(name="hub_manage_rules"),
        SimpleNamespace(name="hub_search_tools"),
        SimpleNamespace(name="hub_get_tool_guide"),
        SimpleNamespace(name="hub_list_devices"),
        SimpleNamespace(name="hub_read_devices"),
    ]
    selected = UnifiedAdaptiveMCPAgent._select_compact_tools(
        fake_agent,
        "arbitrary wording",
        tools,
    )
    names = [tool.name for tool in selected]
    assert names[:4] == [
        "hub_get_tool_guide",
        "hub_list_devices",
        "hub_read_devices",
        "hub_search_tools",
    ]
