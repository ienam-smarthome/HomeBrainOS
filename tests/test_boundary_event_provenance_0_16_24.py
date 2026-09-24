from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_command_provenance import (  # noqa: E402
    boundary_producer_transition_sufficient,
    correlate_boundary_producers,
    correlate_command_producers,
)
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _device(device_id: str, label: str, room: str) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": ["Switch"],
        "attributes": {"switch": "off"},
        "commands": ["on", "off"],
    }


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("direct boundary provenance must not call provider")

    async def aclose(self) -> None:
        return None


class _BoundaryMCP:
    def __init__(
        self,
        *,
        device: dict,
        transition: str,
        switch_events: list[dict],
        command_events: list[dict],
    ) -> None:
        self.device = dict(device)
        self.transition = transition
        self.switch_events = list(switch_events)
        self.command_events = list(command_events)
        self.calls: list[tuple[str, dict]] = []

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
        return [dict(self.device)]

    def peek_device_identities(self):
        return [dict(self.device)]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        if arguments.get("tool") == "hub_list_devices":
            data = {"devices": [dict(self.device)]}
            return MCPToolResult(name, arguments, {}, "ok", data)

        assert arguments.get("tool") == "hub_list_device_events", arguments
        args = arguments.get("args") or {}
        assert str(args.get("deviceId")) == str(self.device["id"])
        attribute = args.get("attribute")
        if attribute == "switch":
            events = list(self.switch_events)
        elif attribute == f"command-{self.transition}":
            events = list(self.command_events)
        else:
            raise AssertionError(("unexpected event read", attribute))
        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


def _fan_switch_events() -> list[dict]:
    return [
        {
            "name": "switch",
            "value": "off",
            "date": "2026-09-24T00:23:37.836+0100",
            "isStateChange": True,
            "type": "digital",
            "producedBy": {"name": "01. Humidity Controller", "appId": 3995},
        },
        {
            "name": "switch",
            "value": "on",
            "date": "2026-09-23T21:59:59.735+0100",
            "isStateChange": True,
            "type": "digital",
            "producedBy": {"name": "01. Humidity Controller", "appId": 3995},
        },
        {
            "name": "switch",
            "value": "off",
            "date": "2026-09-23T21:52:37.258+0100",
            "isStateChange": True,
            "type": "digital",
            "producedBy": {"name": "01. Humidity Controller", "appId": 3995},
        },
    ]


def _fan_command_events() -> list[dict]:
    return [{
        "name": "command-on",
        "value": None,
        "date": "2026-09-23T21:59:59.748+0100",
        "description": "Command called: on()",
        "isStateChange": False,
        "type": "command",
        "producedBy": {"name": "01. Humidity Controller", "appId": 3995},
    }]


@pytest.mark.asyncio
async def test_corroborated_13ms_inversion_finalizes_fan_without_logs_or_model() -> None:
    device = _device("7086", "Fan Switch (Tuya Local)", "Ventilation")
    mcp = _BoundaryMCP(
        device=device,
        transition="on",
        switch_events=_fan_switch_events(),
        command_events=_fan_command_events(),
    )
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did Fan Switch (Tuya Local) start running?"
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_command_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters["tool_calls"] == 3
    assert counters.get("causal_native_log_reads", 0) == 0

    assert "01. Humidity Controller" in outcome.message
    assert "13 ms later" in outcome.message
    assert "recording-order inversion" in outcome.message
    assert "2 hours 24 minutes" in outcome.message

    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )


def _hue_switch_events() -> list[dict]:
    triggered = [
        {
            "name": "Bedroom 1 (⚪ Lights Off)",
            "appId": 4015,
            "handler": "lightSwitchHandler",
        },
        {
            "name": "SenseCap D1 Settings",
            "appId": 4129,
            "handler": "liveDeviceEventHandler",
        },
    ]
    return [
        {
            "name": "switch",
            "value": "off",
            "descriptionText": "Bedroom 1 Light switch is off",
            "date": "2026-09-23T22:22:45.632+0100",
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        },
        {
            "name": "switch",
            "value": "on",
            "descriptionText": "Bedroom 1 Light switch is on",
            "date": "2026-09-23T22:11:04.111+0100",
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        },
        {
            "name": "switch",
            "value": "off",
            "descriptionText": "Bedroom 1 Light switch is off",
            "date": "2026-09-23T21:49:32.655+0100",
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        },
    ]


