from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import _apply_device_tool_policy  # noqa: E402


class FakeAgent:
    @staticmethod
    def _is_broad_device_inventory_request(query: str) -> bool:
        return query.strip().lower() in {"find devices", "list devices"}

    async def _answer_from_targeted_device_search(self, query, history, planner_error):
        return {
            "success": True,
            "route": "ollama+mcp",
            "message": "Found Front Door, device 7399, in Hallway.",
            "tools_used": [
                {
                    "name": "homebrain_search_devices",
                    "arguments": {"query": query, "limit": 8},
                    "success": True,
                }
            ],
            "targeted_device_search": True,
        }


@pytest.mark.asyncio
async def test_non_broad_inventory_call_is_corrected_to_targeted_search():
    app = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "tools_used": [{"name": "hub_list_devices", "arguments": {}}],
        "message": "No match",
    }
    result = await _apply_device_tool_policy(app, "Find front door", [], answer)
    assert result["tool_policy_corrected"] is True
    assert result["targeted_device_search"] is True
    assert result["message"].startswith("Found Front Door")


@pytest.mark.asyncio
async def test_broad_inventory_request_keeps_hub_list_devices_answer():
    app = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "tools_used": [{"name": "hub_list_devices", "arguments": {}}],
        "message": "I found 106 devices.",
    }
    result = await _apply_device_tool_policy(app, "find devices", [], answer)
    assert result is answer
    assert "tool_policy_corrected" not in result
