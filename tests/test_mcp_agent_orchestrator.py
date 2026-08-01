from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
            MCPTool("set_switch", "Set switch", {"type": "object"}),
        ]

    async def get_cached_devices(self):
        return [{"id": "42", "label": "Couch Lamp", "room": "Lounge"}]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(
                name, arguments, {}, "", {"matches": [{"gateway": "set_switch"}]}
            )
        return MCPToolResult(name, arguments, {}, "ok", {"switch": "on"})


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return FakeResponse(next(self.responses))

    async def aclose(self):
        return None


class FakeStreamResponse:
    def __init__(self, lines, *, delay=0):
        self.lines = lines
        self.delay = delay

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self.lines:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield line


class FakeStreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_):
        return None


class FakeStreamingAI:
    def __init__(self, lines, *, delay=0):
        self.response = FakeStreamResponse(lines, delay=delay)
        self.requests = []

    def stream(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return FakeStreamContext(self.response)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_ollama_native_multi_round_tool_execution():
    mcp = FakeMCP()
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "set switch"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "set_switch",
                "arguments": {"device_id": "42", "state": "on"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "The couch lamp is on."}},
    ])
    agent = UnifiedMCPAgent(
        mcp, "test-key", "gemma4:31b", ai_client=ai,
        require_sensitive_confirmation=False,
    )

    answer = await agent.process_user_request("Turn on the couch lamp")

    assert answer == "The couch lamp is on."
    assert mcp.calls[-1] == ("set_switch", {"device_id": "42", "state": "on"})
    assert mcp.calls[0][0] == "hub_search_tools"
    assert ai.requests[0][0] == "https://ollama.com/api/chat"
    assert ai.requests[0][1]["headers"]["Authorization"] == "Bearer test-key"
    messages = ai.requests[2][1]["json"]["messages"]
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_name"] == "set_switch"


@pytest.mark.asyncio
async def test_rule_authoring_discovery_reaches_confirmation_not_false_denial():
    class RuleAuthoringMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                MCPTool(
                    "hub_read_apps_code",
                    "Read apps",
                    {"type": "object"},
                ),
                MCPTool(
                    "hub_manage_rule_machine",
                    "Create and edit Rule Machine rules",
                    {"type": "object"},
                ),
            ]

        async def get_cached_devices(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_apps_code":
                return MCPToolResult(name, arguments, {}, "", {"apps": []})
            if name == "hub_manage_rule_machine":
                assert arguments == {}
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "tools": [{
                            "name": "hub_set_rule",
                            "requiredOnCreate": ["name"],
                        }],
                    },
                )
            if name == "hub_search_tools":
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "query": arguments["query"],
                        "resultsCount": 1,
                        "totalToolsSearched": 142,
                        "results": [{
                            "tool": "hub_set_rule",
                            "gateway": "hub_manage_rule_machine",
                            "callAs": (
                                "Call via hub_manage_rule_machine"
                                "(tool=\"hub_set_rule\", args={...})"
                            ),
                        }],
                    },
                )
            raise AssertionError("rule mutation must wait for confirmation")

    mcp = RuleAuthoringMCP()
    block_rule_arguments = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Tab S9 FE - Block (9am)",
            "bestPracticeKey": "live-key",
            "addTriggers": [{
                "capability": "Certain Time (and optional date)",
                "time": "A specific time",
                "atTime": "09:00",
            }],
            "addActions": [{
                "capability": "runCommand",
                "deviceIds": [6916],
                "capabilityFilter": "Switch",
                "command": "blockInternet",
            }],
        },
    }
    unblock_rule_arguments = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Tab S9 FE - Unblock (7pm)",
            "bestPracticeKey": "live-key",
            "addTriggers": [{
                "capability": "Certain Time (and optional date)",
                "time": "A specific time",
                "atTime": "19:00",
            }],
            "addActions": [{
                "capability": "runCommand",
                "deviceIds": [6916],
                "capabilityFilter": "Switch",
                "command": "allowInternet",
            }],
        },
    }
    ai = FakeAI([
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_manage_rule_machine",
                "arguments": {},
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [{
            "function": {
                "name": "hub_manage_rule_machine",
                "arguments": {
                    "tool": "hub_set_rule",
                    "args": {"tool": "hub_set_rule"},
                },
            }
        }]}},
        {"message": {"role": "assistant", "tool_calls": [
            {
                "function": {
                    "name": "hub_manage_rule_machine",
                    "arguments": block_rule_arguments,
                }
            },
            {
                "function": {
                    "name": "hub_manage_rule_machine",
                    "arguments": unblock_rule_arguments,
                }
            },
        ]}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "write a rule to block tab s9 from 9am to 7pm everyday",
        session_id="rule-authoring",
    )

    assert outcome.request_class == "write"
    assert outcome.message == (
        "Please confirm before I run 2 sensitive Hubitat actions through "
        "`hub_manage_rule_machine`."
        )
    assert mcp.calls == [
        (
            "hub_search_tools",
            {"query": "write a rule to block tab s9 from 9am to 7pm everyday"},
        ),
        (
            "hub_read_apps_code",
            {"tool": "hub_list_apps", "args": {"scope": "instances"}},
        ),
        (
            "hub_manage_rule_machine",
            {},
        ),
    ]
    assert agent._pending["rule-authoring"].actions == [
        ("hub_manage_rule_machine", block_rule_arguments),
        ("hub_manage_rule_machine", unblock_rule_arguments),
    ]
    first_tools = {
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    }
    assert "hub_manage_rule_machine" in first_tools
    assert "HOST ORIGINAL-REQUEST CAPABILITY DISCOVERY" in (
        ai.requests[0][1]["json"]["messages"][0]["content"]
    )
    recovery_message = ai.requests[2][1]["json"]["messages"][-1]["content"]
    assert "non-empty name" in recovery_message
    assert "set_rule_reference" in recovery_message


@pytest.mark.asyncio
async def test_confirmed_rule_authoring_injects_upstream_approval_and_reports_verified_ids():
    class ConfirmedRuleMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                MCPTool("hub_manage_rule_machine", "Manage rules", {"type": "object"}),
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            assert name == "hub_manage_rule_machine"
            assert arguments["args"]["confirm"] is True
            app_id = 4160 if "Block" in arguments["args"]["name"] else 4161
            return MCPToolResult(
                name, arguments, {}, "",
                {"success": True, "appId": app_id, "ruleId": app_id, "health": {"ok": True}},
            )

    ai = FakeAI([])
    agent = UnifiedMCPAgent(ConfirmedRuleMCP(), "key", "model", ai_client=ai)
    actions = [
        ("hub_manage_rule_machine", {
            "tool": "hub_set_rule",
            "args": {
                "name": "Tab S9 FE - Block (9am)",
                "addAction": {"capability": "runCommand", "command": "blockInternet"},
            },
        }),
        ("hub_manage_rule_machine", {
            "tool": "hub_set_rule",
            "args": {
                "name": "Tab S9 FE - Unblock (7pm)",
                "addAction": {"capability": "runCommand", "command": "allowInternet"},
            },
        }),
    ]
    agent.confirmations.queue(
        "rule-confirmation", actions,
        [{"role": "user", "content": "create the rules"}],
        {"role": "assistant", "content": "Please confirm", "tool_calls": []},
    )

    outcome = await agent.process_user_request_result("confirm", session_id="rule-confirmation")

    assert outcome.request_class == "write"
    assert "Confirmed Rule Machine actions completed" in outcome.message
    assert "appId: 4160" in outcome.message
    assert "appId: 4161" in outcome.message
    assert "healthy" in outcome.message
    assert ai.requests == []


