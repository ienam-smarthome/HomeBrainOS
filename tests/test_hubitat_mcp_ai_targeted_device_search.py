from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_index_broker import IndexedMCPStateBroker  # noqa: E402


def test_targeted_device_search_ranks_exact_label_without_inventory_truncation():
    devices = [
        {"id": "1", "label": "Fridge Door", "room": "Appliances"},
        {"id": "7399", "label": "Front Door", "room": "Hallway", "currentStates": {"contact": "closed"}},
        {"id": "7062", "label": "G4 Doorbell ringing", "room": "Hallway"},
    ]
    matches = IndexedMCPStateBroker._rank_device_matches("Find front door", devices, 5)
    assert matches[0]["id"] == "7399"
    assert matches[0]["label"] == "Front Door"


def test_targeted_device_search_uses_semantic_tokens_not_fixed_phrase_routes():
    devices = [
        {"id": "7399", "label": "Front Door", "room": "Hallway"},
        {"id": "7062", "label": "G4 Doorbell ringing", "room": "Hallway"},
        {"id": "3", "label": "Back Door", "room": "Kitchen"},
    ]
    matches = IndexedMCPStateBroker._rank_device_matches(
        "Which device is used for the front entrance?", devices, 5
    )
    assert matches[0]["id"] == "7399"


def test_virtual_search_tool_is_prioritised_for_unified_agent():
    tools = [
        SimpleNamespace(name="hub_search_tools"),
        SimpleNamespace(name="hub_list_devices"),
        SimpleNamespace(name="homebrain_search_devices"),
    ]
    from ollama_agent_unified import UnifiedAdaptiveMCPAgent  # noqa: E402

    fake = SimpleNamespace(unified_tool_limit=48)
    selected = UnifiedAdaptiveMCPAgent._select_compact_tools(fake, "anything", tools)
    names = [tool.name for tool in selected]
    assert names[0] == "homebrain_search_devices"
