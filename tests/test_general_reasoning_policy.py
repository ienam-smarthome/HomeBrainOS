from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from chat_transport import ChatTransport  # noqa: E402
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from reasoning_policy import (  # noqa: E402
    EVIDENCE_REVIEW_INSTRUCTION,
    FINAL_SYNTHESIS_INSTRUCTION,
    active_tool_round_size,
    observe_assistant_message,
    should_defer_deterministic_presentation,
)


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


class ReasoningMCP:
    """Minimal live-state + location-history MCP for model-loop regressions."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.devices = [
            {
                "id": "42",
                "label": "Lounge Lamp",
                "room": "Lounge",
                "capabilities": ["Switch", "Light"],
                "attributes": {"switch": "on"},
            }
        ]

    async def list_tools(self):
        return []

    async def get_cached_devices(self):
        return list(self.devices)

    def peek_cached_devices(self):
        return list(self.devices)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if name == "hub_read_devices" and operation == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"devices": list(self.devices)},
            )
        if name == "hub_read_devices" and operation == "hub_list_device_events":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "mode",
                            "value": "Evening",
                            "date": "2026-09-17T19:00:00+01:00",
                            "isStateChange": True,
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected MCP call: {name} {arguments}")


def _call(name: str, arguments: dict | None = None) -> dict:
    return {
        "function": {
            "name": name,
            "arguments": arguments or {},
        }
    }


def test_reasoning_policy_is_tool_round_based_not_prompt_based() -> None:
    observe_assistant_message({
        "role": "assistant",
        "content": "",
        "tool_calls": [_call("homebrain_active_lights"), _call("homebrain_location_events")],
    })
    try:
        assert active_tool_round_size() == 2
        assert should_defer_deterministic_presentation(
            "homebrain_active_lights", {"lights": []}
        ) is True
        assert should_defer_deterministic_presentation(
            "homebrain_device_history", {"events": []}
        ) is False
    finally:
        observe_assistant_message({"role": "assistant", "content": "done"})


def test_reasoning_instructions_are_generic_and_causally_conservative() -> None:
    review = EVIDENCE_REVIEW_INSTRUCTION.casefold()
    final = FINAL_SYNTHESIS_INSTRUCTION.casefold()
    assert "original request" in review
    assert "every material part" in review
    assert "correlation" in review and "causation" in review
    assert "do not reveal hidden reasoning" in review
    assert "using only the evidence already gathered" in final
    assert "correlation" in final and "causation" in final


@pytest.mark.asyncio
async def test_multi_tool_round_executes_every_call_before_synthesis() -> None:
    """A deterministic presenter must not cut a native multi-call round in half."""

    mcp = ReasoningMCP()
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    _call("homebrain_active_lights"),
                    _call("homebrain_location_events", {"hours_back": 24}),
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": (
                    "The Lounge Lamp is on, and the hub most recently entered "
                    "Evening mode at 7:00 PM. Those facts are correlated in time, "
                    "but the evidence does not prove the mode caused the lamp."
                ),
            }
        },
    ])
    agent = UnifiedMCPAgent(mcp, "key", "gemma4:31b", ai_client=ai)

    answer = await agent.process_user_request(
        "Check the current lights and recent mode history, then tell me what they show."
    )

    assert len(ai.requests) == 2
    assert any(
        args.get("tool") == "hub_list_devices" for _, args in mcp.calls
    )
    assert any(
        args.get("tool") == "hub_list_device_events" for _, args in mcp.calls
    )
    second_messages = ai.requests[1][1]["json"]["messages"]
    tool_messages = [message for message in second_messages if message.get("role") == "tool"]
    assert [message.get("tool_name") for message in tool_messages[-2:]] == [
        "homebrain_active_lights",
        "homebrain_location_events",
    ]
    payloads = [json.loads(str(message["content"])) for message in tool_messages[-2:]]
    assert all("host_instruction" in payload for payload in payloads)
    assert "does not prove" in answer


@pytest.mark.asyncio
async def test_single_tool_round_keeps_deterministic_fast_presentation() -> None:
    """More reasoning must not add a provider round to a simple one-tool answer."""

    mcp = ReasoningMCP()
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [_call("homebrain_active_lights")],
            }
        }
    ])
    agent = UnifiedMCPAgent(mcp, "key", "gemma4:31b", ai_client=ai)

    answer = await agent.process_user_request("Which lights are on?")

    assert answer == "1 light is on: Lounge Lamp."
    assert len(ai.requests) == 1


@pytest.mark.asyncio
async def test_thinking_is_enabled_for_reasoning_models_and_trace_is_not_retained() -> None:
    ai = FakeAI([
        {
            "message": {
                "role": "assistant",
                "thinking": "private provider reasoning that must not be retained",
                "content": "Final answer only.",
            }
        }
    ])
    transport = ChatTransport("key", "gemma4:31b-cloud", ai_client=ai) if False else None

    # ChatTransport's injected client parameter is named `client`; keep this
    # test independent from the agent wrapper that calls it `ai_client`.
    transport = ChatTransport("key", "gemma4:31b-cloud", client=ai)
    message = await transport.chat([{"role": "user", "content": "status"}], [])

    request = ai.requests[0][1]["json"]
    assert request["think"] is True
    assert message == {"role": "assistant", "content": "Final answer only."}
    assert "thinking" not in message


def test_thinking_is_not_sent_to_unlisted_model_family() -> None:
    transport = ChatTransport("key", "llama3.2:3b", client=FakeAI([]))
    request = transport._request(
        [{"role": "user", "content": "hello"}],
        [],
        "llama3.2:3b",
        stream=False,
        keep_alive=None,
    )
    assert "think" not in request