@pytest.mark.asyncio
async def test_confirmed_rule_authoring_never_claims_success_without_verified_rule_id():
    class FailedRuleMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                MCPTool("hub_manage_rule_machine", "Manage rules", {"type": "object"}),
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name, arguments, {}, "",
                {"success": False, "error": "Rule validation failed"},
            )

    agent = UnifiedMCPAgent(FailedRuleMCP(), "key", "model", ai_client=FakeAI([]))
    agent.confirmations.queue(
        "failed-rule",
        [
            ("hub_manage_rule_machine", {
                "tool": "hub_set_rule",
                "args": {
                    "name": "Tab S9 FE - Block (9am)",
                    "addAction": {"capability": "runCommand", "command": "blockInternet"},
                },
            }),
            ("hub_manage_rule_machine", {
                "tool": "hub_set_rule",
                "args": {
                    "name": "Tab S9 FE - Unblock (7pm)",
                    "addAction": {"capability": "runCommand", "command": "allowInternet"},
                },
            }),
        ],
        [],
        {"role": "assistant", "content": "Please confirm", "tool_calls": []},
    )

    outcome = await agent.process_user_request_result("confirm", session_id="failed-rule")

    assert "not fully completed" in outcome.message
    assert "was not verified" in outcome.message
    assert "Rule validation failed" in outcome.message
    assert "1 remaining confirmed action was not attempted" in outcome.message
    assert "completed successfully" not in outcome.message.casefold()
    assert len(agent.mcp.calls) == 1


@pytest.mark.asyncio
async def test_rule_authoring_prompt_documents_supported_gateway_path():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))

    instruction = await agent._system_prompt(
        "write a rule to block tab s9 from 9am to 7pm everyday"
    )

    assert "RULE AUTHORING" in instruction
    assert "'find device commands'" in instruction
    assert "never guess an ID or command" in instruction
    assert "query 'create Rule Machine rule'" in instruction
    assert "hub_manage_rule_machine" in instruction
    assert "tool='hub_set_rule'" in instruction
    assert "best_practice_reference" in instruction
    assert "set_rule_reference" in instruction
    assert "never invent an operation/create/args envelope" in instruction
    assert "Rule creation is supported" in instruction
    assert "complementary start and end actions" in instruction


@pytest.mark.asyncio
async def test_streaming_chat_assembles_content_and_tool_calls():
    ai = FakeStreamingAI([
        '{"message":{"role":"assistant","content":"Checking "}}',
        '{"message":{"role":"assistant","content":"now.","tool_calls":['
        '{"function":{"name":"hub_get_info","arguments":{}}}]}}',
        '{"done":true}',
    ])
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=ai)

    message = await agent._chat([{"role": "user", "content": "status"}], [])

    assert message["content"] == "Checking now."
    assert message["tool_calls"][0]["function"]["name"] == "hub_get_info"
    assert ai.requests[0][2]["json"]["stream"] is True


@pytest.mark.asyncio
async def test_streaming_chat_detects_idle_stall():
    ai = FakeStreamingAI(
        ['{"message":{"role":"assistant","content":"late"}}'],
        delay=0.05,
    )
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=ai)
    agent.stream_idle_timeout_seconds = 0.01

    with pytest.raises(TimeoutError, match="0.01s"):
        await agent._chat([{"role": "user", "content": "status"}], [])


@pytest.mark.asyncio
async def test_post_only_test_client_keeps_non_streaming_compatibility():
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "ok"}},
    ])
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=ai)

    message = await agent._chat([{"role": "user", "content": "hello"}], [])

    assert message["content"] == "ok"
    assert ai.requests[0][1]["json"]["stream"] is False


@pytest.mark.asyncio
async def test_non_routine_write_prompt_contains_live_device_identity():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    request_token = agent._request_class.set("write")
    try:
        instruction = await agent._system_prompt("Set the couch lamp level to 50")
    finally:
        agent._request_class.reset(request_token)
    assert "'Couch Lamp' | ID: 42 | Room: Lounge" in instruction


@pytest.mark.asyncio
async def test_non_device_prompt_omits_device_manifest():
    class NoDeviceMCP(FakeMCP):
        async def get_cached_devices(self):
            raise AssertionError("unrelated requests must not load the device manifest")

    agent = UnifiedMCPAgent(NoDeviceMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("Is a software update available?")
    assert "Device manifest omitted or unavailable." in instruction


def test_initial_tool_set_is_stable_lean_and_excludes_remote_writes():
    tools = [
        MCPTool("hub_search_tools", "search", {"type": "object"}),
        MCPTool("hub_read_diagnostics", "diagnostics", {"type": "object"}),
        MCPTool("hub_read_devices", "devices", {"type": "object"}),
        MCPTool("hub_update_firmware", "firmware", {"type": "object"}),
        *[
            MCPTool(name, name, {"type": "object"})
            for name in (
                "homebrain_filter_devices",
                "homebrain_query_devices",
                "homebrain_active_lights",
                "homebrain_active_rooms",
                "homebrain_active_switches",
                "homebrain_home_snapshot",
                "homebrain_hub_info_snapshot",
                "homebrain_weather_snapshot",
                "homebrain_control_devices",
            )
        ],
    ]

    selected = UnifiedMCPAgent._initial_tools(tools)

    assert [tool.name for tool in selected] == [
        "hub_search_tools",
        "hub_read_diagnostics",
        "homebrain_filter_devices",
        "homebrain_query_devices",
        "homebrain_active_lights",
        "homebrain_active_rooms",
        "homebrain_active_switches",
        "homebrain_home_snapshot",
        "homebrain_hub_info_snapshot",
        "homebrain_weather_snapshot",
        "homebrain_control_devices",
    ]
    assert "hub_read_devices" not in [tool.name for tool in selected]
    assert "hub_update_firmware" not in [tool.name for tool in selected]
    assert len(selected) == 11
    assert not hasattr(UnifiedMCPAgent, "_select_tools")


def test_read_state_question_is_not_misclassified_as_mutation():
    assert not UnifiedMCPAgent._requests_mutation("Which switches are on?")
    assert not UnifiedMCPAgent._requests_mutation("Which doors are open?")
    assert UnifiedMCPAgent._requests_mutation("turn off hallway lights")
    assert UnifiedMCPAgent._requests_mutation("switch on bedroom three big lamp")
    assert UnifiedMCPAgent._requests_mutation("pause humidity app")
    assert UnifiedMCPAgent._requests_mutation("install the firmware update")


def test_generic_routine_control_grammar_extracts_speech_target():
    assert UnifiedMCPAgent._routine_control_arguments(
        "Turn on living room two"
    ) == {
        "device_names": ["living room two"],
        "device_kind": "auto",
        "command": "on",
    }
    assert UnifiedMCPAgent._routine_control_arguments(
        "switch bedroom three big lamp on"
    ) == {
        "device_names": ["bedroom three big lamp"],
        "device_kind": "auto",
        "command": "on",
    }


@pytest.mark.asyncio
async def test_weather_question_receives_authoritative_weather_snapshot():
    class WeatherMCP(FakeMCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [{
                        "id": "7243",
                        "label": "Weather Open-Meteo",
                        "roomName": "Climate",
                        "attributes": {
                            "temperature": 24.9,
                            "humidity": 50,
                        },
                    }]
                },
            )

        async def get_cached_devices(self):
            return []

    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "content": "It is 24.9°C with 50% humidity.",
        }
    }])
    agent = UnifiedMCPAgent(WeatherMCP(), "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("What is the weather?")

    assert outcome.message == "It is 24.9°C with 50% humidity."
    assert "AUTHORITATIVE CURRENT WEATHER SNAPSHOT" in (
        ai.requests[0][1]["json"]["messages"][0]["content"]
    )
    assert any(
        receipt["evidence_kind"] == "authoritative_weather_snapshot"
        for receipt in outcome.evidence
    )


def test_conversational_prompt_detection_does_not_classify_mutations():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    assert agent._is_conversational_prompt("hello") is True
    assert agent._is_conversational_prompt("What is the hub status?") is False
    assert agent._is_conversational_prompt("turn off hallway lights") is False
    assert not hasattr(agent, "_classify_request")


@pytest.mark.asyncio
async def test_live_read_without_evidence_retries_then_fails_closed():
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "It looks healthy."}},
        {"message": {"role": "assistant", "content": "It still looks healthy."}},
    ])
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Check hub status")

    assert "could not retrieve verified live Hubitat evidence" in outcome.message
    assert outcome.request_class == "live-read"
    assert outcome.evidence == []
    assert "No successful live evidence receipt exists" in (
        ai.requests[1][1]["json"]["messages"][-1]["content"]
    )


