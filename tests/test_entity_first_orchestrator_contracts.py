from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SUITE_PATH = Path(__file__).with_name("_entity_first_orchestrator_cases.py")
_SPEC = importlib.util.spec_from_file_location("_entity_first_orchestrator_cases", _SUITE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_suite = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_suite)

from request_metrics import RequestMetrics  # noqa: E402


def test_model_rule_authoring_omits_eager_full_device_manifest():
    agent = object.__new__(_suite.UnifiedMCPAgent)

    assert agent._include_identity_manifest(
        "create a rule: if Big lamp turns on after 2am, turn it off 30 minutes later"
    ) is False
    assert agent._include_identity_manifest(
        "delete the Big lamp device"
    ) is False
    assert agent._include_identity_manifest(
        "if Big lamp turns on between 2:30am and 6:30am, turn it off 30 minutes later"
    ) is False


@pytest.mark.asyncio
async def test_invalid_rule_proposal_returns_exact_failed_outcome():
    class RuleMCP(_suite.FakeMCP):
        async def list_tools(self):
            return [
                _suite.MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                _suite.MCPTool(
                    "hub_manage_rule_machine", "Manage rules", {"type": "object"}
                ),
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_search_tools":
                return _suite.MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {"results": [{
                        "tool": "hub_set_rule",
                        "gateway": "hub_manage_rule_machine",
                    }]},
                )
            raise AssertionError("invalid proposal must not reach Hubitat")

    rejected_arguments = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Big Lamp Auto-Off (2:30am-6:30am)",
            "addRequiredExpression": {
                "conditions": [{
                    "capability": "Between two times",
                    "start": {"type": "clock", "time": "02:30"},
                    "end": {"type": "clock", "time": "06:30"},
                }],
                "operator": "AND",
            },
            "addActions": [
                {"capability": "delay", "minutes": 30},
                "not-an-action-object",
            ],
        },
    }
    ai = _suite.FakeAI([
        {"message": {
            "role": "assistant",
            "tool_calls": [{"function": {
                "name": "hub_manage_rule_machine",
                "arguments": rejected_arguments,
            }}],
        }},
        {"message": {
            "role": "assistant",
            "content": "The action sequence had a formatting error.",
        }},
    ])
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        agent = _suite.UnifiedMCPAgent(RuleMCP(), "key", "model", ai_client=ai)
        outcome = await agent.process_user_request_result(
            "Create the advanced Big Lamp rule", session_id="invalid-rule"
        )
        assert metrics.completed_outcome() == "failed"
        assert metrics.snapshot()["counters"]["proposal_validation_failures"] == 1
    finally:
        metrics.reset(token)

    assert "No Hubitat action was queued or executed" in outcome.message
    assert "Exact reason:" in outcome.message
    assert "Rejected payload:" in outcome.message
    assert '"not-an-action-object"' in outcome.message
    assert "every addActions item must be an object" in outcome.message
    assert len(ai.requests) == 2


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
                assert arguments["tool"] == "hub_list_devices"
                assert arguments["args"]["labelFilter"] == "tab s9"
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
        (
            "hub_read_devices",
            {
                "tool": "hub_list_devices",
                "args": {
                    "labelFilter": "tab s9",
                    "fields": [
                        "id", "name", "label", "room", "capabilities",
                        "attributes", "commands",
                    ],
                },
            },
        ),
        ("hub_read_rules", {"tool": "hub_list_rules", "args": {}}),
    ]


@pytest.mark.asyncio
async def test_history_uses_targeted_local_resolver():
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
                assert arguments["args"]["labelFilter"] == "tab s9"
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
    ai = _suite.FakeAI([
        {"message": {
            "role": "assistant",
            "tool_calls": [{"function": {
                "name": "homebrain_device_history",
                "arguments": {"name": "tab s9"},
            }}],
        }},
        {"message": {
            "role": "assistant",
            "content": (
                "Block Tab-S9-FE last changed at 2:55 pm on Saturday 1 August 2026."
            ),
        }},
    ])
    agent = _suite.UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "When did tab s9 last change?"
    )

    assert outcome.request_class == "live-read"
    assert "Block Tab-S9-FE" in outcome.message
    assert len(ai.requests) == 2
    assert mcp.calls[-1][1]["args"]["deviceId"] == "6916"
    inventory_calls = [
        arguments
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
    ]
    assert len(inventory_calls) == 1
    assert inventory_calls[0]["args"]["labelFilter"] == "tab s9"
