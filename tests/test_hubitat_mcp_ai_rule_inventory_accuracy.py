from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_inventory import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeRulesMCP:
    def __init__(self, rules):
        self.rules = rules

    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_rules",
                description="List Hubitat rules",
                input_schema={"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name, arguments):
        assert name == "hub_list_rules"
        assert arguments == {}
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"rules": self.rules},
            is_error=False,
        )


def test_active_rule_query_does_not_turn_unknown_status_into_zero_active():
    rules = [
        {"id": "1", "name": "Hall light timer", "status": "Available"},
        {"id": "2", "name": "Night heating", "status": "Available"},
    ]
    answer = asyncio.run(
        FastFallbackRouter(FakeRulesMCP(rules)).answer(
            "List active automation rules"
        )
    )

    assert answer["route"] == "fallback"
    assert answer["intent"] == "fallback-active-rules"
    assert "does not expose" in answer["message"]
    assert "zero rules are active" in answer["message"]
    metrics = {
        item["label"]: item["value"]
        for item in answer["display"]["metrics"]
    }
    assert metrics["Active"] == "Unknown"
    assert metrics["Status unknown"] == "2"


def test_active_rule_query_lists_only_explicitly_active_rules():
    rules = [
        {"id": "1", "name": "Hall light timer", "enabled": True},
        {"id": "2", "name": "Night heating", "paused": True},
        {"id": "3", "name": "Kitchen presence", "active": True},
    ]
    answer = asyncio.run(
        FastFallbackRouter(FakeRulesMCP(rules)).answer(
            "List active automation rules"
        )
    )

    assert "Hall light timer" in answer["message"]
    assert "Kitchen presence" in answer["message"]
    assert "Night heating" not in answer["message"]
    assert answer["display"]["subtitle"] == "2 active"

def test_disabled_flag_wins_over_paused_false_and_status_is_counted_correctly():
    rules = [
        {
            "id": "1",
            "name": "Disabled media rule",
            "disabled": True,
            "paused": False,
            "status": "disabled",
        },
        {
            "id": "2",
            "name": "Active lighting rule",
            "disabled": False,
            "paused": False,
            "status": "active",
        },
    ]
    answer = asyncio.run(
        FastFallbackRouter(FakeRulesMCP(rules)).answer("List automation rules")
    )

    assert "Disabled media rule: Disabled" in answer["message"]
    assert "Active lighting rule: Active" in answer["message"]
    metrics = {item["label"]: item["value"] for item in answer["display"]["metrics"]}
    assert metrics["Active"] == "1"
    assert metrics["Inactive"] == "1"
    assert metrics["Status unknown"] == "0"