@pytest.mark.asyncio
async def test_bridge_boundary_provenance_finalizes_as_reporting_source() -> None:
    device = _device("7840", "Bedroom 1 Light", "Bedroom 1")
    mcp = _BoundaryMCP(
        device=device,
        transition="on",
        switch_events=_hue_switch_events(),
        command_events=[],
    )
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did Bedroom 1 Light turn itself on?"
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_boundary_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters["causal_reporting_source_correlation"] == 1
    assert counters["causal_room_plan"] == 1
    assert 3 <= counters["tool_calls"] <= 8
    assert counters.get("causal_native_log_reads", 0) == 0
    assert counters.get("causal_command_producer_provenance", 0) == 0

    assert (
        "did not record a command-on producer aligned with this ON transition"
        in outcome.message
    )
    assert "Matter Hue Bridge Pro" in outcome.message
    assert "reporting path into Hubitat" in outcome.message
    assert "not the exact initiating action" in outcome.message
    assert "Bedroom 1 (⚪ Lights Off)" in outcome.message
    assert "SenseCap D1 Settings" in outcome.message
    assert "reaction to the state change" in outcome.message
    assert "rather than by a Hubitat automation" not in outcome.message
    assert "12 minutes" in outcome.message

    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )


def test_later_command_without_same_app_boundary_is_still_rejected() -> None:
    evidence = [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Fan Switch (Tuya Local)",
            "temporalAnalysis": {
                "observedIntervals": [{
                    "start": "2026-09-23T21:59:59.735+0100",
                    "end": "2026-09-24T00:23:37.836+0100",
                    "durationSeconds": 8618,
                }],
            },
            "boundaryEvents": [{
                "name": "switch",
                "value": "on",
                "date": "2026-09-23T21:59:59.735+0100",
                "type": "digital",
                "producedBy": {
                    "label": "Different Controller",
                    "id": "4000",
                    "type": "app",
                },
            }],
            "commandEvents": [{
                "name": "command-on",
                "date": "2026-09-23T21:59:59.748+0100",
                "type": "command",
                "producedBy": {
                    "label": "01. Humidity Controller",
                    "id": "3995",
                    "type": "app",
                },
            }],
        },
    }]

    assert correlate_command_producers(evidence) == []


def test_self_produced_boundary_does_not_stop_deeper_fallback() -> None:
    evidence = [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Bedroom2 (MQTT)",
            "temporalAnalysis": {
                "observedIntervals": [{
                    "start": "2026-09-20T20:48:30.176+0100",
                    "end": "2026-09-21T18:01:50.996+0100",
                }],
            },
            "boundaryEvents": [{
                "name": "switch",
                "value": "off",
                "date": "2026-09-21T18:01:50.996+0100",
                "type": "digital",
                "producedBy": {
                    "label": "Bedroom2 (MQTT)",
                    "id": "7102",
                    "type": "device",
                },
            }],
            "commandEvents": [],
        },
    }]

    rows = correlate_boundary_producers(evidence)
    assert rows
    assert boundary_producer_transition_sufficient(rows, "off") is False


def _short_hue_switch_events() -> list[dict]:
    return [
        {
            "name": "switch",
            "value": "off",
            "descriptionText": "Bedroom 1 Light switch is off",
            "date": "2026-09-24T14:58:59.777+0100",
            "isStateChange": True,
            "type": "physical",
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        },
        {
            "name": "switch",
            "value": "on",
            "descriptionText": "Bedroom 1 Light switch is on",
            "date": "2026-09-24T14:58:47.954+0100",
            "isStateChange": True,
            "type": "physical",
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        },
        {
            "name": "switch",
            "value": "off",
            "descriptionText": "Bedroom 1 Light switch is off",
            "date": "2026-09-24T14:58:37.134+0100",
            "isStateChange": True,
            "type": "physical",
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        },
    ]


@pytest.mark.asyncio
async def test_short_bridge_interval_keeps_authoritative_boundary_provenance() -> None:
    device = _device("7840", "Bedroom 1 Light", "Bedroom 1")
    mcp = _BoundaryMCP(
        device=device,
        transition="on",
        switch_events=_short_hue_switch_events(),
        command_events=[],
    )
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )

    outcome = await agent.process_user_request_result(
        "Why did Bedroom 1 Light turn itself on?"
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_subject_prefetch"] == 1
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_boundary_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters.get("causal_native_log_reads", 0) == 0

    assert "Matter Hue Bridge Pro" in outcome.message
    assert "reporting path into Hubitat" in outcome.message
    assert "12 seconds" in outcome.message
    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )
