from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


def _device() -> dict:
    return {
        "id": "7841",
        "name": "Bedroom 3 Light",
        "label": "Bedroom 3 Light",
        "room": "Bedroom 3",
        "capabilities": ["Switch", "Light"],
        "attributes": {"switch": "off"},
        "commands": ["on", "off"],
    }


class ResolutionReuseMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if name == "hub_read_devices" and operation == "hub_list_devices":
            return MCPToolResult(
                name, arguments, {}, "ok", {"devices": [_device()]}
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
                            "name": "switch",
                            "value": "off",
                            "date": "2026-09-18T01:45:02+01:00",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-09-18T01:32:51+01:00",
                            "isStateChange": True,
                        },
                    ]
                },
            )
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_history_reuses_request_local_device_resolution_across_service_instances() -> None:
    mcp = ResolutionReuseMCP()
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        resolver = DeviceQueryService(mcp, lambda *_a, **_k: None)
        resolved = await resolver.resolve_device({"name": "bedroom 3 light"})
        assert resolved.data["matched"] is True
        assert resolved.data["requestCacheHit"] is False

        history = DeviceHistoryService(mcp, lambda *_a, **_k: None)
        result = await history.history(
            {"name": "Bedroom 3 Light", "attribute": "switch", "hours_back": 24}
        )

        assert result.is_error is False
        list_device_calls = [
            args
            for name, args in mcp.calls
            if name == "hub_read_devices" and args.get("tool") == "hub_list_devices"
        ]
        event_calls = [
            args
            for name, args in mcp.calls
            if name == "hub_read_devices"
            and args.get("tool") == "hub_list_device_events"
        ]
        assert len(list_device_calls) == 1
        assert len(event_calls) == 1
        assert metrics.snapshot()["counters"]["resolution_cache_hit"] == 1
    finally:
        metrics.reset(token)


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


class HistoryOnlyMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.devices = [
            {
                "id": "42",
                "label": "Lounge Lamp",
                "name": "Lounge Lamp",
                "room": "Lounge",
                "capabilities": ["Switch", "Light"],
                "attributes": {"switch": "off"},
                "commands": ["on", "off"],
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
                name, arguments, {}, "ok", {"devices": list(self.devices)}
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
                            "name": "switch",
                            "value": "off",
                            "date": "2026-09-18T07:10:00+01:00",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-09-18T07:00:00+01:00",
                            "isStateChange": True,
                        },
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


@pytest.mark.asyncio
async def test_successful_noncausal_history_forces_synthesis_before_unrelated_reads() -> None:
    mcp = HistoryOnlyMCP()
    ai = FakeAI(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        _call(
                            "homebrain_device_history",
                            {
                                "name": "Lounge Lamp",
                                "attribute": "switch",
                                "hours_back": 24,
                            },
                        )
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "The recorded switch rows show one bounded ten-minute "
                        "on interval for Lounge Lamp."
                    ),
                }
            },
        ]
    )
    agent = UnifiedMCPAgent(mcp, "key", "gemma4:31b", ai_client=ai)

    outcome = await agent.process_user_request_result(
        "How long was Lounge Lamp on in the last 24 hours?"
    )

    assert outcome.metrics["counters"]["evidence_sufficiency_stop"] == 1
    assert outcome.metrics["counters"]["model_rounds"] == 2
    assert len(ai.requests) == 2
    assert ai.requests[1][1]["json"].get("tools") in (None, [])
    assert not any(
        args.get("tool") in {"hub_list_rules", "hub_get_logs"}
        for _name, args in mcp.calls
    )
    assert not any(
        args.get("resource") == "hubitat://context"
        for _name, args in mcp.calls
    )


@pytest.mark.parametrize(
    "prompt",
    [
        "Why was Lounge Lamp on earlier?",
        "What caused Lounge Lamp to turn on earlier?",
        "Was Lounge Lamp behaving normally earlier?",
    ],
)
@pytest.mark.asyncio
async def test_investigative_history_is_not_hard_stopped_by_sufficiency_gate(
    prompt: str,
) -> None:
    mcp = HistoryOnlyMCP()
    ai = FakeAI(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        _call(
                            "homebrain_device_history",
                            {
                                "name": "Lounge Lamp",
                                "attribute": "switch",
                                "hours_back": 24,
                            },
                        )
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "The history establishes the switch event, but not its cause."
                    ),
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "At 7:00 am the recorded history establishes the switch-on "
                        "event, but the current-turn evidence does not establish its cause."
                    ),
                }
            },
        ]
    )
    agent = UnifiedMCPAgent(mcp, "key", "gemma4:31b", ai_client=ai)

    outcome = await agent.process_user_request_result(prompt)

    assert outcome.metrics["counters"].get("evidence_sufficiency_stop", 0) == 0
    assert outcome.metrics["counters"].get("investigative_finalization", 0) == 1
    assert len(ai.requests) == 3
    # Because the request is investigative, the second ordinary reasoning turn
    # keeps callable tools available. Its no-tool draft is then routed through
    # the shared no-tools final synthesis coordinator.
    assert ai.requests[1][1]["json"]["tools"]
    assert ai.requests[2][1]["json"].get("tools") in (None, [])
