from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


class HistoryWindowMCP:
    def __init__(self) -> None:
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
                {
                    "events": [
                        {
                            "name": "switch",
                            "value": "off",
                            "date": "2026-09-17T07:34:00.000+0100",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-09-17T04:56:00.000+0100",
                            "isStateChange": True,
                        },
                    ]
                },
            )
        raise AssertionError((name, arguments))


async def _history(arguments: dict) -> tuple[HistoryWindowMCP, dict]:
    mcp = HistoryWindowMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)
    result = await service.history(arguments)
    assert result.is_error is False
    assert isinstance(result.data, dict)
    return mcp, result.data


@pytest.mark.asyncio
async def test_attribute_analysis_without_small_limit_defaults_to_24_hours() -> None:
    mcp, data = await _history({"name": "big lamp", "attribute": "switch"})

    event_call = next(
        arguments
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_device_events"
    )
    assert event_call["args"]["hoursBack"] == 24
    assert data["hoursBack"] == 24


@pytest.mark.asyncio
async def test_point_lookup_with_explicit_small_limit_keeps_7_day_widening() -> None:
    mcp, data = await _history(
        {"name": "big lamp", "attribute": "switch", "limit": 2}
    )

    event_call = next(
        arguments
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_device_events"
    )
    assert event_call["args"]["hoursBack"] == 168
    assert data["hoursBack"] == 168


@pytest.mark.asyncio
async def test_explicit_hours_back_always_wins_over_default_window_policy() -> None:
    mcp, data = await _history(
        {"name": "big lamp", "attribute": "switch", "limit": 2, "hours_back": 12}
    )

    event_call = next(
        arguments
        for _name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_device_events"
    )
    assert event_call["args"]["hoursBack"] == 12
    assert data["hoursBack"] == 12
