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