@pytest.mark.asyncio
async def test_successful_tool_call_returns_sanitized_evidence_receipt():
    class ReadMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                MCPTool("hub_read_devices", "Read devices", {"type": "object"})
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_search_tools":
                return MCPToolResult(
                    name, arguments, {}, "", {"matches": [{"gateway": "hub_read_devices"}]}
                )
            return MCPToolResult(name, arguments, {}, "", {"devices": []})

    ai = FakeAI([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "read devices"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
                "function": {
                    "name": "hub_read_devices",
                    "arguments": {"includeAppUpdate": True, "token": "secret-value"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "The hub is healthy."}},
    ])
    agent = UnifiedMCPAgent(ReadMCP(), "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Get location details")

    assert outcome.message == "The hub is healthy."
    receipt = next(
        item for item in outcome.evidence if item["tool"] == "hub_read_devices"
    )
    assert receipt["supports_live_claim"] is True
    assert receipt["arguments"]["token"] == "[redacted]"
    assert receipt["timestamp"].endswith("+00:00")
    first_names = {
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    }
    second_names = {
        item["function"]["name"]
        for item in ai.requests[1][1]["json"]["tools"]
    }
    assert "hub_read_devices" in first_names
    assert "hub_read_devices" in second_names


@pytest.mark.asyncio
async def test_initial_registry_payload_stays_bounded_with_many_remote_tools():
    class LargeRegistryMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_search_tools", "Search tools", {"type": "object"}),
                *[
                    MCPTool(
                        f"hub_manage_large_{index}",
                        "x" * 2000,
                        {"type": "object", "description": "y" * 2000},
                    )
                    for index in range(50)
                ],
            ]

    ai = FakeAI([{"message": {"role": "assistant", "content": "Hello."}}])
    agent = UnifiedMCPAgent(LargeRegistryMCP(), "key", "model", ai_client=ai)

    answer = await agent.process_user_request("hello")

    declared = ai.requests[0][1]["json"]["tools"]
    names = [item["function"]["name"] for item in declared]
    assert answer == "Hello."
    assert len(declared) == 10
    assert names[0] == "hub_search_tools"
    assert not any(name.startswith("hub_manage_large_") for name in names)
    assert len(__import__("json").dumps(declared)) < 12_000


def test_initial_registry_excludes_remote_read_and_manage_gateways():
    tools = [
        MCPTool("hub_read_devices", "read devices", {}),
        MCPTool("hub_manage_devices", "manage devices", {}),
        MCPTool("hub_read_rooms", "read rooms", {}),
        MCPTool("hub_manage_rooms", "manage rooms", {}),
        MCPTool("hub_search_tools", "search", {}),
        MCPTool("hub_get_info", "info", {}),
    ]
    selected = UnifiedMCPAgent._initial_tools(tools)
    assert [tool.name for tool in selected] == ["hub_search_tools"]
    assert "hub_read_devices" not in [tool.name for tool in selected]
    assert "hub_manage_devices" not in [tool.name for tool in selected]
    assert "hub_read_rooms" not in [tool.name for tool in selected]
    assert "hub_manage_rooms" not in [tool.name for tool in selected]


@pytest.mark.asyncio
async def test_model_invokes_general_filter_for_complete_low_battery_answer():
    class BatteryMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_read_devices", "read devices", {}),
                MCPTool("hub_search_tools", "search tools", {}),
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [
                        {
                            "id": "5401",
                            "label": "Fridge Door",
                            "attributes": {"battery": 14},
                        },
                        {
                            "id": "4718",
                            "label": "Livingroom TRV",
                            "attributes": {"battery": 10},
                        },
                    ]
                },
            )

    mcp = BatteryMCP()
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "homebrain_filter_devices",
                        "arguments": {
                            "attribute": "battery",
                            "operator": "lte",
                            "value": 20,
                        },
                    }
                }],
            }
        },
        {"message": {"role": "assistant", "content": "2 devices have battery levels at or below 20%: Fridge Door (14%) and Livingroom TRV (10%)."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which batteries are low?")

    assert outcome.message == (
        "2 devices have battery levels at or below 20%: Fridge Door (14%) and "
        "Livingroom TRV (10%)."
    )
    assert len(ai.requests) == 2
    assert mcp.calls == [
        ("hub_search_tools", {"query": "Which batteries are low?"}),
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}}),
    ]
    kinds = [receipt["evidence_kind"] for receipt in outcome.evidence]
    assert kinds == [
        "authoritative_state_snapshot",
        "deterministic_attribute_filter",
    ]
    assert outcome.evidence[-2]["supports_live_claim"] is True
    assert outcome.evidence[-1]["supports_live_claim"] is True
    declared = ai.requests[0][1]["json"]["tools"]
    assert [item["function"]["name"] for item in declared] == [
            "hub_search_tools",
            "homebrain_filter_devices",
            "homebrain_query_devices",
            "homebrain_active_lights",
        "homebrain_active_rooms",
            "homebrain_active_switches",
            "homebrain_home_snapshot",
            "homebrain_hub_info_snapshot",
            "homebrain_weather_snapshot",
            "homebrain_control_devices",
        ]


