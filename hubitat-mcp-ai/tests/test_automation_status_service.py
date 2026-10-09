from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import pytest

from automation_status_service import AutomationStatusService, AutomationStatusOutcome
from mcp_client import MCPToolResult


class FakeMCPClient:
    def __init__(self, results):
        self._results = results

    async def call_tool(self, name, arguments):
        return self._results[name]


def test_normal_running_app_without_flags_is_active():
    assert AutomationStatusService.normalise_status({"id": "3919", "label": "Package Manager"}) == "active"


def test_disabled_and_paused_precedence():
    assert AutomationStatusService.normalise_status({"id": "1", "disabled": True}) == "disabled"
    assert AutomationStatusService.normalise_status({"id": "2", "paused": True}) == "paused"


def test_tool_schema_entries_are_not_rules():
    result = MCPToolResult(name="hub_read_rules", arguments={}, raw={}, text="ok", data={"tools": [{"name": "hub_list_rules", "input_schema": {}}], "rules": [{"id": "42", "name": "Morning Lights", "disabled": False}]})
    items = AutomationStatusService._items_from_result(result, item_type="rule", source="hub_read_rules")
    assert len(items) == 1
    assert items[0]["name"] == "Morning Lights"


def test_tool_only_response_has_no_rules():
    result = MCPToolResult(name="hub_read_rules", arguments={}, raw={}, text="ok", data={"tools": [{"name": "hub_list_rules"}], "rules": []})
    assert AutomationStatusService._items_from_result(result, item_type="rule", source="hub_read_rules") == []


def test_broad_automation_improvement_request_uses_reasoning_agent():
    assert not AutomationStatusService.matches_request("What improvements can I make to my automations?")
    assert not AutomationStatusService.matches_request("Review and improve my automations")


def test_explicit_automation_status_request_keeps_deterministic_route():
    assert AutomationStatusService.matches_request("Show disabled automations")
    assert AutomationStatusService.matches_request("What is the status of my rules?")


def test_explicit_new_automation_ideas_keep_creative_route():
    prompt = "Recommend useful automations for my home"
    assert AutomationStatusService.matches_request(prompt)
    assert AutomationStatusService.is_advisory_request(prompt)
    assert AutomationStatusService.wants_new_automation_ideas(prompt)


@pytest.mark.asyncio
async def test_snapshot_does_not_fabricate_rules():
    service = AutomationStatusService(FakeMCPClient({
        "hub_read_apps_code": MCPToolResult(name="hub_read_apps_code", arguments={}, raw={}, text="ok", data={"apps": [{"id": "1", "label": "Test App"}]}),
        "hub_read_rules": MCPToolResult(name="hub_read_rules", arguments={}, raw={}, text="ok", data={"tools": [{"name": "hub_list_rules"}], "rules": []}),
    }))
    outcome = await service.snapshot()
    assert isinstance(outcome, AutomationStatusOutcome)
    assert any(item["name"] == "Test App" and item["status"] == "active" for item in outcome.automation_items)
    assert all(item["type"] != "rule" for item in outcome.automation_items)

@pytest.mark.asyncio
async def test_snapshot_uses_real_rule_listing_contract_and_preserves_coverage():
    class RecordingMCP:
        def __init__(self):
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_apps_code":
                return MCPToolResult(name=name, arguments=arguments, raw={}, text="ok", data={"apps": [{"id": "169", "name": "Rule Machine", "disabled": False}]})
            return MCPToolResult(name=name, arguments=arguments, raw={}, text="ok", data={"rules": [{"id": "4206", "name": "Night Light", "disabled": False}]})

    client = RecordingMCP()
    outcome = await AutomationStatusService(client).snapshot(brief=True)
    assert ("hub_read_rules", {"tool": "hub_list_rules", "args": {}}) in client.calls
    assert "1 structured entries returned" in outcome.message
    assert "completeness not independently verified" in outcome.message
    assert any(item["id"] == "4206" and item["type"] == "rule" for item in outcome.automation_items)


@pytest.mark.asyncio
async def test_rule_listing_tool_error_cannot_establish_live_rule_coverage():
    service = AutomationStatusService(FakeMCPClient({
        "hub_read_apps_code": MCPToolResult(name="hub_read_apps_code", arguments={}, raw={}, text="ok", data={"apps": [{"id": "169", "label": "Rule Machine"}]}),
        "hub_read_rules": MCPToolResult(name="hub_read_rules", arguments={}, raw={}, text="failed", data={"success": False, "error": "not available"}),
    }))
    outcome = await service.snapshot(brief=True)
    assert "unavailable (hub_list_rules returned a tool error)" in outcome.message
    assert all(item["type"] != "rule" for item in outcome.automation_items)
    assert outcome.evidence[-1]["supports_live_claim"] is False
