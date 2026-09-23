from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_command_provenance import (  # noqa: E402
    command_producer_transition_sufficient,
    correlate_command_producers,
    render_command_producer_answer,
)
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _device() -> dict:
    return {
        "id": "4222",
        "label": "Dehumidifier 2",
        "name": "Dehumidifier 2",
        "room": "Dehumidifier",
        "capabilities": ["Switch", "PowerMeter", "EnergyMeter"],
        "attributes": {"switch": "off", "power": 0},
        "commands": ["on", "off"],
    }


def _producer_href(app_id: str, label: str) -> str:
    return (
        f"<a href='/installedapp/configure/{app_id}' target='_blank' "
        f"class='text-base'>{label}</a>"
    )


def _history_receipt() -> dict:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "arguments": {
            "name": "Dehumidifier 2",
            "attribute": "switch",
            "limit": 3,
        },
        "details": {
            "label": "Dehumidifier 2",
            "attribute": "switch",
            "temporalAnalysis": {
                "intervalCount": 1,
                "observedIntervals": [{
                    "start": "2026-09-23T06:57:23.391+0100",
                    "end": "2026-09-23T08:27:23.601+0100",
                    "startNatural": "6:57 am on Wednesday 23 September 2026",
                    "endNatural": "8:27 am on Wednesday 23 September 2026",
                    "durationSeconds": 5400,
                    "duration": "1h 30m",
                }],
            },
            "commandEvents": [
                {
                    "name": "command-off",
                    "description": "Command called: off()",
                    "date": "2026-09-23T08:27:23.518+0100",
                    "type": "command",
                    "source": "DEVICE",
                    "producedBy": {
                        "label": "01. Humidity Controller",
                        "id": "3995",
                        "type": "app",
                    },
                },
                {
                    "name": "command-on",
                    "description": "Command called: on()",
                    "date": "2026-09-23T06:57:23.292+0100",
                    "type": "command",
                    "source": "DEVICE",
                    "producedBy": {
                        "label": "Ikea Rodret (Livingroom): button 2 pushed",
                        "id": "3700",
                        "type": "app",
                    },
                },
            ],
        },
    }


class _OffCommandProducerMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.identity = _device()

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices. hub_list_device_events.",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics. hub_get_logs.",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_device_identities(self):
        return [dict(self.identity)]

    def peek_device_identities(self):
        return [dict(self.identity)]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        assert arguments.get("tool") == "hub_list_device_events", arguments
        args = arguments.get("args") or {}
        assert args.get("deviceId") == "4222"
        attribute = args.get("attribute")

        if attribute == "switch":
            events = [
                {
                    "name": "switch",
                    "value": "off",
                    "descriptionText": "switch attribute updated",
                    "date": "2026-09-23T08:27:23.601+0100",
                    "isStateChange": True,
                    "source": "DEVICE",
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "on",
                    "descriptionText": "switch attribute updated",
                    "date": "2026-09-23T06:57:23.391+0100",
                    "isStateChange": True,
                    "source": "DEVICE",
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "off",
                    "descriptionText": "switch attribute updated",
                    "date": "2026-09-22T22:38:13.489+0100",
                    "isStateChange": True,
                    "source": "DEVICE",
                    "type": "digital",
                },
            ]
        elif attribute == "command-on":
            events = [{
                "name": "command-on",
                "value": None,
                "type": "command",
                "date": "2026-09-23T06:57:23.292+0100",
                "descriptionText": "Command called: on()",
                "isStateChange": False,
                "deviceId": 4222,
                "source": "DEVICE",
                "producedBy": _producer_href(
                    "3700",
                    "Ikea Rodret (Livingroom): button 2 pushed",
                ),
            }]
        elif attribute == "command-off":
            events = [{
                "name": "command-off",
                "value": None,
                "type": "command",
                "date": "2026-09-23T08:27:23.518+0100",
                "descriptionText": "Command called: off()",
                "isStateChange": False,
                "deviceId": 4222,
                "source": "DEVICE",
                "producedBy": _producer_href(
                    "3995",
                    "01. Humidity Controller",
                ),
            }]
        else:
            raise AssertionError(("unexpected event attribute", attribute))

        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("provider must not be called for direct command provenance")

    async def aclose(self) -> None:
        return None


def test_command_producer_sufficiency_is_transition_aware() -> None:
    rows = correlate_command_producers([_history_receipt()])

    assert command_producer_transition_sufficient(rows, "on") is True
    assert command_producer_transition_sufficient(rows, "off") is True
    assert command_producer_transition_sufficient(rows, "toggle") is False

    off_only = [
        row
        for row in rows
        if row.get("boundaryRole") == "end"
    ]
    assert command_producer_transition_sufficient(off_only, "off") is True
    assert command_producer_transition_sufficient(off_only, "on") is False


def test_command_producer_renderer_focuses_on_requested_off_transition() -> None:
    message = render_command_producer_answer(
        [_history_receipt()],
        transition="off",
    )

    assert message is not None
    paragraphs = message.split("\n\n")
    assert paragraphs[0] == (
        "Hubitat records the OFF command for Dehumidifier 2 as produced by "
        "01. Humidity Controller."
    )
    assert "OFF command was issued at 8:27:23 AM" in paragraphs[1]
    assert "83 ms later" in paragraphs[1]
    assert "observed run of 1 hour 30 minutes" in message
    assert "matching ON command was produced by Ikea Rodret" in message
    assert "does not identify the person" in message


@pytest.mark.asyncio
async def test_agent_finalizes_off_producer_without_logs_or_provider() -> None:
    mcp = _OffCommandProducerMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did dehumidifier 2 turn off?"
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_subject_prefetch"] == 1
    assert counters["causal_command_producer_reads"] == 1
    assert counters["tool_calls"] == 3
    assert counters["causal_command_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters["investigative_finalization"] == 1
    assert counters.get("causal_native_log_reads", 0) == 0

    assert outcome.message.startswith(
        "Hubitat records the OFF command for Dehumidifier 2 as produced by "
        "01. Humidity Controller."
    )
    assert "83 ms later" in outcome.message
    assert "observed run of 1 hour 30 minutes" in outcome.message
    assert "began when the device reported ON at 6:57:23 AM" in outcome.message
    assert "Ikea Rodret (Livingroom): button 2 pushed" not in outcome.message

    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )
