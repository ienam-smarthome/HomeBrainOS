from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import _normalise_history, should_use_unified_agent  # noqa: E402
from control_agent_combined_level import install_combined_level_intent  # noqa: E402
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


def test_explicit_named_lookup_is_distinguished_from_broad_inventory():
    lookup = UnifiedAdaptiveMCPAgent._targeted_device_lookup
    assert lookup("find front door") == "front door"
    assert lookup("Please search for the device Entrance Lock") == "Entrance Lock"
    assert lookup("show all selected devices") is None
    assert lookup("what doors are open?") is None


def test_planner_broad_call_is_repaired_before_targeted_lookup_synthesis():
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return SimpleNamespace(
                data={"matches": [{"id": "7399", "label": "Front Door"}]},
                text="",
                raw={},
                is_error=False,
            )

    client = FakeClient()
    agent = object.__new__(UnifiedAdaptiveMCPAgent)
    agent.client = client
    agent.require_sensitive_confirmation = False
    agent.tool_result_limit_chars = 8000

    record, tool_text = asyncio.run(
        agent._execute_tool_call("hub_list_devices", {}, "find front door")
    )

    assert client.calls == [
        ("homebrain_search_devices", {"query": "front door", "limit": 8})
    ]
    assert record["name"] == "homebrain_search_devices"
    assert record["success"] is True
    assert "Front Door" in tool_text


def test_exact_fast_control_and_protocol_followups_stay_deterministic():
    install_combined_level_intent()
    assert not should_use_unified_agent("Turn on Bedroom 1 Light")
    assert not should_use_unified_agent("turn on living room light 2 at 90%")
    assert not should_use_unified_agent("yes")
    assert not should_use_unified_agent("Create paused rule")


def test_device_health_queries_never_enter_unified_ai_synthesis():
    variants = (
        "Are any devices offline or stale?",
        "List devices that are offline or stale",
        "Do I have stale devices?",
        "Device health status",
    )

    assert all(not should_use_unified_agent(query) for query in variants)


def test_attention_shortcut_never_becomes_a_device_name_search():
    assert not should_use_unified_agent("Find devices that need attention")


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
