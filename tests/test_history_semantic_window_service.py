from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from history_time_windows import (  # noqa: E402
    parse_history_window_request,
    reset_history_window_request,
    set_history_window_request,
)
from mcp_client import MCPToolResult  # noqa: E402


LOCAL = timezone(timedelta(hours=1))
NOW = datetime(2026, 9, 17, 20, 0, tzinfo=LOCAL)


def _event(value: str, timestamp: str) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": True,
    }


BIG_LAMP_EVENTS = [
    _event("off", "2026-09-17T07:34:00.000+0100"),
    _event("on", "2026-09-17T04:56:00.000+0100"),
    _event("off", "2026-09-17T04:00:00.000+0100"),
    _event("on", "2026-09-17T03:49:00.000+0100"),
    _event("off", "2026-09-17T03:27:00.000+0100"),
    _event("on", "2026-09-17T03:00:00.100+0100"),
    _event("off", "2026-09-17T03:00:00.000+0100"),
    _event("on", "2026-09-17T02:37:00.000+0100"),
    _event("off", "2026-09-17T02:00:00.000+0100"),
    _event("on", "2026-09-17T01:08:00.000+0100"),
    _event("off", "2026-09-16T17:00:00.000+0100"),
]


class SemanticWindowMCP:
    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "devices": [{
                        "id": "7827",
                        "label": "Big lamp",
                        "capabilities": ["Switch"],
                        "commands": ["on", "off"],
                    }]
                },
            )
        if operation == "hub_list_device_events":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"events": self.events},
            )
        raise AssertionError((name, arguments))


def _event_call(mcp: SemanticWindowMCP) -> dict:
    return next(
        arguments
        for _name, arguments in reversed(mcp.calls)
        if arguments.get("tool") == "hub_list_device_events"
    )


@pytest.mark.asyncio
async def test_prompt_scoped_last_night_window_widens_fetch_and_clips_locally() -> None:
    mcp = SemanticWindowMCP(BIG_LAMP_EVENTS)
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: None,
        now=lambda: NOW,
    )
    token = set_history_window_request(
        parse_history_window_request("How long was big lamp on last night?")
    )
    try:
        result = await service.history({
            "name": "big lamp",
            "attribute": "switch",
            "hours_back": 24,
        })
    finally:
        reset_history_window_request(token)

    assert result.is_error is False
    assert isinstance(result.data, dict)
    data = result.data
    assert _event_call(mcp)["args"]["hoursBack"] == 27
    assert data["hoursBack"] == 27
    assert data["timeWindow"]["kind"] == "last_night"
    assert data["timeWindow"]["label"] == "last night"
    assert data["timeWindow"]["start"] == "2026-09-16T18:00:00+01:00"
    assert data["timeWindow"]["end"] == "2026-09-17T08:00:00+01:00"
    assert data["timeWindow"]["sourceCompleteToStart"] is True
    assert data["timeWindow"]["sourcePageCompleteToStart"] is True
    assert data["historySourceIntegrity"] == "unverified"
    assert data["historySourceIntegrityVerified"] is False
    analysis = data["temporalAnalysis"]
    assert analysis["windowed"] is True
    assert analysis["totalActiveSeconds"] == 16260
    assert analysis["totalActiveDuration"] == "4h 31m"
    assert analysis["intervalCount"] == 5
    assert analysis["coverage"] == "partial"
    assert analysis["totalIsLowerBound"] is False
    assert analysis["durationReliability"] == "unverified-event-stream"
    assert analysis["sourceIntegrityVerified"] is False


@pytest.mark.asyncio
async def test_semantic_window_context_resets_for_next_ordinary_history_read() -> None:
    mcp = SemanticWindowMCP(BIG_LAMP_EVENTS)
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: None,
        now=lambda: NOW,
    )
    token = set_history_window_request(
        parse_history_window_request("How long was big lamp on last night?")
    )
    try:
        await service.history({"name": "big lamp", "attribute": "switch"})
    finally:
        reset_history_window_request(token)

    result = await service.history({"name": "big lamp", "attribute": "switch"})

    assert result.is_error is False
    assert isinstance(result.data, dict)
    assert _event_call(mcp)["args"]["hoursBack"] == 24
    assert result.data["hoursBack"] == 24
    assert "timeWindow" not in result.data
    assert result.data["temporalAnalysis"].get("windowed") is None


@pytest.mark.asyncio
async def test_full_event_page_that_does_not_reach_window_start_stays_partial() -> None:
    newest = datetime(2026, 9, 16, 19, 49, tzinfo=LOCAL)
    events: list[dict] = []
    for index in range(50):
        timestamp = newest - timedelta(minutes=index)
        value = "off" if index % 2 == 0 else "on"
        events.append(_event(value, timestamp.isoformat()))

    mcp = SemanticWindowMCP(events)
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: None,
        now=lambda: NOW,
    )
    token = set_history_window_request(
        parse_history_window_request("How long was big lamp on last night?")
    )
    try:
        result = await service.history({"name": "big lamp", "attribute": "switch"})
    finally:
        reset_history_window_request(token)

    assert result.is_error is False
    assert isinstance(result.data, dict)
    assert result.data["timeWindow"]["sourceCompleteToStart"] is False
    assert result.data["timeWindow"]["sourcePageCompleteToStart"] is False
    analysis = result.data["temporalAnalysis"]
    assert analysis["boundaryStateKnown"] is False
    assert analysis["coverage"] == "partial"
    assert analysis["totalIsLowerBound"] is False
    assert analysis["durationReliability"] == "unverified-event-stream"
    assert analysis["sourceIntegrityVerified"] is False
