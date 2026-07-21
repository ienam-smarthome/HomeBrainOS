from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import (  # noqa: E402
    _apply_automation_recommendation_policy,
    _apply_device_tool_policy,
    _executed_tool_names,
)


class FakeAgent:
    @staticmethod
    def _targeted_device_lookup(query: str) -> str | None:
        return "front door" if query.strip().lower() == "find front door" else None

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


def test_selected_catalogue_tools_are_not_treated_as_executed():
    answer = {
        "tools_used": [{"name": "hub_list_devices", "arguments": {}}],
        "selected_tools": [
            "homebrain_search_devices",
            "hub_list_devices",
            "hub_read_devices",
        ],
    }
    assert _executed_tool_names(answer) == {"hub_list_devices"}


@pytest.mark.asyncio
async def test_real_planner_shape_is_corrected_to_targeted_search():
    app = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "tools_used": [{"name": "hub_list_devices", "arguments": {}}],
        "selected_tools": [
            "homebrain_search_devices",
            "hub_list_devices",
            "hub_read_devices",
        ],
        "message": "No match",
    }
    result = await _apply_device_tool_policy(app, "Find front door", [], answer)
    assert result["tool_policy_corrected"] is True
    assert result["targeted_device_search"] is True
    assert result["original_executed_tools"] == ["hub_list_devices"]
    assert "homebrain_search_devices" in result["original_selected_tools"]
    assert result["message"].startswith("Found Front Door")


@pytest.mark.asyncio
async def test_broad_inventory_request_keeps_hub_list_devices_answer():
    app = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "tools_used": [{"name": "hub_list_devices", "arguments": {}}],
        "selected_tools": ["homebrain_search_devices", "hub_list_devices"],
        "message": "I found 106 devices.",
    }
    result = await _apply_device_tool_policy(app, "find devices", [], answer)
    assert result is answer
    assert "tool_policy_corrected" not in result


@pytest.mark.asyncio
async def test_non_lookup_inventory_read_is_not_forced_into_targeted_search():
    app = SimpleNamespace(ollama=FakeAgent())
    answer = {
        "tools_used": [{"name": "hub_list_devices", "arguments": {}}],
        "selected_tools": ["homebrain_search_devices", "hub_list_devices"],
        "message": "The front door is closed.",
    }
    result = await _apply_device_tool_policy(app, "what doors are open?", [], answer)
    assert result is answer
    assert "tool_policy_corrected" not in result


@pytest.mark.asyncio
async def test_false_timeout_recommendation_is_replaced_with_grounded_service_answer():
    class RecommendationService:
        @staticmethod
        def matches(query):
            return "automation" in query.lower()

        async def answer(self, query):
            return {
                "success": True,
                "route": "mcp-automation-recommendation-ai-fallback",
                "message": "Use Hallway Motion to turn on Hallway Light after dark.",
            }

    app = SimpleNamespace(automation_recommendation=RecommendationService())
    original = {
        "success": True,
        "route": "ollama+mcp",
        "message": (
            "I'm having trouble retrieving your full device list because the system "
            "is timing out with too many items."
        ),
        "tools_used": [{"name": "hub_read_devices", "success": True}],
    }

    result = await _apply_automation_recommendation_policy(
        app,
        "Suggest one useful automation for the devices I have",
        original,
    )

    assert result["synthesis_policy_corrected"] is True
    assert result["message"].startswith("Use Hallway Motion")
    assert result["original_executed_tools"] == ["hub_read_devices"]


def test_false_missing_inventory_claim_is_replaced_after_successful_device_read():
    class RecommendationService:
        @staticmethod
        def matches(query):
            return "automation" in query.lower()

        async def answer(self, query):
            return {
                "success": True,
                "route": "mcp-automation-recommendation",
                "message": "Use Hallway Motion to control Hallway Light after dark.",
            }

    app = SimpleNamespace(automation_recommendation=RecommendationService())
    original = {
        "success": True,
        "route": "ollama+mcp",
        "message": "I currently don't have a list of your devices.",
        "tools_used": [{"name": "hub_list_devices", "success": True}],
    }

    result = asyncio.run(
        _apply_automation_recommendation_policy(
            app,
            "Suggest one useful automation for the devices I have and write a rule",
            original,
        )
    )

    assert result["synthesis_policy_corrected"] is True
    assert result["message"].startswith("Use Hallway Motion")
    assert result["original_executed_tools"] == ["hub_list_devices"]


@pytest.mark.asyncio
async def test_real_mcp_failure_is_not_relabelled_as_false_timeout():
    service = SimpleNamespace(matches=lambda query: True)
    app = SimpleNamespace(automation_recommendation=service)
    original = {
        "message": "The device request is timing out.",
        "tools_used": [{"name": "hub_read_devices", "success": False}],
    }

    result = await _apply_automation_recommendation_policy(
        app,
        "Suggest one useful automation",
        original,
    )
    assert result is original