@pytest.mark.asyncio
async def test_filter_reads_presence_from_current_states_list():
    class PresenceMCP(FakeMCP):
        async def list_tools(self):
            return [MCPTool("hub_read_devices", "read devices", {})]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [{
                        "id": "1",
                        "label": "Muhsena Khan",
                        "currentStates": [{
                            "name": "presence",
                            "currentValue": "present",
                        }],
                    }]
                },
            )

    mcp = PresenceMCP()
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "homebrain_filter_devices",
                        "arguments": {
                            "attribute": "presence",
                            "operator": "exists",
                        },
                    }
                }],
            }
        },
        {"message": {"role": "assistant", "content": "1 device matched presence exists: Muhsena Khan: presence=present."}},
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Who has presence data?")

    assert outcome.message == (
        "1 device matched presence exists: Muhsena Khan: presence=present."
    )


@pytest.mark.asyncio
async def test_whole_home_snapshot_is_complete_and_deterministic():
    class HomeMCP(FakeMCP):
        async def list_tools(self):
            return [MCPTool("hub_read_devices", "read devices", {})]

        async def get_cached_devices(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Muhsena Khan",
                            "currentStates": [{
                                "name": "presence",
                                "currentValue": "present",
                            }],
                        },
                        {
                            "id": "2",
                            "label": "Hallway Sensor",
                            "roomName": "Hallway",
                            "currentStates": [{
                                "name": "motion",
                                "currentValue": "active",
                            }],
                        },
                        {
                            "id": "3",
                            "label": "Hallway Light 1",
                            "roomName": "Hallway",
                            "capabilities": ["Switch", "Light"],
                            "currentStates": [{
                                "name": "switch",
                                "currentValue": "on",
                            }],
                        },
                        {
                            "id": "4",
                            "label": "Fridge Door",
                            "currentStates": [{
                                "name": "battery",
                                "currentValue": 14,
                            }],
                        },
                    ]
                },
            )

    mcp = HomeMCP()
    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_home_snapshot",
                    "arguments": {},
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "What's happening at home?"
    )

    assert "**Present:** Muhsena Khan" in outcome.message
    assert "active rooms: Hallway" in outcome.message
    assert "motion: Hallway Sensor" in outcome.message
    assert "**Lights on (1):** Hallway Light 1" in outcome.message
    assert "**Low batteries:** Fridge Door (14%)" in outcome.message
    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert "homebrain_home_snapshot" in declared


@pytest.mark.asyncio
async def test_home_snapshot_is_available_for_unseen_natural_paraphrase():
    class ParaphraseMCP(FakeMCP):
        async def list_tools(self):
            return [MCPTool("hub_search_tools", "search tools", {})]

        async def get_cached_devices(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name, arguments, {}, "", {"devices": []}
            )

    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "homebrain_home_snapshot",
                        "arguments": {},
                    }
                }],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Everything appears quiet at home.",
            }
        },
    ])
    agent = UnifiedMCPAgent(
        ParaphraseMCP(), "key", "model", ai_client=ai
    )

    outcome = await agent.process_user_request_result(
        "Give me a rundown of the house"
    )

    declared = {
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    }
    assert "homebrain_home_snapshot" in declared
    assert outcome.message.startswith("Everything appears quiet at home")


@pytest.mark.asyncio
async def test_active_rooms_tool_matches_dashboard_definition():
    class ActiveRoomMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_read_devices", "read devices", {}),
                MCPTool("hub_read_rooms", "read rooms", {}),
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Bedroom 3 Presence",
                            "roomName": "Bedroom 3",
                            "capabilities": ["MotionSensor"],
                            "attributes": {"motion": "active"},
                        },
                        {
                            "id": "2",
                            "label": "Livingroom Presence",
                            "roomName": "Living Room",
                            "capabilities": ["MotionSensor"],
                            "attributes": {"motion": "active"},
                        },
                        {
                            "id": "3",
                            "label": "Hallway Light",
                            "roomName": "Hallway",
                            "capabilities": ["Switch", "Light"],
                            "attributes": {"switch": "off"},
                        },
                    ]
                },
            )

    mcp = ActiveRoomMCP()
    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_active_rooms",
                    "arguments": {},
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which rooms are active?")

    assert outcome.message == (
        "2 rooms are active: Bedroom 3 and Living Room."
    )
    assert len(ai.requests) == 1
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert [receipt["evidence_kind"] for receipt in outcome.evidence] == [
        "authoritative_state_snapshot",
        "deterministic_active_rooms",
    ]
    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert "homebrain_active_rooms" in declared


@pytest.mark.asyncio
async def test_active_lights_tool_returns_exhaustive_list_without_second_round():
    class ActiveLightMCP(FakeMCP):
        async def list_tools(self):
            return [MCPTool("hub_read_devices", "read devices", {})]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Bedroom 2 Light",
                            "roomName": "Bedroom 2",
                            "capabilities": ["Switch", "Light"],
                            "attributes": {"switch": "on"},
                        },
                        {
                            "id": "2",
                            "label": "Hallway Light",
                            "roomName": "Hallway",
                            "capabilities": ["Switch", "Light"],
                            "attributes": {"switch": "off"},
                        },
                        {
                            "id": "3",
                            "label": "Fridge",
                            "roomName": "Appliances",
                            "capabilities": ["Switch"],
                            "attributes": {"switch": "on"},
                        },
                    ]
                },
            )

    mcp = ActiveLightMCP()
    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_active_lights",
                    "arguments": {},
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which lights are on?")

    assert outcome.message == "1 light is on: Bedroom 2 Light."
    assert len(ai.requests) == 1
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert [receipt["evidence_kind"] for receipt in outcome.evidence] == [
        "authoritative_state_snapshot",
        "deterministic_active_lights",
    ]
    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert "homebrain_active_lights" in declared


@pytest.mark.asyncio
async def test_active_switches_tool_excludes_lights_like_dashboard():
    class ActiveSwitchMCP(FakeMCP):
        async def list_tools(self):
            return [MCPTool("hub_read_devices", "read devices", {})]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Fridge",
                            "roomName": "Appliances",
                            "capabilities": ["Switch"],
                            "attributes": {"switch": "on"},
                        },
                        {
                            "id": "2",
                            "label": "Bedroom 1 Light",
                            "roomName": "Bedroom 1",
                            "capabilities": ["Switch", "Light"],
                            "attributes": {"switch": "on"},
                        },
                        {
                            "id": "3",
                            "label": "Fan",
                            "roomName": "Ventilation",
                            "capabilities": ["Switch"],
                            "attributes": {"switch": "off"},
                        },
                    ]
                },
            )

    mcp = ActiveSwitchMCP()
    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_active_switches",
                    "arguments": {},
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which switches are on?")

    assert outcome.message == "1 non-light switch is on: Fridge."
    assert len(ai.requests) == 1
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert [receipt["evidence_kind"] for receipt in outcome.evidence] == [
        "authoritative_state_snapshot",
        "deterministic_active_switches",
    ]
    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert "homebrain_active_switches" in declared


