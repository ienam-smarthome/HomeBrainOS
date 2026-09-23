from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def _device() -> dict:
    return {
        "id": "4222",
        "label": "Dehumidifier 2",
        "name": "Dehumidifier 2",
        "room": "Dehumidifier",
        "capabilities": ["Switch"],
        "attributes": {"switch": "off"},
        "commands": ["on", "off"],
    }


_SWITCH_EVENTS = [
    {
        "name": "switch",
        "value": "off",
        "date": "2026-09-23T08:27:23.601+0100",
        "isStateChange": True,
        "type": "digital",
    },
    {
        "name": "switch",
        "value": "on",
        "date": "2026-09-23T06:57:23.391+0100",
        "isStateChange": True,
        "type": "digital",
    },
    {
        "name": "switch",
        "value": "off",
        "date": "2026-09-22T22:38:13.489+0100",
        "isStateChange": True,
        "type": "digital",
    },
]


class _OverlapMCP:
    def __init__(self, transition: str) -> None:
        self.transition = transition
        self.calls: list[str | None] = []
        self.active = 0
        self.peak = 0
        self.started: set[str | None] = set()
        self._both_started = asyncio.Event()

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        assert name == "hub_read_devices"
        assert arguments.get("tool") == "hub_list_device_events"
        args = arguments.get("args") or {}
        assert args.get("deviceId") == "4222"
        attribute = args.get("attribute")
        self.calls.append(attribute)

        self.active += 1
        self.peak = max(self.peak, self.active)
        self.started.add(attribute)
        if {"switch", f"command-{self.transition}"} <= self.started:
            self._both_started.set()

        try:
            # This makes the test prove overlap rather than merely inspect task
            # creation. A sequential implementation times out here.
            await asyncio.wait_for(self._both_started.wait(), timeout=0.5)

            if attribute == "switch":
                events = list(_SWITCH_EVENTS)
            elif attribute == f"command-{self.transition}":
                if self.transition == "on":
                    events = [{
                        "name": "command-on",
                        "value": None,
                        "date": "2026-09-23T06:57:23.292+0100",
                        "description": "Command called: on()",
                        "isStateChange": False,
                        "type": "command",
                        "producedBy": {
                            "name": "Ikea Rodret (Livingroom): button 2 pushed",
                            "appId": 3700,
                        },
                    }]
                else:
                    events = [{
                        "name": "command-off",
                        "value": None,
                        "date": "2026-09-23T08:27:23.518+0100",
                        "description": "Command called: off()",
                        "isStateChange": False,
                        "type": "command",
                        "producedBy": {
                            "name": "01. Humidity Controller",
                            "appId": 3995,
                        },
                    }]
            else:
                raise AssertionError(("unexpected event read", attribute))

            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"events": events, "count": len(events)},
            )
        finally:
            self.active -= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("transition", ["on", "off"])
async def test_requested_command_provenance_overlaps_switch_history(
    transition: str,
) -> None:
    mcp = _OverlapMCP(transition)
    service = DeviceHistoryService(mcp, lambda *_a, **_k: None)

    result = await service.history({
        "name": "Dehumidifier 2",
        "attribute": "switch",
        "limit": 3,
        "_resolved_target": _device(),
        "_include_command_provenance": True,
        "_causal_transition": transition,
    })

    assert result.is_error is False
    assert result.data["causationAvailable"] is True
    assert mcp.peak == 2
    assert set(mcp.calls) == {"switch", f"command-{transition}"}
    assert len(mcp.calls) == 2
    assert {
        row["name"]
        for row in result.data["commandEvents"]
    } == {f"command-{transition}"}


def test_single_command_correlation_keeps_closed_interval_context() -> None:
    evidence = [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Dehumidifier 2",
            "temporalAnalysis": {
                "observedIntervals": [{
                    "start": "2026-09-23T06:57:23.391+0100",
                    "end": "2026-09-23T08:27:23.601+0100",
                    "durationSeconds": 5400,
                    "duration": "1h 30m",
                }],
            },
            "commandEvents": [{
                "name": "command-on",
                "date": "2026-09-23T06:57:23.292+0100",
                "description": "Command called: on()",
                "type": "command",
                "producedBy": {
                    "label": "Ikea Rodret (Livingroom): button 2 pushed",
                    "id": "3700",
                    "type": "app",
                },
            }],
        },
    }]

    from causal_command_provenance import render_command_producer_answer

    message = render_command_producer_answer(evidence, transition="on")

    assert message is not None
    assert "Ikea Rodret (Livingroom): button 2 pushed" in message
    assert "99 ms later" in message
    assert "reported OFF at 8:27:23 AM" in message
    assert "after 1 hour 30 minutes" in message
    assert "01. Humidity Controller" not in message
