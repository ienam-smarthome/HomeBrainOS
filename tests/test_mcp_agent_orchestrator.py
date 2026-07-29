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
        return [MCPTool("set_switch", "Set switch", {"type": "object"})]

    async def get_cached_devices(self):
        return [{"id": "42", "label": "Couch Lamp", "room": "Lounge"}]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
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
    assert mcp.calls == [("set_switch", {"device_id": "42", "state": "on"})]
    assert ai.requests[0][0] == "https://ollama.com/api/chat"
    assert ai.requests[0][1]["headers"]["Authorization"] == "Bearer test-key"
    messages = ai.requests[1][1]["json"]["messages"]
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_name"] == "set_switch"


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
async def test_manifest_contains_live_device_identity():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("What is the couch lamp state?")
    assert "'Couch Lamp' | ID: 42 | Room: Lounge" in instruction


@pytest.mark.asyncio
async def test_non_device_prompt_omits_device_manifest():
    class NoDeviceMCP(FakeMCP):
        async def get_cached_devices(self):
            raise AssertionError("unrelated requests must not load the device manifest")

    agent = UnifiedMCPAgent(NoDeviceMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("Is a software update available?")
    assert "Device manifest omitted or unavailable." in instruction


def test_default_and_diagnostic_tool_sets_are_lean():
    tools = [
        MCPTool("hub_get_info", "info", {"type": "object"}),
        MCPTool("hub_search_tools", "search", {"type": "object"}),
        MCPTool("hub_read_diagnostics", "diagnostics", {"type": "object"}),
        MCPTool("hub_read_devices", "devices", {"type": "object"}),
        MCPTool("hub_update_firmware", "firmware", {"type": "object"}),
    ]

    default = UnifiedMCPAgent._select_tools("help me inspect the hub", tools)
    update = UnifiedMCPAgent._select_tools("software update available?", tools)
    install = UnifiedMCPAgent._select_tools("install the firmware update", tools)

    assert [tool.name for tool in default] == ["hub_get_info", "hub_search_tools"]
    assert [tool.name for tool in update] == [
        "hub_get_info", "hub_search_tools", "hub_read_diagnostics",
    ]
    assert [tool.name for tool in install] == [
        "hub_get_info", "hub_search_tools", "hub_read_diagnostics",
        "hub_update_firmware",
    ]


def test_read_state_question_is_not_misclassified_as_mutation():
    assert not UnifiedMCPAgent._requests_mutation("Which switches are on?")
    assert not UnifiedMCPAgent._requests_mutation("Which doors are open?")
    assert UnifiedMCPAgent._requests_mutation("turn off hallway lights")
    assert UnifiedMCPAgent._requests_mutation("pause humidity app")
    assert UnifiedMCPAgent._requests_mutation("install the firmware update")


def test_general_request_classification():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    assert agent._classify_request("hello", "s") == "conversational"
    assert agent._classify_request("What is the hub status?", "s") == "live-read"
    assert agent._classify_request("turn off hallway lights", "s") == "write"


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
            return [MCPTool("hub_get_info", "Hub info", {"type": "object"})]

    ai = FakeAI([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {
                "name": "hub_get_info",
                "arguments": {"includeAppUpdate": True, "token": "secret-value"},
            }
        }]}},
        {"message": {"role": "assistant", "content": "The hub is healthy."}},
    ])
    agent = UnifiedMCPAgent(ReadMCP(), "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Check hub status")

    assert outcome.message == "The hub is healthy."
    assert outcome.evidence[0]["tool"] == "hub_get_info"
    assert outcome.evidence[0]["supports_live_claim"] is True
    assert outcome.evidence[0]["arguments"]["token"] == "[redacted]"
    assert outcome.evidence[0]["timestamp"].endswith("+00:00")