def test_general_device_attribute_comparisons_are_not_battery_specific():
    compare = UnifiedMCPAgent._attribute_matches

    assert compare(25.4, "gt", 20)
    assert compare("17.5", "lte", 20)
    assert compare("active", "eq", "ACTIVE")
    assert compare("partly cloudy", "contains", "cloud")
    assert compare(0, "exists", None)
    assert compare(None, "not_exists", None)


@pytest.mark.asyncio
async def test_high_level_room_control_executes_concurrently_and_skips_synthesis():
    class ControlMCP(FakeMCP):
        devices = [
            {
                "id": "1",
                "label": "Hallway Light 1",
                "roomName": "Hallway",
                "capabilities": ["Switch", "Light"],
            },
            {
                "id": "2",
                "label": "Hallway Light 2",
                "roomName": "Hallway",
                "capabilities": ["Switch", "Light"],
            },
            {
                "id": "3",
                "label": "Hallway socket",
                "roomName": "Hallway",
                "capabilities": ["Switch"],
            },
        ]

        async def list_tools(self):
            return [MCPTool("hub_manage_devices", "manage devices", {})]

        async def get_cached_devices(self):
            return self.devices

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                return MCPToolResult(
                    name, arguments, {}, "", {"devices": self.devices}
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"success": True, "waitFor": {"converged": True}},
            )

    mcp = ControlMCP()
    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_control_devices",
                    "arguments": {
                        "room": "Hallway",
                        "device_kind": "light",
                        "command": "off",
                    },
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Turn off hallway lights")

    assert outcome.message == "Turned off Hallway Light 1 and Hallway Light 2."
    assert len(ai.requests) == 1
    management_arguments = [
        arguments for name, arguments in mcp.calls
        if name == "hub_manage_devices"
    ]
    assert len(management_arguments) == 2
    for device_id in ("1", "2"):
        assert {
            "tool": "hub_call_device_command",
            "args": {
                "deviceId": device_id,
                "command": "off",
                "waitFor": {
                    "attribute": "switch",
                    "expectedValue": "off",
                    "timeoutMs": 5000,
                },
            },
        } in management_arguments
    evidence_kinds = [
        receipt["evidence_kind"] for receipt in outcome.evidence
    ]
    assert evidence_kinds[0] == "control_target_resolution"
    assert evidence_kinds[-1] == "deterministic_device_control"
    assert evidence_kinds.count("device_command_result") == 2
    assert "device_state_verification" not in evidence_kinds
    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert "homebrain_control_devices" in declared


@pytest.mark.asyncio
async def test_high_level_control_fails_closed_when_device_name_is_unmatched():
    class ControlMCP(FakeMCP):
        async def get_cached_devices(self):
            return [{
                "id": "1",
                "label": "Hallway Light 1",
                "roomName": "Hallway",
                "capabilities": ["Switch", "Light"],
            }]

    mcp = ControlMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI([]))

    result = await agent._control_devices({
        "device_names": ["Unknown Light"],
        "device_kind": "light",
        "command": "on",
    })

    assert result.is_error
    assert result.data["success"] is False
    assert result.data["executed"] == 0
    assert mcp.calls == [
        (
            "hub_read_devices",
            {
                "tool": "hub_list_devices",
                "args": {"labelFilter": "Unknown Light"},
            },
        )
    ]


@pytest.mark.asyncio
async def test_generic_tv_write_uses_only_high_level_control_and_verifies():
    class TVMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_read_devices", "read devices", {}),
                MCPTool("hub_manage_devices", "manage devices", {}),
                MCPTool("hub_search_tools", "search tools", {}),
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "devices": [{
                            "id": "4221",
                            "label": "TV",
                            "roomName": "Multimedia",
                            "capabilities": ["Switch", "PowerMeter"],
                        }]
                    },
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"success": True, "waitFor": {"converged": True}},
            )

    mcp = TVMCP()
    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_control_devices",
                    "arguments": {
                        "device_names": ["TV"],
                        "device_kind": "switch",
                        "command": "on",
                    },
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("turn on the tv")

    assert outcome.message == "Turned on TV."
    assert len(ai.requests) == 1
    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert declared == [
        "hub_search_tools",
        "homebrain_filter_devices",
        "homebrain_query_devices",
        "homebrain_active_lights",
        "homebrain_active_rooms",
        "homebrain_active_switches",
        "homebrain_home_snapshot",
        "homebrain_hub_info_snapshot",
        "homebrain_weather_snapshot",
        "homebrain_control_devices",
    ]
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_read_devices",
        "hub_manage_devices",
    ]
    assert mcp.calls[1][1]["args"] == {"labelFilter": "TV"}
    assert mcp.calls[-1][1] == {
        "tool": "hub_call_device_command",
        "args": {
            "deviceId": "4221",
            "command": "on",
            "waitFor": {
                "attribute": "switch",
                "expectedValue": "on",
                "timeoutMs": 5000,
            },
        },
    }
    assert [receipt["evidence_kind"] for receipt in outcome.evidence] == [
        "control_target_resolution",
        "device_command_result",
        "deterministic_device_control",
    ]


@pytest.mark.asyncio
async def test_high_level_control_accepts_unique_decorated_speech_match():
    class DecoratedLightMCP(FakeMCP):
        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "devices": [{
                            "id": "7045",
                            "label": "Livingroom Light 2 (Lights Off)",
                            "displayName": "Livingroom Light 2",
                            "roomName": "Living Room",
                            "capabilities": ["Switch", "Light"],
                        }]
                    },
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"success": True, "waitFor": {"converged": True}},
            )

    mcp = DecoratedLightMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI([]))

    result = await agent._control_devices({
        "device_names": ["living room light two"],
        "device_kind": "light",
        "command": "on",
    })

    assert result.data["success"] is True
    assert result.data["succeeded"][0]["id"] == "7045"
    assert mcp.calls[0] == (
        "hub_read_devices",
        {
            "tool": "hub_list_devices",
            "args": {"labelFilter": "living room light two"},
        },
    )
    assert mcp.calls[1][1]["args"] == {
        "deviceId": "7045",
        "command": "on",
        "waitFor": {
            "attribute": "switch",
            "expectedValue": "on",
            "timeoutMs": 5000,
        },
    }


