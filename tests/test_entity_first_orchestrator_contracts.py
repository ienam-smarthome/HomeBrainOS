from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SUITE_PATH = Path(__file__).with_name("_entity_first_orchestrator_cases.py")
_SPEC = importlib.util.spec_from_file_location("_entity_first_orchestrator_cases", _SUITE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_suite = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_suite)


@pytest.mark.asyncio
async def test_rule_authoring_uses_complete_inventory_before_model():
    class RuleAuthoringMCP(_suite.FakeMCP):
        async def list_tools(self):
            return [
                _suite.MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                _suite.MCPTool("hub_read_apps_code", "Read apps", {"type": "object"}),
                _suite.MCPTool(
                    "hub_manage_rule_machine",
                    "Create and edit Rule Machine rules",
                    {"type": "object"},
                ),
                _suite.MCPTool("hub_read_devices", "Read devices", {"type": "object"}),
                _suite.MCPTool("hub_read_rules", "Read rules", {"type": "object"}),
            ]

        async def get_cached_devices(self):
            return [{
                "id": "6916",
                "label": "Block Tab-S9-FE",
                "commands": ["blockInternet", "allowInternet", "addTime"],
                "capabilities": ["Switch"],
            }]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                assert arguments == {"tool": "hub_list_devices", "args": {}}
                return _suite.MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {"devices": await self.get_cached_devices()},
                )
            if name == "hub_read_rules":
                return _suite.MCPToolResult(name, arguments, {}, "", {"rules": []})
            if name == "hub_search_tools":
                return _suite.MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "query": arguments["query"],
                        "results": [
                            {
                                "tool": "hub_set_rule",
                                "gateway": "hub_manage_rule_machine",
                            },
                            {
                                "tool": "hub_list_rules",
                                "gateway": "hub_read_rules",
                            },
                        ],
                    },
                )
            raise AssertionError((name, arguments))

    mcp = RuleAuthoringMCP()
    agent = _suite.UnifiedMCPAgent(
        mcp, "key", "model", ai_client=_suite.FakeAI([])
    )

    outcome = await agent.process_user_request_result(
        "write a rule to block tab s9 from 9am to 7pm everyday",
        session_id="rule-authoring-entity-first",
    )

    assert outcome.request_class == "write"
    assert outcome.confirmation_required is True
    assert mcp.calls == [
        (
            "hub_search_tools",
            {"query": "write a rule to block tab s9 from 9am to 7pm everyday"},
        ),
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}}),
        ("hub_read_rules", {"tool": "hub_list_rules", "args": {}}),
    ]


@pytest.mark.asyncio
async def test_history_uses_complete_inventory_local_resolver():
    class HistoryMCP(_suite.FakeMCP):
        async def list_tools(self):
            return [
                _suite.MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                _suite.MCPTool("hub_read_devices", "Read devices", {"type": "object"}),
            ]

        async def get_cached_devices(self):
            return [{
                "id": "6916",
                "label": "Block Tab-S9-FE",
                "capabilities": ["Switch"],
                "commands": ["blockInternet", "allowInternet"],
            }]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_search_tools":
                return _suite.MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {"results": [{
                        "tool": "hub_list_device_events",
                        "gateway": "hub_read_devices",
                    }]},
                )
            operation = arguments.get("tool")
            if operation == "hub_list_devices":
                assert arguments.get("args") == {}
                return _suite.MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {"devices": await self.get_cached_devices()},
                )
            if operation == "hub_list_device_events":
                return _suite.MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {"events": [{
                        "name": "switch",
                        "value": "off",
                        "date": "2026-08-01T14:55:00.000+0100",
                        "isStateChange": True,
                    }]},
                )
            raise AssertionError((name, arguments))

    mcp = HistoryMCP()
    ai = _suite.FakeAI([{"message": {
        "role": "assistant",
        "tool_calls": [{"function": {
            "name": "homebrain_device_history",
            "arguments": {"name": "tab s9"},
        }}],
    }}])
    agent = _suite.UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "When did tab s9 last change?"
    )

    assert outcome.request_class == "live-read"
    assert "Block Tab-S9-FE" in outcome.message
    assert mcp.calls[-1][1]["args"]["deviceId"] == "6916"
    inventory_calls = [
        arguments
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
    ]
    assert inventory_calls == [{"tool": "hub_list_devices", "args": {}}]
