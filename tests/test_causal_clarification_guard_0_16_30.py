from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_agent_orchestrator import (  # noqa: E402
    AgentOutcome,
    UnifiedMCPAgent as BaseUnifiedMCPAgent,
)
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from synthesis_validator import validate_synthesis  # noqa: E402


LIGHT = {
    "id": "7829",
    "label": "Hallway Light 1",
    "name": "Hallway Light 1",
    "room": "Hallway",
    "capabilities": ["Switch", "Light"],
    "attributes": {"switch": "on"},
    "commands": ["on", "off"],
}


def _hallway_events() -> list[dict]:
    triggered = [
        {
            "name": "Hallway (💡 1/2 On)",
            "appId": 4012,
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
            "value": "on",
            "description": "Hallway Light 1 switch is on",
            "date": "2026-09-24T17:45:42.743+0100",
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {
                "name": "Matter Hue Bridge Pro",
                "deviceId": 7790,
            },
        },
        {
            "name": "switch",
            "value": "off",
            "description": "Hallway Light 1 switch is off",
            "date": "2026-09-24T17:44:51.444+0100",
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {
                "name": "Matter Hue Bridge Pro",
                "deviceId": 7790,
            },
        },
        {
            "name": "switch",
            "value": "on",
            "description": "Hallway Light 1 switch is on",
            "date": "2026-09-24T17:43:34.945+0100",
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {
                "name": "Matter Hue Bridge Pro",
                "deviceId": 7790,
            },
        },
    ]


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError(
            "clarified causal switch request must resume deterministic path"
        )

    async def aclose(self) -> None:
        return None


class _HallwayMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices and device events.",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read hub logs.",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_device_identities(self):
        return [dict(LIGHT)]

    def peek_device_identities(self):
        return [dict(LIGHT)]

    def peek_cached_devices(self):
        return [dict(LIGHT)]

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        operation = arguments.get("tool")
        args = arguments.get("args") or {}

        if operation == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"devices": [dict(LIGHT)]},
            )

        assert operation == "hub_list_device_events", arguments
        assert str(args.get("deviceId") or "") == "7829"
        attribute = args.get("attribute")
        if attribute == "switch":
            events = _hallway_events()
        elif attribute == "command-on":
            events = []
        elif attribute is None:
            events = _hallway_events()
        else:
            raise AssertionError(("unexpected event attribute", attribute))

        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