@pytest.mark.asyncio
async def test_high_level_control_falls_back_when_literal_filter_is_empty():
    class EmptyFilteredLightMCP(FakeMCP):
        async def get_cached_devices(self):
            return [{
                "id": "7045",
                "label": "Livingroom Light 2",
                "roomName": "Living Room",
                "capabilities": ["Switch", "Light"],
            }]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                return MCPToolResult(
                    name, arguments, {}, "", {"devices": []}
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"success": True, "waitFor": {"converged": True}},
            )

    mcp = EmptyFilteredLightMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI([]))

    result = await agent._control_devices({
        "device_names": ["living room light two"],
        "device_kind": "light",
        "command": "on",
    })

    assert result.data["success"] is True
    assert result.data["succeeded"][0]["id"] == "7045"
    assert mcp.calls == [(
        "hub_manage_devices",
        {
            "tool": "hub_call_device_command",
            "args": {
                "deviceId": "7045",
                "command": "on",
                "waitFor": {
                    "attribute": "switch",
                    "expectedValue": "on",
                    "timeoutMs": 5000,
                },
            },
        },
    )]


@pytest.mark.asyncio
@pytest.mark.parametrize("room", ["Living Room", "Livingroom"])
async def test_room_control_falls_back_to_enriched_identity_manifest(room):
    class RoomIdentityMCP(FakeMCP):
        async def get_cached_devices(self):
            return [
                {
                    "id": "7044",
                    "label": "Livingroom Light 1",
                    "roomName": "Living Room",
                    "capabilities": ["Switch", "Light"],
                },
                {
                    "id": "7045",
                    "label": "Livingroom Light 2",
                    "roomName": "Living Room",
                    "capabilities": ["Switch", "Light"],
                },
                {
                    "id": "9000",
                    "label": "Livingroom Socket",
                    "roomName": "Living Room",
                    "capabilities": ["Switch"],
                },
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_read_devices":
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "",
                    {
                        "devices": [
                            {
                                "id": "7044",
                                "label": "Livingroom Light 1",
                                "capabilities": ["Switch", "Light"],
                            },
                            {
                                "id": "7045",
                                "label": "Livingroom Light 2",
                                "capabilities": ["Switch", "Light"],
                            },
                        ]
                    },
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"success": True, "waitFor": {"converged": True}},
            )

    mcp = RoomIdentityMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI([]))

    result = await agent._control_devices({
        "room": room,
        "device_names": [],
        "device_kind": "light",
        "command": "off",
    })

    assert result.data["success"] is True
    assert {item["id"] for item in result.data["succeeded"]} == {
        "7044", "7045"
    }
    command_calls = [
        call for call in mcp.calls
        if call[1].get("tool") == "hub_call_device_command"
    ]
    assert [call[1]["args"]["deviceId"] for call in command_calls] == [
        "7044", "7045"
    ]
    assert all(
        call[1]["args"]["waitFor"]["expectedValue"] == "off"
        for call in command_calls
    )


@pytest.mark.asyncio
async def test_hub_info_snapshot_refreshes_firmware_before_reporting():
    class HubInfoMCP(FakeMCP):
        async def get_cached_devices(self):
            return [{
                "id": "1089",
                "label": "Hub Info (C8 Pro)",
                "capabilities": ["Actuator", "Refresh", "Sensor"],
            }]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_manage_devices":
                return MCPToolResult(
                    name, arguments, {}, "ok", {"success": True}
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "id": "1089",
                    "label": "Hub Info (C8 Pro)",
                    "attributes": {
                        "firmwareVersionString": "2.5.1.136",
                        "hubUpdateStatus": "Update Available",
                        "hubUpdateVersion": "2.5.1.139",
                        "cpu5Min": 0.77,
                        "cpuPct": 19.25,
                        "freeMemory": 948.12,
                    },
                },
            )

    mcp = HubInfoMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI([]))

    result = await agent._hub_info_snapshot({"scope": "firmware"})

    assert result.data["success"] is True
    assert result.data["installed_firmware"] == "2.5.1.136"
    assert result.data["available_firmware"] == "2.5.1.139"
    assert result.data["update_available"] is True
    assert mcp.calls[0] == (
        "hub_manage_devices",
        {
            "tool": "hub_call_device_command",
            "args": {"deviceId": "1089", "command": "updateCheck"},
        },
    )
    assert mcp.calls[1][0] == "hub_read_devices"
    assert mcp.calls[1][1] == {
        "tool": "hub_get_device",
        "args": {"deviceId": "1089"},
    }


@pytest.mark.asyncio
async def test_active_lights_merges_cached_identity_with_compact_live_state():
    class CompactActiveLightMCP(FakeMCP):
        async def get_cached_devices(self):
            return [
                {
                    "id": "1",
                    "label": "Bedroom 2 Light",
                    "roomName": "Bedroom 2",
                    "capabilities": ["Switch", "Light"],
                    "attributes": {"switch": "off"},
                },
                {
                    "id": "2",
                    "label": "Fridge",
                    "roomName": "Appliances",
                    "capabilities": ["Switch"],
                    "attributes": {"switch": "off"},
                },
            ]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [
                        {"id": "1", "attributes": {"switch": "on"}},
                        {"id": "2", "attributes": {"switch": "on"}},
                    ]
                },
            )

    agent = UnifiedMCPAgent(
        CompactActiveLightMCP(),
        "key",
        "model",
        ai_client=FakeAI([]),
    )

    result = await agent._active_lights({})

    assert result.data["count"] == 1
    assert result.data["lights"] == [
        {
            "id": "1",
            "label": "Bedroom 2 Light",
            "room": "Bedroom 2",
            "switch": "on",
        }
    ]


@pytest.mark.asyncio
async def test_hub_info_request_uses_authoritative_snapshot_not_generic_info():
    class HubInfoToolsMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_get_info", "generic info", {}),
                MCPTool("hub_read_diagnostics", "diagnostics", {}),
            ]

        async def get_cached_devices(self):
            return [{"id": "1089", "label": "Hub Info (C8 Pro)"}]

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_manage_devices":
                return MCPToolResult(
                    name, arguments, {}, "ok", {"success": True}
                )
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {
                    "devices": [{
                        "id": "1089",
                        "label": "Hub Info (C8 Pro)",
                        "attributes": {
                            "firmwareVersionString": "2.5.1.136",
                            "hubUpdateStatus": "Current",
                            "hubUpdateVersion": "2.5.1.136",
                        },
                    }]
                },
            )

    ai = FakeAI([{
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "function": {
                    "name": "homebrain_hub_info_snapshot",
                    "arguments": {"scope": "firmware"},
                }
            }],
        }
    }])
    agent = UnifiedMCPAgent(
        HubInfoToolsMCP(), "key", "model", ai_client=ai
    )

    outcome = await agent.process_user_request_result("firmware update?")

    declared = [
        item["function"]["name"]
        for item in ai.requests[0][1]["json"]["tools"]
    ]
    assert "homebrain_hub_info_snapshot" in declared
    assert "hub_get_info" not in declared
    assert outcome.message == "Hub firmware 2.5.1.136 is up to date."
    assert outcome.evidence[-1]["evidence_kind"] == (
        "authoritative_hub_info_snapshot"
    )


@pytest.mark.asyncio
async def test_weather_live_read_does_not_load_identity_manifest():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("What is the weather?")
    assert "Device manifest omitted or unavailable." in instruction
    assert "'Couch Lamp' | ID: 42" not in instruction