def test_read_queries_exclude_manage_gateways():
    tools = [
        MCPTool("hub_read_devices", "read devices", {}),
        MCPTool("hub_manage_devices", "manage devices", {}),
        MCPTool("hub_read_rooms", "read rooms", {}),
        MCPTool("hub_manage_rooms", "manage rooms", {}),
        MCPTool("hub_search_tools", "search", {}),
        MCPTool("hub_get_info", "info", {}),
    ]
    switches = UnifiedMCPAgent._select_tools("Which switches are on?", tools)
    rooms = UnifiedMCPAgent._select_tools("List my Hubitat rooms", tools)
    control = UnifiedMCPAgent._select_tools("turn off hallway lights", tools)
    assert "hub_manage_devices" not in [tool.name for tool in switches]
    assert [tool.name for tool in rooms] == [
        "hub_read_rooms", "hub_search_tools",
    ]
    assert "hub_search_tools" not in [tool.name for tool in switches]
    assert "hub_manage_devices" in [tool.name for tool in control]


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
        {
            "message": {
                "role": "assistant",
                "content": "Fridge Door is 14% and Livingroom TRV is 10%.",
            }
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which batteries are low?")

    assert outcome.message == "Fridge Door is 14% and Livingroom TRV is 10%."
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    kinds = [receipt["evidence_kind"] for receipt in outcome.evidence]
    assert kinds == [
        "identity_manifest",
        "authoritative_state_snapshot",
        "deterministic_attribute_filter",
    ]
    assert outcome.evidence[-1]["supports_live_claim"] is True
    declared = ai.requests[0][1]["json"]["tools"]
    assert [item["function"]["name"] for item in declared] == [
        "hub_read_devices",
        "homebrain_filter_devices",
    ]


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
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "homebrain_active_rooms",
                        "arguments": {},
                    }
                }],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Bedroom 3 and Living Room are active.",
            }
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which rooms are active?")

    assert outcome.message == "Bedroom 3 and Living Room are active."
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
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "homebrain_active_switches",
                        "arguments": {},
                    }
                }],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "One non-light switch is on: Fridge.",
            }
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", "model", ai_client=ai)

    outcome = await agent.process_user_request_result("Which switches are on?")

    assert outcome.message == "One non-light switch is on: Fridge."
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert [receipt["evidence_kind"] for receipt in outcome.evidence] == [
        "identity_manifest",
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
async def test_weather_request_loads_device_manifest():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("What is the weather?")
    assert "'Couch Lamp' | ID: 42" in instruction


@pytest.mark.asyncio
async def test_manifest_includes_compact_live_states():
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
    assert "Current: motion=active, battery=91" in instruction


@pytest.mark.asyncio
async def test_update_prompt_requires_status_reconciliation():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("software update")
    assert "includeAppUpdate=true" in instruction
    assert "never summarize those values as up to date" in instruction


@pytest.mark.asyncio
async def test_low_battery_prompt_matches_dashboard_threshold():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("Which batteries are low?")
    assert "at or below 20 percent" in instruction
    assert "Exclude every device above 20 percent" in instruction


def test_device_health_query_gets_read_and_diagnostic_gateways():
    tools = [
        MCPTool("hub_read_devices", "devices", {}),
        MCPTool("hub_read_diagnostics", "diagnostics", {}),
        MCPTool("hub_manage_devices", "manage", {}),
        MCPTool("hub_search_tools", "search", {}),
    ]
    selected = UnifiedMCPAgent._select_tools(
        "List devices that are offline or stale", tools
    )
    assert [tool.name for tool in selected] == [
        "hub_read_devices", "hub_read_diagnostics",
        "hub_manage_devices",
    ]


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
async def test_health_manifest_includes_explicit_driver_status():
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
    assert "healthStatus=offline" in instruction
    assert "rtt=timeout" in instruction
    assert "Status=clear" in instruction


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


@pytest.mark.asyncio
async def test_repeated_tool_call_forces_final_answer_instead_of_round_error():
    repeated = {"message": {"role": "assistant", "content": "", "tool_calls": [{
        "function": {
            "name": "set_switch",
            "arguments": {"device_id": "42", "state": "on"},
        }
    }]}}
    ai = FakeAI([
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
    assert len(mcp.calls) == 1
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

    assert "did not execute a Hubitat control tool" in answer
    assert len(ai.requests) == 2


@pytest.mark.asyncio
async def test_control_request_retries_once_and_executes_tool():
    ai = FakeAI([
        {"message": {"role": "assistant", "content": "I will do that."}},
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
    assert mcp.calls == [("set_switch", {"device_id": "42", "state": "off"})]


@pytest.mark.asyncio
async def test_control_prompt_documents_fast_routine_commands():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model", ai_client=FakeAI([]))
    instruction = await agent._system_prompt("turn off the couch lamp")
    assert "ROUTINE DEVICE CONTROL" in instruction
    assert "do not require confirmation" in instruction


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


def test_app_request_limits_visible_gateways():
    tools = [
        MCPTool("hub_read_devices", "devices", {"type": "object"}),
        MCPTool("hub_read_apps_code", "apps", {"type": "object"}),
        MCPTool(
            "hub_manage_native_rules_and_apps", "manage apps", {"type": "object"}
        ),
        MCPTool("hub_manage_logs", "logs", {"type": "object"}),
    ]
    selected = UnifiedMCPAgent._select_tools("pause humidity app", tools)
    assert [tool.name for tool in selected] == [
        "hub_read_apps_code",
        "hub_manage_native_rules_and_apps",
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
