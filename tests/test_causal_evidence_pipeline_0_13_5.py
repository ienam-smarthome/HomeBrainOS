from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import (  # noqa: E402
    DEVICE_GATEWAY,
    EVENT_OPERATION,
    DeviceHistoryService,
)
from history_time_windows import (  # noqa: E402
    parse_history_window_request,
    reset_history_window_request,
    set_history_window_request,
)
from mcp_agent_orchestrator import (  # noqa: E402
    UNVERIFIED_MUTATION_REFUSAL,
    UnifiedMCPAgent,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402


class _WindowLocationMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"timeZone": "Europe/London"},
            )
        if name == DEVICE_GATEWAY and arguments.get("tool") == EVENT_OPERATION:
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "events": [
                        {
                            "name": "mode",
                            "value": "Night",
                            "description": "Hub is now in Night mode",
                            "date": "2026-09-18T23:00:01.921+0100",
                            "isStateChange": True,
                        },
                        {
                            "name": "mode",
                            "value": "Bedtime",
                            "description": "Hub is now in Bedtime mode",
                            "date": "2026-09-18T21:30:01.970+0100",
                            "isStateChange": True,
                        },
                        {
                            "name": "mode",
                            "value": "Late afternoon",
                            "description": "outside requested window",
                            "date": "2026-09-18T17:09:00.915+0100",
                            "isStateChange": True,
                        },
                        {
                            "name": "mode",
                            "value": "Late Night",
                            "description": "previous overnight period",
                            "date": "2026-09-18T01:30:02.403+0100",
                            "isStateChange": True,
                        },
                    ]
                },
            )
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_location_events_are_clipped_to_active_history_window() -> None:
    london = ZoneInfo("Europe/London")
    mcp = _WindowLocationMCP()
    receipts: list[tuple[tuple, dict]] = []
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: receipts.append((args, kwargs)),
        now=lambda: datetime(2026, 9, 19, 0, 7, 55, tzinfo=london),
    )
    token = set_history_window_request(
        parse_history_window_request(
            "Why was Bedroom 3 Light on during the night?"
        )
    )
    try:
        result = await service.location_events({"hours_back": 24, "limit": 50})
    finally:
        reset_history_window_request(token)

    assert result.is_error is False
    assert result.data["timeWindow"]["start"] == "2026-09-18T18:00:00+01:00"
    assert result.data["timeWindow"]["end"].startswith("2026-09-19T00:07:55")
    assert [event["value"] for event in result.data["events"]] == [
        "Night",
        "Bedtime",
    ]
    assert "Late Night" not in {
        event["value"] for event in result.data["events"]
    }
    event_call = next(
        arguments
        for name, arguments in mcp.calls
        if name == DEVICE_GATEWAY and arguments.get("tool") == EVENT_OPERATION
    )
    assert event_call["args"]["limit"] == 50
    raw_receipt = next(
        kwargs
        for args, kwargs in receipts
        if args and args[0] == DEVICE_GATEWAY
        and kwargs.get("evidence_kind") == "authoritative_location_event_history"
    )
    assert [row["value"] for row in raw_receipt["details"]["events"]] == [
        "Night",
        "Bedtime",
    ]


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeAI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return _FakeResponse(next(self.responses))

    async def aclose(self):
        return None


class _ReadOnlyMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool(
                "hub_search_tools",
                "Search tools",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics and logs",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_cached_devices(self):
        return []

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_search_tools":
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"results": []},
            )
        if name == "hub_read_diagnostics":
            return MCPToolResult(
                name,
                arguments,
                {},
                "",
                {"status": "ok"},
            )
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_undeclared_call_cannot_turn_read_request_into_write() -> None:
    mcp = _ReadOnlyMCP()
    ai = _FakeAI([
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "hub_read_diagnostics",
                        "arguments": {},
                    }
                }],
            }
        },
        {
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "totally_undeclared_tool",
                        "arguments": {},
                    }
                }],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Diagnostics were checked; no Hubitat action was run.",
            }
        },
    ])
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result("Check hub diagnostics")

    assert outcome.request_class == "live-read"
    assert outcome.message == "Diagnostics were checked; no Hubitat action was run."
    assert outcome.message != UNVERIFIED_MUTATION_REFUSAL
    assert not any(
        receipt.get("success") and receipt.get("mutates")
        for receipt in outcome.evidence
    )


def test_causal_location_metric_is_supported() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_location_read")
        assert metrics.snapshot()["counters"]["causal_location_read"] == 1
    finally:
        metrics.reset(token)