@pytest.mark.asyncio
async def test_live_read_does_not_inject_compact_cached_states():
    class StateMCP(FakeMCP):
        async def get_cached_devices(self):
            return [{
                "id": "7",
                "label": "Hallway Sensor",
                "room": "Hallway",
                "capabilities": ["MotionSensor"],
                "attributes": [
                    {"name": "motion", "value": "active"},
                    {"name": "battery", "value": 91},
                ],
            }]

    agent = UnifiedMCPAgent(StateMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("Which motion sensors are active?")
    assert "Current: motion=active, battery=91" not in instruction
    assert "Device manifest omitted or unavailable." in instruction


@pytest.mark.asyncio
async def test_update_prompt_requires_status_reconciliation():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("software update")
    assert "homebrain_hub_info_snapshot" in instruction
    assert "{'scope': 'firmware'}" in instruction
    assert "Never replace it with generic hub_get_info" in instruction
    assert "update_available=true" in instruction


@pytest.mark.asyncio
async def test_low_battery_prompt_matches_dashboard_threshold():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("Which batteries are low?")
    assert "at or below 20 percent" in instruction
    assert "Exclude every device above 20 percent" in instruction


def test_device_health_gateways_require_structured_discovery():
    tools = [
        MCPTool("hub_read_devices", "devices", {}),
        MCPTool("hub_read_diagnostics", "diagnostics", {}),
        MCPTool("hub_manage_devices", "manage", {}),
        MCPTool("hub_search_tools", "search", {}),
    ]
    selected = UnifiedMCPAgent._initial_tools(tools)
    assert [tool.name for tool in selected] == [
        "hub_search_tools", "hub_read_diagnostics",
    ]
    result = MCPToolResult(
        "hub_search_tools", {}, {}, "",
        {"matches": [{"gateway": "hub_manage_devices"}]},
    )
    discovered = UnifiedMCPAgent._discovered_tools(
        result, {tool.name: tool for tool in tools}
    )
    assert [tool.name for tool in discovered] == ["hub_manage_devices"]


@pytest.mark.asyncio
async def test_device_health_prompt_distinguishes_stale_from_offline():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt(
        "List devices that are offline or stale"
    )
    assert "Stale means no recent event" in instruction
    assert "does not prove a device is offline" in instruction
    assert "rtt=timeout" in instruction
    assert "command='ping'" in instruction
    assert "Limit active checks to five devices" in instruction


@pytest.mark.asyncio
async def test_live_read_prompt_omits_cached_identity_state():
    class HealthMCP(FakeMCP):
        async def get_cached_devices(self):
            return [{
                "id": "9",
                "label": "Remote",
                "capabilities": ["HealthCheck"],
                "attributes": [
                    {"name": "healthStatus", "value": "offline"},
                    {"name": "rtt", "value": "timeout"},
                    {"name": "Status", "value": "clear"},
                ],
            }]

    agent = UnifiedMCPAgent(HealthMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("find offline or stale devices")
    assert "Device manifest omitted or unavailable." in instruction
    assert "'Remote' | ID: 9" not in instruction
    assert "rtt=timeout" in instruction  # Health-check policy, not cached state.
    assert not agent._evidence.get()


@pytest.mark.asyncio
async def test_whole_home_prompt_requires_multi_category_snapshot():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("What's happening at home?")
    assert "WHOLE-HOME SUMMARY RULES" in instruction
    assert "active motion" in instruction
    assert "open doors/windows" in instruction
    assert "Do not say the home is quiet when anyone is present" in instruction


def test_large_tool_results_are_bounded():
    agent = UnifiedMCPAgent(
        FakeMCP(), "key", "model", ai_client=FakeAI([]),
        max_tool_result_chars=2000,
    )
    result = MCPToolResult("tool", {}, {}, "", {"content": "x" * 5000})
    payload = agent._result_payload(result)
    parsed = __import__("json").loads(payload)
    assert parsed["truncated"] is True
    assert parsed["original_chars"] > 5000


def test_conversation_history_keeps_recent_messages_with_char_budget():
    agent = UnifiedMCPAgent(
        FakeMCP(),
        "key",
        "model",
        ai_client=FakeAI([]),
        max_history_messages=4,
        max_history_chars=110,
    )
    history = [
        {
            "role": "assistant" if index % 2 else "user",
            "content": f"{index:02d}" + "x" * 38,
        }
        for index in range(10)
    ]

    bounded = agent._history(history)

    assert len(bounded) == 3
    assert bounded[-1]["content"].startswith("09")
    assert bounded[0]["content"].startswith("07")
    assert bounded[0]["content"].endswith("[earlier history truncated]")
    assert sum(len(item["content"]) for item in bounded) <= 110


def test_tool_context_compacts_oldest_results_before_newest():
    agent = UnifiedMCPAgent(
        FakeMCP(),
        "key",
        "model",
        ai_client=FakeAI([]),
        max_tool_context_chars=4000,
        compacted_tool_result_chars=500,
    )
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "original question"},
        {"role": "tool", "tool_name": "first", "content": "a" * 2500},
        {"role": "tool", "tool_name": "second", "content": "b" * 2500},
        {"role": "tool", "tool_name": "latest", "content": "c" * 1000},
    ]

    bounded = agent._bounded_messages(messages)
    tool_messages = [item for item in bounded if item["role"] == "tool"]

    assert sum(len(item["content"]) for item in tool_messages) <= 4000
    assert __import__("json").loads(tool_messages[0]["content"])[
        "context_compacted"
    ] is True
    assert tool_messages[-1]["content"] == "c" * 1000
    assert messages[2]["content"] == "a" * 2500


@pytest.mark.asyncio
async def test_chat_sends_bounded_tool_context_to_model():
    ai = FakeAI([{"message": {"role": "assistant", "content": "Done."}}])
    agent = UnifiedMCPAgent(
        FakeMCP(),
        "key",
        "model",
        ai_client=ai,
        max_tool_context_chars=4000,
        compacted_tool_result_chars=500,
    )
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "question"},
        {"role": "tool", "tool_name": "first", "content": "a" * 3000},
        {"role": "tool", "tool_name": "latest", "content": "b" * 3000},
    ]

    response = await agent._chat(messages, [])

    sent = ai.requests[0][1]["json"]["messages"]
    sent_tool_chars = sum(
        len(item["content"]) for item in sent if item["role"] == "tool"
    )
    assert response["content"] == "Done."
    assert sent_tool_chars <= 4000
    assert messages[-1]["content"] == "b" * 3000


