"""Causal benchmark: on()/off() is not the only light-switching command.

These fixtures are synthetic, based on common command/state shapes; they are
not proof that the user's Hallway app executed any specific historical command.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_command_semantics import (
    classify_state_command,
    command_actions_for_history,
    dimmer_command_supported,
)
from causal_command_provenance import (
    command_producer_transition_sufficient,
    correlate_command_producers,
    render_command_producer_answer,
    render_command_producer_summary,
    render_competing_command_summary,
)
from device_history_service import DeviceHistoryService
from homebrain_agent import UnifiedMCPAgent
from mcp_client import MCPTool, MCPToolResult


ON = "2026-10-12T01:04:10.000+01:00"
OFF = "2026-10-12T01:04:48.000+01:00"


def _dimmer() -> dict:
    return {
        "id": "7700", "name": "Hallway Light 1", "label": "Hallway Light 1",
        "room": "Hallway",
        "capabilities": ["Switch", "SwitchLevel"],
        "attributes": {"switch": "off", "level": 20},
        "commands": ["on", "off", "setLevel"],
    }


def _plain_switch() -> dict:
    return {
        "id": "7711", "label": "Appliance Switch",
        "capabilities": ["Switch"], "attributes": {"switch": "on"},
        "commands": ["on", "off"],
    }


def _producer(id_: str = "4012", label: str = "Hallway Light Mode Controller"):
    return {"type": "app", "id": id_, "label": label}


def _command(
    timestamp: str,
    *,
    method: str = "setLevel",
    description: str = "Command called: setLevel(20)",
    producer: dict | None = None,
    value=None,
) -> dict:
    return {
        "name": f"command-{method}", "date": timestamp, "type": "command",
        "value": value, "description": description,
        "producedBy": producer or _producer(),
    }


def _state(value: str, when: str) -> dict:
    return {
        "name": "switch", "value": value, "date": when,
        "type": "physical", "isStateChange": True,
        "producedBy": {
            "type": "device", "id": "7790", "label": "Matter Hue Bridge Pro",
        },
        "triggered": [{
            "appId": 4012, "name": "Hallway Lights Controller",
            "handler": "lightSwitchHandler",
        }],
    }


def _receipt(commands: list[dict], *, older: bool = False) -> list[dict]:
    history = [{
        "start": ON, "end": OFF, "durationSeconds": 38,
    }]
    if older:
        history.append({
            "start": "2026-10-12T00:50:00+01:00",
            "end": "2026-10-12T00:50:20+01:00",
        })
    return [{
        "tool": "homebrain_device_history", "success": True,
        "arguments": {"name": "Hallway Light 1", "attribute": "switch"},
        "details": {
            "label": "Hallway Light 1",
            "temporalAnalysis": {"observedIntervals": history},
            "commandEvents": commands,
            "boundaryEvents": [_state("on", ON), _state("off", OFF)],
        },
    }]


def test_semantics_registry_rejects_unsupported_and_unknown_effects():
    assert dimmer_command_supported(_dimmer())
    assert not dimmer_command_supported(_plain_switch())
    assert command_actions_for_history(_plain_switch(), ("on",)) == ("on",)
    assert command_actions_for_history(_dimmer(), ("on",)) == ("on", "setLevel")
    assert command_actions_for_history(_dimmer(), ("off",)) == ("off", "setLevel")

    on_level = classify_state_command(_command(ON), "on")
    assert on_level["compatible"] is True
    assert on_level["display"] == "setLevel(20)"
    assert on_level["level"] == 20
    assert classify_state_command(_command(ON), "off")["compatible"] is False
    assert classify_state_command(
        _command(ON, description="Command called: setLevel(0)"), "off"
    )["compatible"] is True
    assert classify_state_command(
        _command(ON, description="Command called: setLevel(0)"), "on"
    )["compatible"] is False
    assert classify_state_command(
        _command(ON, description="setLevel(no argument)"), "on"
    )["compatible"] is False
    assert classify_state_command(
        _command(ON, description="Command called: setLevel(500)"), "on"
    )["compatible"] is False
    assert classify_state_command(
        _command(ON, method="setColor", description="setColor({})"), "on"
    )["provenEffect"] is False
    assert classify_state_command(
        _command(ON, method="on", description="Command called: on()"), "on"
    )["compatible"] is True


def test_authoritative_setlevel_before_on_is_direct_command_level_evidence():
    commands = [_command("2026-10-12T01:04:09.452+01:00")]
    evidence = _receipt(commands)
    correlations = correlate_command_producers(evidence)
    assert len(correlations) == 1
    row = correlations[0]
    assert row["action"] == "on"
    assert row["producer"]["id"] == "4012"
    assert row["command"]["name"] == "command-setLevel"
    assert row["command"]["semantics"] == "level-switch-command"
    assert row["command"]["commandToStateMs"] == 548.0
    assert command_producer_transition_sufficient(
        correlations, "on", requested_boundary=ON
    )
    message = render_command_producer_summary(evidence, transition="on")
    assert message.startswith("**Command evidence:**")
    assert "Hallway Light Mode Controller issued setLevel(20)" in message
    assert "548 ms later" in message
    assert "without a separate on() command" in message
    assert "not identify the person" in message
    assert "setLevel(20)" in render_command_producer_answer(evidence)


def test_later_brightness_command_must_not_be_misreported_as_on_cause():
    evidence = _receipt([
        _command("2026-10-12T01:04:10.475+01:00"),
    ])
    assert correlate_command_producers(evidence) == []
    assert render_command_producer_summary(evidence, transition="on") is None
    assert not command_producer_transition_sufficient(
        [], "on", requested_boundary=ON
    )


def test_other_events_with_commands_do_not_hijack_requested_latest_on():
    evidence = _receipt([
        _command("2026-10-12T00:50:00.100+01:00"),
    ], older=True)
    # The old event is not a command producer for the focal 01:04 boundary.
    assert render_command_producer_summary(evidence, transition="on") is None


def test_two_producing_apps_are_preserved_as_competing_command_paths():
    evidence = _receipt([
        _command("2026-10-12T01:04:09.452+01:00"),
        _command(
            "2026-10-12T01:04:09.700+01:00", method="on",
            description="Command called: on()",
            producer=_producer("8888", "Second Controller"),
        ),
    ])
    rows = correlate_command_producers(evidence)
    assert len(rows) == 1
    assert len(rows[0]["competingCommands"]) == 2
    assert rows[0]["provenanceStrength"] == "ambiguous-multiple-command-producers"
    assert not command_producer_transition_sufficient(
        rows, "on", requested_boundary=ON
    )
    assert render_command_producer_summary(evidence, transition="on") is None
    msg = render_competing_command_summary(evidence, transition="on")
    assert "No single initiating app is uniquely established" in msg
    assert "Hallway Light Mode Controller (setLevel(20)" in msg
    assert "Second Controller (on()" in msg


def test_one_app_on_followed_by_setlevel_is_not_a_competing_controller():
    evidence = _receipt([
        _command("2026-10-12T01:04:09.452+01:00"),
        _command("2026-10-12T01:04:09.700+01:00", method="on",
                 description="Command called: on()"),
    ])
    rows = correlate_command_producers(evidence)
    assert len(rows) == 1
    assert rows[0]["competingCommands"] == []
    assert command_producer_transition_sufficient(rows, "on")


def test_off_boundary_only_accepts_zero_level_or_explicit_off():
    evidence = _receipt([
        _command("2026-10-12T01:04:47.700+01:00",
                 description="Command called: setLevel(0)"),
    ])
    rows = correlate_command_producers(evidence)
    assert len(rows) == 1
    assert rows[0]["boundaryRole"] == "end"
    assert rows[0]["command"]["level"] == 0
    assert command_producer_transition_sufficient(rows, "off")
    assert not command_producer_transition_sufficient(rows, "on")


class _DimmerMCP:
    """Real end-to-end gateway mock; distinguishes switch and command streams."""

    def __init__(self, *, extra_app=False, later_level=False):
        self.calls = []
        self.extra_app = extra_app
        self.later_level = later_level

    async def list_tools(self):
        return [MCPTool(
            "hub_read_devices", "Read Hubitat devices and scoped event histories",
            {"type": "object", "properties": {}},
        )]

    async def get_device_identities(self):
        return [_dimmer()]

    def peek_device_identities(self):
        return [_dimmer()]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name == "hub_read_devices"
        assert arguments["tool"] == "hub_list_device_events"
        args = arguments["args"]
        assert args["deviceId"] == "7700"
        attribute = args.get("attribute")
        if attribute == "switch":
            events = [_state("off", OFF), _state("on", ON), _state(
                "off", "2026-10-12T01:03:50.000+01:00"
            )]
        elif attribute == "command-on":
            events = [
                _command(
                    "2026-10-12T01:04:09.700+01:00",
                    method="on", description="Command called: on()",
                    producer=_producer("8888", "Second Controller"),
                )
            ] if self.extra_app else []
        elif attribute == "command-setLevel":
            events = [_command(
                "2026-10-12T01:04:10.450+01:00"
                if self.later_level
                else "2026-10-12T01:04:09.452+01:00",
            )]
        else:
            raise AssertionError("Unexpected MCP scoped history " + str(attribute))
        return MCPToolResult(
            name, arguments, {}, "ok",
            {"events": events, "count": len(events)},
        )


class _NoProvider:
    async def post(self, *_args, **_kwargs):
        raise AssertionError("Reasoning model must not be used for direct cause")

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_dimmer_gateway_read_scope_includes_setlevel_without_generic_page():
    mcp = _DimmerMCP()
    receipts = []
    history = DeviceHistoryService(mcp, lambda *a, **kw: receipts.append((a, kw)))
    result = await history.history({
        "name": "Hallway Light 1",
        "attribute": "switch",
        "_resolved_target": _dimmer(),
        "_include_command_provenance": True,
        "_causal_transition": "on",
        "limit": 3,
    })
    assert not result.is_error
    assert {a["args"].get("attribute") for _, a in mcp.calls} == {
        "switch", "command-on", "command-setLevel"
    }
    assert len(mcp.calls) == 3
    assert {r["name"] for r in result.data.get("commandEvents", [])} == {
        "command-setLevel"
    }
    assert result.data["causationAvailable"] is True
    assert any(
        kw.get("evidence_kind") == "authoritative_command_event_history"
        and kw.get("details", {}).get("eventName") == "command-setLevel"
        for _, kw in receipts
    )


@pytest.mark.asyncio
async def test_full_agent_finds_level_command_before_expanding_to_sensor_guesses():
    mcp = _DimmerMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai,
        require_sensitive_confirmation=False,
    )
    outcome = await agent.process_user_request_result(
        "Why did Hallway Light 1 turn on?"
    )
    assert outcome.model is None if hasattr(outcome, "model") else True
    assert "Hallway Light Mode Controller issued setLevel(20)" in outcome.message
    assert "548 ms later" in outcome.message
    assert "without a separate on() command" in outcome.message
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0
    assert outcome.metrics["counters"]["causal_command_producer_reads"] == 2
    assert len(mcp.calls) == 3


@pytest.mark.asyncio
async def test_full_agent_keeps_competing_controller_evidence_ambiguous():
    mcp = _DimmerMCP(extra_app=True)
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai,
        require_sensitive_confirmation=False,
    )
    result = await agent.process_user_request_result(
        "Why did Hallway Light 1 turn on?"
    )
    assert "Competing commands" in result.message
    assert "Second Controller" in result.message
    assert "Hallway Light Mode Controller" in result.message
    assert "No single initiating app is uniquely established" in result.message
    assert "Hubitat has no direct command producer" not in result.message


@pytest.mark.asyncio
async def test_full_agent_late_level_is_not_an_on_producer():
    mcp = _DimmerMCP(later_level=True)
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=ai,
        require_sensitive_confirmation=False,
    )
    result = await agent.process_user_request_result(
        "Why did Hallway Light 1 turn on?"
    )
    assert "Hallway Light Mode Controller issued setLevel(20)" not in result.message
    assert "Hubitat has no direct command producer" in result.message