@pytest.mark.asyncio
async def test_causal_choices_store_original_objective(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_base(
        _self: object,
        prompt: str,
        *_args: object,
        **_kwargs: object,
    ) -> AgentOutcome:
        assert prompt == "Why did hallway lights turn on?"
        return AgentOutcome(
            message=(
                "I could not resolve hallway lights uniquely. Possible matches: "
                "Hallway Light 1 or Hallway Light 2."
            ),
            request_class="live-read",
            evidence=[],
            choices=["Hallway Light 1", "Hallway Light 2"],
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent,
        "process_user_request_result",
        fake_base,
    )
    agent = UnifiedMCPAgent(
        _HallwayMCP(),
        "key",
        ai_client=_NoProvider(),
    )

    outcome = await agent.process_user_request_result(
        "Why did hallway lights turn on?",
        session_id="hallway-causal-choice",
    )

    assert outcome.choices == ["Hallway Light 1", "Hallway Light 2"]
    assert agent._clarification_objectives["hallway-causal-choice"] == (
        "Why did hallway lights turn on?"
    )


@pytest.mark.asyncio
async def test_selected_causal_choice_resumes_zero_model_boundary_path() -> None:
    mcp = _HallwayMCP()
    ai = _NoProvider()
    agent = UnifiedMCPAgent(
        mcp,
        "key",
        "model",
        ai_client=ai,
        require_sensitive_confirmation=False,
    )
    session = "hallway-causal-resume"
    agent._clarification_choices[session] = [
        "Hallway Light 1",
        "Hallway Light 2",
    ]
    agent._clarification_objectives[session] = (
        "Why did hallway lights turn on?"
    )

    outcome = await agent.process_user_request_result(
        "Hallway Light 1",
        session_id=session,
    )

    counters = outcome.metrics["counters"]
    assert ai.requests == []
    assert counters.get("model_rounds", 0) == 0
    assert counters["causal_clarification_resume"] == 1
    assert counters["causal_subject_prefetch"] == 1
    assert counters["causal_command_producer_reads"] == 1
    assert counters["causal_boundary_producer_provenance"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters.get("causal_native_log_reads", 0) == 0

    assert "Matter Hue Bridge Pro" in outcome.message
    assert "reporting path into Hubitat" in outcome.message
    assert "Hallway (💡 1/2 On)" in outcome.message
    assert "reaction to the state change" in outcome.message
    assert "triggered by the Hallway (💡 1/2 On)" not in outcome.message
    assert session not in agent._clarification_choices
    assert session not in agent._clarification_objectives

    assert not any(
        name == "hub_read_diagnostics"
        for name, _arguments in mcp.calls
    )


def _triggered_only_evidence(*, direct_app_command: bool = False) -> list[dict]:
    command_events: list[dict] = []
    if direct_app_command:
        command_events.append({
            "name": "command-on",
            "date": "2026-09-24T17:45:42.700+0100",
            "type": "command",
            "producedBy": {
                "label": "Hallway (💡 1/2 On)",
                "id": "4012",
                "type": "app",
            },
        })

    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Hallway Light 1",
            "attribute": "switch",
            "temporalAnalysis": {
                "observedIntervals": [{
                    "start": "2026-09-24T17:43:34.945+0100",
                    "end": "2026-09-24T17:44:51.444+0100",
                    "durationSeconds": 76,
                }],
                "unboundedActiveInterval": True,
                "openActiveInterval": True,
                "openActiveStart": "2026-09-24T17:45:42.743+0100",
            },
            "boundaryEvents": [{
                "name": "switch",
                "value": "on",
                "date": "2026-09-24T17:45:42.743+0100",
                "type": "physical",
                "triggered": [{
                    "name": "Hallway (💡 1/2 On)",
                    "appId": 4012,
                    "handler": "lightSwitchHandler",
                }],
                "producedBy": {
                    "label": "Matter Hue Bridge Pro",
                    "id": "7790",
                    "type": "device",
                },
            }],
            "observedEvents": [{
                "name": "switch",
                "value": "on",
                "date": "2026-09-24T17:45:42.743+0100",
                "type": "physical",
                "triggered": [{
                    "name": "Hallway (💡 1/2 On)",
                    "appId": 4012,
                    "handler": "lightSwitchHandler",
                }],
                "producedBy": {
                    "label": "Matter Hue Bridge Pro",
                    "id": "7790",
                    "type": "device",
                },
            }],
            "commandEvents": command_events,
        },
    }]


def test_validator_blocks_triggered_listener_from_becoming_direct_cause() -> None:
    bad = (
        "The most recent turn-on was directly triggered by an automation. "
        "Event metadata provides direct provenance, confirming this was triggered "
        "by the Hallway (💡 1/2 On) app."
    )

    corrected, issues = validate_synthesis(
        bad,
        _triggered_only_evidence(),
        causal=True,
    )

    assert "triggered_listener_causal_attribution" in issues
    assert "downstream listener in triggered[]" in corrected
    assert "Matter Hue Bridge Pro" in corrected
    assert "does not establish that Hallway (💡 1/2 On) initiated" in corrected
    assert "directly triggered by an automation" not in corrected


def test_validator_does_not_block_app_with_independent_direct_provenance() -> None:
    message = (
        "Hubitat records the Hallway (💡 1/2 On) app as the direct command "
        "source for the ON transition."
    )

    corrected, issues = validate_synthesis(
        message,
        _triggered_only_evidence(direct_app_command=True),
        causal=True,
    )

    assert corrected == message
    assert "triggered_listener_causal_attribution" not in issues