@pytest.mark.asyncio
async def test_streaming_chat_sends_bounded_tool_context_to_model():
    ai = FakeStreamingAI([
        '{"message":{"role":"assistant","content":"Done."}}',
        '{"done":true}',
    ])
    agent = UnifiedMCPAgent(
        FakeMCP(),
        "key",
        "model",
        ai_client=ai,
        max_tool_context_chars=4000,
        compacted_tool_result_chars=500,
    )
    messages = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "question"},
        {"role": "tool", "tool_name": "first", "content": "a" * 3000},
        {"role": "tool", "tool_name": "latest", "content": "b" * 3000},
    ]

    response = await agent._chat(messages, [])

    sent = ai.requests[0][2]["json"]["messages"]
    sent_tool_chars = sum(
        len(item["content"]) for item in sent if item["role"] == "tool"
    )
    assert response["content"] == "Done."
    assert sent_tool_chars <= 4000
    assert messages[-1]["content"] == "b" * 3000


def test_tool_search_discovers_declared_gateway():
    tools = {
        "hub_search_tools": MCPTool("hub_search_tools", "search", {}),
        "hub_read_files": MCPTool("hub_read_files", "files", {}),
    }
    result = MCPToolResult(
        "hub_search_tools", {}, {}, "", {"matches": [{"gateway": "hub_read_files"}]}
    )
    discovered = UnifiedMCPAgent._discovered_tools(result, tools)
    assert [tool.name for tool in discovered] == ["hub_read_files"]


def test_tool_search_does_not_expand_from_description_mentions():
    tools = {
        "hub_search_tools": MCPTool("hub_search_tools", "search", {}),
        "hub_manage_devices": MCPTool("hub_manage_devices", "manage", {}),
    }
    result = MCPToolResult(
        "hub_search_tools",
        {},
        {},
        "",
        {
            "matches": [{
                "gateway": "hub_read_devices",
                "description": "Related operations may mention hub_manage_devices.",
            }]
        },
    )

    assert UnifiedMCPAgent._discovered_tools(result, tools) == []


@pytest.mark.asyncio
async def test_repeated_tool_call_forces_final_answer_instead_of_round_error():
    repeated = {"message": {"role": "assistant", "content": "", "tool_calls": [{
        "function": {
            "name": "set_switch",
            "arguments": {"device_id": "42", "state": "on"},
        }
    }]}}
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "set switch"},
            }
        }]}},
        repeated,
        repeated,
        {"message": {"role": "assistant", "content": "The couch lamp is on."}},
    ])
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai,
        require_sensitive_confirmation=False,
    )

    answer = await agent.process_user_request("Turn on the couch lamp")

    assert answer == "The couch lamp is on."
    assert [name for name, _ in mcp.calls] == [
        "hub_search_tools",
        "hub_search_tools",
        "set_switch",
    ]
    assert ai.requests[-1][1]["json"]["tools"] is None


@pytest.mark.asyncio
async def test_control_request_cannot_claim_done_without_write_tool():
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "Done."}},
        {"message": {"role": "assistant", "content": "Still done."}},
    ])
    agent = UnifiedMCPAgent(
        FakeMCP(), "key", "model", ai_client=ai,
        require_sensitive_confirmation=False,
    )

    answer = await agent.process_user_request("turn off hallway lights")

    assert answer == "I could not retrieve verified live Hubitat evidence, so I will not provide an inferred answer."
    assert "did not execute a Hubitat control tool" not in answer
    assert len(ai.requests) == 2


@pytest.mark.asyncio
async def test_control_request_retries_once_and_executes_tool():
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "I will do that."}},
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "hub_search_tools",
                "arguments": {"query": "set switch"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "set_switch",
                "arguments": {"device_id": "42", "state": "off"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "The couch lamp is off."}},
    ])
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai,
        require_sensitive_confirmation=False,
    )
    answer = await agent.process_user_request("turn off the couch lamp")
    assert answer == "The couch lamp is off."
    assert mcp.calls[-1] == ("set_switch", {"device_id": "42", "state": "off"})


@pytest.mark.asyncio
async def test_control_prompt_documents_fast_routine_commands():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("turn off the couch lamp")
    assert "ROUTINE DEVICE CONTROL" in instruction
    assert "do not require confirmation" in instruction
    assert "only when the user explicitly requests a state change" in instruction
    assert "Never call it for status, history, 'why', or 'which' questions" in instruction


@pytest.mark.asyncio
async def test_log_prompt_requires_actual_hub_get_logs_call():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("check hub logs")
    assert "LIVE HUB LOG RULES" in instruction
    assert "tool='hub_get_logs'" in instruction
    assert "'since': '30m'" in instruction
    assert "Never infer logs" in instruction


def test_live_log_call_detection_requires_exact_gateway_subtool():
    assert UnifiedMCPAgent._is_live_log_call(
        "hub_read_diagnostics",
        {"tool": "hub_get_logs", "args": {"since": "30m"}},
    )
    assert not UnifiedMCPAgent._is_live_log_call(
        "hub_read_diagnostics",
        {"tool": "hub_get_metrics", "args": {}},
    )


@pytest.mark.asyncio
async def test_log_question_refuses_inferred_answer_after_retry():
    class LogMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_read_diagnostics", "diagnostics", {"type": "object"}),
            ]

    ai = FakeAI([
        {"message": {"role": "assistant", "content": "The logs look busy."}},
        {"message": {"role": "assistant", "content": "They still look busy."}},
    ])
    agent = UnifiedMCPAgent(LogMCP(), "key", "model", ai_client=ai)
    answer = await agent.process_user_request("check hub logs")
    assert "could not retrieve the actual Hubitat logs" in answer
    assert len(ai.requests) == 2


def test_app_gateways_are_added_only_from_search_results():
    tools = [
        MCPTool("hub_read_devices", "devices", {"type": "object"}),
        MCPTool("hub_read_apps_code", "apps", {"type": "object"}),
        MCPTool(
            "hub_manage_native_rules_and_apps", "manage apps", {"type": "object"}
        ),
        MCPTool("hub_manage_logs", "logs", {"type": "object"}),
    ]
    selected = UnifiedMCPAgent._initial_tools(tools)
    assert selected == []
    result = MCPToolResult(
        "hub_search_tools", {}, {}, "",
        {"matches": [{"gateway": "hub_manage_native_rules_and_apps"}]},
    )
    discovered = UnifiedMCPAgent._discovered_tools(
        result, {tool.name: tool for tool in tools}
    )
    assert [tool.name for tool in discovered] == [
        "hub_manage_native_rules_and_apps"
    ]


@pytest.mark.asyncio
async def test_app_prompt_uses_cached_app_manifest_and_omits_devices():
    class AppMCP(FakeMCP):
        async def list_tools(self):
            return [
                MCPTool("hub_read_apps_code", "apps", {"type": "object"}),
                MCPTool(
                    "hub_manage_native_rules_and_apps",
                    "manage apps",
                    {"type": "object"},
                ),
            ]

        async def get_cached_devices(self):
            raise AssertionError("device manifest should not load for app requests")

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"apps": [{"id": "3995", "label": "01. Humidity Controller"}]},
            )

    mcp = AppMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=FakeAI([]))
    prompt = await agent._system_prompt("pause humidity app")
    again = await agent._system_prompt("resume humidity app")
    assert "'01. Humidity Controller' | appId: 3995" in prompt
    assert "hub_set_rule_paused" in prompt
    assert again
    assert len(mcp.calls) == 1
