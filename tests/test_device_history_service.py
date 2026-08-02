from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from deterministic_tool_presenter import present_tool_result  # noqa: E402
from device_history_service import (  # noqa: E402
    DEVICE_GATEWAY,
    DEVICE_HISTORY_TOOL,
    EVENT_OPERATION,
    DeviceHistoryService,
)
from mcp_client import MCPToolResult  # noqa: E402
from tool_registry import (  # noqa: E402
    EVIDENCE_KINDS,
    ToolEffect,
    classify_tool_effect,
    device_history_tool,
)


class HistoryMCP:
    def __init__(self, *, resolve: bool = True) -> None:
        self.resolve = resolve
        self.calls: list[tuple[str, dict]] = []

    async def get_cached_devices(self):
        if not self.resolve:
            return []
        return [{
            "id": "42",
            "label": "Livingroom Light 1",
            "capabilities": ["Switch"],
            "commands": ["on", "off"],
        }]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            devices = []
            if self.resolve:
                devices = [{
                    "id": "42",
                    "label": "Livingroom Light 1",
                    "capabilities": ["Switch"],
                    "commands": ["on", "off"],
                }]
            return MCPToolResult(name, arguments, {}, "ok", {"devices": devices})
        if operation == EVENT_OPERATION:
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "source": "device",
                    "deviceId": "42",
                    "device": "Livingroom Light 1",
                    "events": [
                        {
                            "name": "switch",
                            "value": "off",
                            "date": "2026-08-01T12:30:00.000+0100",
                            "description": "Livingroom Light 1 was turned off",
                            "isStateChange": True,
                        },
                        {
                            "name": "switch",
                            "value": "on",
                            "date": "2026-08-01T11:00:00.000+0100",
                            "descriptionText": "Livingroom Light 1 was turned on",
                            "isStateChange": True,
                        },
                    ],
                    "count": 2,
                },
            )
        raise AssertionError(f"unexpected operation: {operation}")


@pytest.mark.asyncio
async def test_reads_bounded_authoritative_history_after_targeted_resolution():
    mcp = HistoryMCP()
    receipts = []
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: receipts.append((args, kwargs)),
    )

    result = await service.history({
        "name": "living room light 1",
        "hours_back": 999,
        "attribute": "switch",
        "limit": 500,
    })

    assert result.is_error is False
    assert result.data["label"] == "Livingroom Light 1"
    assert result.data["hoursBack"] == 168
    assert result.data["count"] == 2
    assert result.data["causationAvailable"] is False
    assert mcp.calls[-1] == (
        DEVICE_GATEWAY,
        {
            "tool": EVENT_OPERATION,
            "args": {
                "deviceId": "42",
                "hoursBack": 168,
                "limit": 50,
                "attribute": "switch",
            },
        },
    )
    assert receipts[-1][1]["evidence_kind"] == (
        "authoritative_device_event_history"
    )
    assert receipts[-1][1]["success"] is True


@pytest.mark.asyncio
async def test_short_name_resolves_prefixed_hyphenated_device_before_history():
    class PrefixedHistoryMCP(HistoryMCP):
        def __init__(self):
            super().__init__()
            self.devices = [{
                "id": "6916",
                "label": "Block Tab-S9-FE",
                "capabilities": ["Switch"],
                "commands": ["blockInternet", "allowInternet"],
            }]

        async def get_cached_devices(self):
            return self.devices

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            operation = arguments.get("tool")
            if operation == "hub_list_devices":
                assert arguments.get("args") == {}
                return MCPToolResult(
                    name, arguments, {}, "ok", {"devices": self.devices}
                )
            if operation == EVENT_OPERATION:
                return MCPToolResult(
                    name,
                    arguments,
                    {},
                    "ok",
                    {
                        "events": [{
                            "name": "switch",
                            "value": "off",
                            "date": "2026-08-01T14:55:00.000+0100",
                            "isStateChange": True,
                        }]
                    },
                )
            raise AssertionError(f"unexpected operation: {operation}")

    mcp = PrefixedHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "tab s9"})

    assert result.is_error is False
    assert result.data["deviceId"] == "6916"
    assert result.data["label"] == "Block Tab-S9-FE"
    inventory_calls = [
        (name, arguments)
        for name, arguments in mcp.calls
        if arguments.get("tool") == "hub_list_devices"
    ]
    assert inventory_calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert mcp.calls[-1][1]["args"]["deviceId"] == "6916"


@pytest.mark.asyncio
async def test_unresolved_device_never_reads_event_history():
    mcp = HistoryMCP(resolve=False)
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)

    result = await service.history({"name": "missing lamp"})

    assert result.is_error is True
    assert result.data["success"] is False
    assert all(
        arguments.get("tool") != EVENT_OPERATION
        for _, arguments in mcp.calls
    )


def test_history_tool_is_a_bounded_read_only_local_schema():
    tool = device_history_tool()

    assert tool.name == DEVICE_HISTORY_TOOL
    assert tool.input_schema["required"] == ["name"]
    assert tool.input_schema["properties"]["hours_back"]["maximum"] == 168
    assert tool.input_schema["properties"]["limit"]["maximum"] == 50
    assert classify_tool_effect(tool, {"name": "lamp"}) is ToolEffect.READ
    assert EVIDENCE_KINDS[DEVICE_HISTORY_TOOL] == (
        "deterministic_device_event_history"
    )


def test_history_presenter_reports_transitions_without_inventing_cause():
    message = present_tool_result(
        DEVICE_HISTORY_TOOL,
        {
            "success": True,
            "label": "Livingroom Light 1",
            "hoursBack": 24,
            "count": 1,
            "events": [{
                "name": "switch",
                "value": "off",
                "date": "2026-08-01T12:30:00.000+0100",
                "description": "Livingroom Light 1 was turned off",
            }],
        },
    )

    assert "Recent history for **Livingroom Light 1**" in message
    assert "**switch: off**" in message
    assert "do not by themselves identify what caused them" in message


def test_empty_history_is_explicit_about_window_and_attribute():
    message = present_tool_result(
        DEVICE_HISTORY_TOOL,
        {
            "success": True,
            "label": "Hallway Motion",
            "hoursBack": 6,
            "attribute": "motion",
            "events": [],
        },
    )

    assert message == (
        "No motion events were reported for **Hallway Motion** in the last "
        "6 hours."
    )
