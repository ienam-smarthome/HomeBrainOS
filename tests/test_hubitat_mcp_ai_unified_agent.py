from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import _normalise_history, should_use_unified_agent  # noqa: E402
from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402


def test_natural_rule_requests_go_to_unified_agent_without_phrase_patches():
    variants = (
        "Write a rule to alert me if the front door remains open",
        "Let me know whenever the entrance contact is open too long",
        "Create something that warns us about a door left ajar",
        "Build an automation for the front door being open for more than two minutes",
    )
    assert all(should_use_unified_agent(query) for query in variants)


def test_device_discovery_goes_to_the_same_agent():
    assert should_use_unified_agent("Find front door")
    assert should_use_unified_agent("Which sensor belongs to the main entrance?")


def test_exact_fast_control_and_protocol_followups_stay_deterministic():
    assert not should_use_unified_agent("Turn on Bedroom 1 Light")
    assert not should_use_unified_agent("yes")
    assert not should_use_unified_agent("Create paused rule")


def test_typed_history_is_normalised_before_entering_agent_loop():
    class PydanticLike:
        def model_dump(self):
            return {"role": "assistant", "content": "Previous answer"}

    history = _normalise_history(
        [
            SimpleNamespace(role="user", content="Previous question"),
            PydanticLike(),
            {"role": "system", "content": "ignored"},
        ]
    )
    assert history == [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"},
    ]


def test_unified_catalogue_exposes_discovery_core_and_gateways_without_keywords():
    fake_agent = SimpleNamespace(unified_tool_limit=48)
    tools = [
        SimpleNamespace(name="hub_manage_rules"),
        SimpleNamespace(name="hub_read_rooms"),
        SimpleNamespace(name="hub_search_tools"),
        SimpleNamespace(name="hub_get_tool_guide"),
        SimpleNamespace(name="hub_list_devices"),
        SimpleNamespace(name="hub_read_devices"),
        SimpleNamespace(name="hub_manage_devices"),
        SimpleNamespace(name="hub_get_info"),
    ]
    selected = UnifiedAdaptiveMCPAgent._select_compact_tools(fake_agent, "unrelated wording", tools)
    names = [tool.name for tool in selected]

    assert names[:4] == [
        "hub_get_tool_guide",
        "hub_list_devices",
        "hub_read_devices",
        "hub_search_tools",
    ]
    assert "hub_manage_rules" in names
    assert "hub_read_rooms" in names
    assert "hub_manage_devices" in names
