from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
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


class _MCP441CommandProducerMCP:
    """Exact structured provenance shape introduced by MCP Rule Server 4.4.1."""

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
                    "date": "2026-09-23T08:27:23.601+0100",
                    "description": "switch attribute updated",
                    "isStateChange": True,
                    "type": "digital",
                    "triggered": [
                        {
                            "name": "Maker API",
                            "appId": 62,
                            "handler": "eventHandler",
                        }
                    ],
                },
                {
                    "name": "switch",
                    "value": "on",
                    "date": "2026-09-23T06:57:23.391+0100",
                    "description": "switch attribute updated",
                    "isStateChange": True,
                    "type": "digital",
                },
                {
                    "name": "switch",
                    "value": "off",
                    "date": "2026-09-22T22:38:13.489+0100",
                    "description": "switch attribute updated",
                    "isStateChange": True,
                    "type": "digital",
                },
            ]
        elif attribute == "command-on":
            events = [{
                "name": "command-on",
                "value": None,
                "type": "command",
                "date": "2026-09-23T06:57:23.292+0100",
                "description": "Command called: on()",
                "isStateChange": False,
                "producedBy": {
                    "name": "Ikea Rodret (Livingroom): button 2 pushed",
                    "appId": 3700,
                },
            }]
        elif attribute == "command-off":
            events = [{
                "name": "command-off",
                "value": None,
                "type": "command",
                "date": "2026-09-23T08:27:23.518+0100",
                "description": "Command called: off()",
                "isStateChange": False,
                "producedBy": {
                    "name": "01. Humidity Controller",
                    "appId": 3995,
                },
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


def test_mcp_441_structured_producer_infers_app_and_device_types() -> None:
    assert DeviceHistoryService._producer({
        "name": "01. Humidity Controller",
        "appId": 3995,
    }) == {
        "label": "01. Humidity Controller",
        "id": "3995",
        "type": "app",
    }

    assert DeviceHistoryService._producer({
        "name": "Dehumidifier 2",
        "deviceId": "4222",
    }) == {
        "label": "Dehumidifier 2",
        "id": "4222",
        "type": "device",
    }


def test_mcp_441_triggered_list_survives_event_normalization() -> None:
    triggered = [
        {"name": "Button Rule", "appId": 173, "handler": "allHandlerX"},
        {"name": "Maker API", "appId": 62, "handler": "eventHandler"},
    ]
    events = DeviceHistoryService._events(
        {
            "events": [{
                "name": "pushed",
                "value": "2",
                "date": "2026-09-23T06:57:23.100+0100",
                "type": "physical",
                "isStateChange": True,
                "producedBy": {"name": "Ikea Rodret", "deviceId": "7129"},
                "triggered": triggered,
            }]
        },
        limit=10,
    )

    assert events == [{
        "name": "pushed",
        "value": "2",
        "unit": None,
        "description": None,
        "date": "2026-09-23T06:57:23.100+0100",
        "isStateChange": True,
        "type": "physical",
        "triggered": triggered,
        "producedBy": {
            "label": "Ikea Rodret",
            "id": "7129",
            "type": "device",
        },
    }]


@pytest.mark.asyncio
async def test_mcp_441_structured_command_provenance_finalizes_without_logs_or_model() -> None:
    mcp = _MCP441CommandProducerMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did dehumidifier 2 turn on?"
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_subject_prefetch"] == 1
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_command_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters.get("causal_native_log_reads", 0) == 0

    assert "Ikea Rodret (Livingroom): button 2 pushed" in outcome.message
    assert "99 ms later" in outcome.message
    assert "The observed run ended when the device reported OFF at 8:27:23 AM" in outcome.message
    assert "after 1 hour 30 minutes" in outcome.message
    assert "01. Humidity Controller" not in outcome.message

    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )

    receipts = [
        receipt
        for receipt in outcome.evidence
        if receipt.get("tool") == "homebrain_device_history"
    ]
    assert len(receipts) == 1
    details = receipts[0]["details"]

    by_name = {
        row["name"]: row
        for row in details["commandEvents"]
    }
    assert set(by_name) == {"command-on"}
    assert by_name["command-on"]["producedBy"] == {
        "label": "Ikea Rodret (Livingroom): button 2 pushed",
        "id": "3700",
        "type": "app",
    }

