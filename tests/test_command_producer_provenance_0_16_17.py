from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_command_provenance import (  # noqa: E402
    command_producer_turn_on_sufficient,
    correlate_command_producers,
    render_command_producer_answer,
)
from device_history_service import DeviceHistoryService  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from technical_metrics_presenter import present_request_metrics  # noqa: E402


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


class _CommandProducerMCP:
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


def test_produced_by_html_is_sanitized_and_structured() -> None:
    producer = DeviceHistoryService._producer(
        _producer_href(
            "3700",
            "Ikea Rodret (Livingroom): button 2 pushed",
        )
    )

    assert producer == {
        "label": "Ikea Rodret (Livingroom): button 2 pushed",
        "id": "3700",
        "type": "app",
    }


@pytest.mark.asyncio
async def test_history_collects_scoped_command_producer_rows() -> None:
    mcp = _CommandProducerMCP()
    evidence: list[tuple[tuple, dict]] = []

    def record(*args, **kwargs):
        evidence.append((args, kwargs))

    service = DeviceHistoryService(mcp, record)
    result = await service.history({
        "name": "Dehumidifier 2",
        "attribute": "switch",
        "limit": 12,
        "_resolved_target": _device(),
        "_include_command_provenance": True,
    })

    assert result.is_error is False
    assert result.data["causationAvailable"] is True
    command_events = result.data["commandEvents"]
    assert {row["name"] for row in command_events} == {
        "command-on",
        "command-off",
    }

    by_name = {row["name"]: row for row in command_events}
    assert by_name["command-on"]["producedBy"] == {
        "label": "Ikea Rodret (Livingroom): button 2 pushed",
        "id": "3700",
        "type": "app",
    }
    assert by_name["command-off"]["producedBy"] == {
        "label": "01. Humidity Controller",
        "id": "3995",
        "type": "app",
    }

    attributes = [
        arguments["args"].get("attribute")
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
    ]
    assert attributes == ["switch", "command-on", "command-off"]


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
                    "producedBy": {
                        "label": "Ikea Rodret (Livingroom): button 2 pushed",
                        "id": "3700",
                        "type": "app",
                    },
                },
            ],
        },
    }


def test_command_producer_correlation_is_direct_and_boundary_aligned() -> None:
    rows = correlate_command_producers([_history_receipt()])

    assert len(rows) == 2
    by_role = {row["boundaryRole"]: row for row in rows}

    start = by_role["start"]
    assert start["producer"]["id"] == "3700"
    assert start["producer"]["label"] == (
        "Ikea Rodret (Livingroom): button 2 pushed"
    )
    assert start["command"]["commandToStateMs"] == 99.0

    end = by_role["end"]
    assert end["producer"]["id"] == "3995"
    assert end["producer"]["label"] == "01. Humidity Controller"
    assert end["command"]["commandToStateMs"] == 83.0

    assert command_producer_turn_on_sufficient(rows) is True


def test_command_after_state_boundary_is_not_accepted_as_provenance() -> None:
    receipt = _history_receipt()
    receipt["details"]["commandEvents"] = [
        {
            "name": "command-on",
            "description": "Command called: on()",
            "date": "2026-09-23T06:57:23.900+0100",
            "type": "command",
            "producedBy": {
                "label": "Late producer",
                "id": "9999",
                "type": "app",
            },
        }
    ]

    rows = correlate_command_producers([receipt])

    assert rows == []
    assert command_producer_turn_on_sufficient(rows) is False


def test_command_producer_renderer_distinguishes_on_and_off_sources() -> None:
    message = render_command_producer_answer([_history_receipt()])

    assert message is not None
    assert "ON command for Dehumidifier 2 as produced by" in message
    assert "Ikea Rodret (Livingroom): button 2 pushed" in message
    assert "99 ms later" in message
    assert "OFF command was produced by 01. Humidity Controller" in message
    assert "83 ms later" in message
    assert "1 hour 30 minutes" in message
    assert "does not identify the person" in message


@pytest.mark.asyncio
async def test_agent_finalizes_from_command_producer_without_logs_or_provider() -> None:
    mcp = _CommandProducerMCP()
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
    assert counters["tool_calls"] == 3
    assert counters["causal_command_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters["investigative_finalization"] == 1
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
    history_receipts = [
        receipt
        for receipt in outcome.evidence
        if receipt.get("tool") == "homebrain_device_history"
    ]
    assert len(history_receipts) == 1
    assert history_receipts[0]["arguments"] == {
        "name": "Dehumidifier 2",
        "attribute": "switch",
        "limit": 3,
    }
    assert history_receipts[0]["details"]["commandEvents"][0]["producedBy"]


def test_command_producer_metrics_are_supported_and_presented() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("causal_command_producer_reads", 2)
        metrics.increment("causal_command_producer_provenance")
        snapshot = metrics.finish("success")
    finally:
        metrics.reset(token)

    rows = present_request_metrics(snapshot)
    assert {"label": "Command-producer reads", "value": "2"} in rows
    assert {"label": "Command-producer provenance", "value": "1"} in rows
