from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_planner import (  # noqa: E402
    build_reporting_source_secondary_analysis,
    render_reporting_source_secondary_analysis,
)
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


LIGHT = {
    "id": "7840",
    "label": "Bedroom 1 Light",
    "name": "Bedroom 1 Light",
    "room": "Bedroom 1",
    "capabilities": ["Switch", "Light"],
    "attributes": {"switch": "off"},
    "commands": ["on", "off"],
}
DIMMER = {
    "id": "7200",
    "label": "Bedroom 1 dimmer",
    "name": "Bedroom 1 dimmer",
    "room": "Bedroom 1",
    "capabilities": ["PushableButton", "HoldableButton"],
    "commands": [],
}
FP300 = {
    "id": "7300",
    "label": "Bedroom 1 FP300 sensor",
    "name": "Bedroom 1 FP300 sensor",
    "room": "Bedroom 1",
    "capabilities": ["MotionSensor"],
    "attributes": {"motion": "active"},
    "commands": [],
}


def _light_events() -> list[dict]:
    triggered = [
        {"name": "Bedroom 1 (⚪ Lights Off)", "appId": 4015, "handler": "lightSwitchHandler"},
        {"name": "SenseCap D1 Settings", "appId": 4129, "handler": "liveDeviceEventHandler"},
    ]
    rows = [
        ("off", "2026-09-23T22:22:45.632+0100"),
        ("on", "2026-09-23T22:11:04.111+0100"),
        ("off", "2026-09-23T21:49:32.655+0100"),
        ("on", "2026-09-23T21:18:26.800+0100"),
        ("off", "2026-09-23T21:00:01.000+0100"),
        ("on", "2026-09-23T20:58:17.600+0100"),
        ("off", "2026-09-23T20:47:06.372+0100"),
    ]
    return [
        {
            "name": "switch",
            "value": value,
            "description": f"Bedroom 1 Light switch is {value}",
            "date": date,
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        }
        for value, date in rows
    ]


def _dimmer_events() -> list[dict]:
    return [
        {
            "name": "pushed",
            "value": "1",
            "description": "button 1 pushed [physical]",
            "date": "2026-09-23T22:22:45.500+0100",
            "isStateChange": True,
            "type": "physical",
        },
        {
            "name": "pushed",
            "value": "1",
            "description": "button 1 pushed [physical]",
            "date": "2026-09-23T21:49:32.500+0100",
            "isStateChange": True,
            "type": "physical",
        },
        {
            "name": "pushed",
            "value": "1",
            "description": "button 1 pushed [physical]",
            "date": "2026-09-23T21:00:00.900+0100",
            "isStateChange": True,
            "type": "physical",
        },
    ]


def _fp300_events() -> list[dict]:
    return [
        {
            "name": "motion",
            "value": "active",
            "date": "2026-09-23T21:18:31.200+0100",
            "isStateChange": True,
        },
        {
            "name": "motion",
            "value": "active",
            "date": "2026-09-23T20:58:18.800+0100",
            "isStateChange": True,
        },
        {
            "name": "motion",
            "value": "inactive",
            "date": "2026-09-23T20:47:06.292+0100",
            "isStateChange": True,
        },
    ]


class _BedroomCorrelationMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool("hub_read_devices", "Read devices", {"type": "object", "properties": {}}),
            MCPTool("hub_read_diagnostics", "Read logs", {"type": "object", "properties": {}}),
        ]

    async def get_device_identities(self):
        return [dict(LIGHT), dict(DIMMER), dict(FP300)]

    def peek_device_identities(self):
        return [dict(LIGHT), dict(DIMMER), dict(FP300)]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        leaf = arguments.get("tool")
        args = arguments.get("args") or {}

        if leaf == "hub_list_devices":
            data = {"devices": [dict(LIGHT), dict(DIMMER), dict(FP300)]}
            return MCPToolResult(name, arguments, {}, "ok", data)

        assert leaf == "hub_list_device_events", arguments
        device_id = str(args.get("deviceId") or "")
        attribute = args.get("attribute")

        if device_id == "7840" and attribute == "switch":
            events = _light_events()
        elif device_id == "7840" and attribute == "command-on":
            events = []
        elif device_id == "7840" and attribute is None:
            events = _light_events()
        elif device_id == "7200":
            events = _dimmer_events()
        elif device_id == "7300":
            events = _fp300_events()
        else:
            raise AssertionError(("unexpected history call", device_id, attribute))

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
        raise AssertionError("bounded reporting-source correlation must not call provider")

    async def aclose(self) -> None:
        return None


def test_secondary_analysis_preserves_repeated_pattern_and_requested_miss() -> None:
    subject = {
        "label": "Bedroom 1 Light",
        "room": "Bedroom 1",
        "correlationEvents": _light_events(),
    }
    controller = {
        "label": "Bedroom 1 dimmer",
        "attribute": "pushed",
        "events": _dimmer_events(),
    }
    sensor = {
        "label": "Bedroom 1 FP300 sensor",
        "attribute": "motion",
        "events": _fp300_events(),
    }

    analysis = build_reporting_source_secondary_analysis(
        subject,
        transition="on",
        requested_boundary="2026-09-23T22:11:04.111+01:00",
        controller_history=controller,
        sensor_history=sensor,
    )

    assert analysis["transitionCount"] == 3
    assert analysis["controller"]["relevantAlignments"] == []
    assert len(analysis["controller"]["oppositeAlignments"]) == 3
    assert analysis["sensor"]["requestedMatched"] is False
    assert analysis["sensor"]["repeatedUpstreamPattern"] is True

    starts = analysis["sensor"]["relevantCorrelations"]
    assert [row["signedDeltaSeconds"] for row in starts] == [1.2, 4.4]
    assert len(analysis["sensor"]["oppositeCorrelations"]) == 1
    assert analysis["sensor"]["oppositeCorrelations"][0]["signedDeltaSeconds"] == -0.08

    rendered = render_reporting_source_secondary_analysis(analysis)
    assert rendered is not None
    assert "did not align with the ON boundaries" in rendered
    assert "did align with 3 OFF boundary event(s)" in rendered
    assert "2 of 3 observed ON transition(s)" in rendered
    assert "1.2s after" in rendered
    assert "4.4s after" in rendered
    assert "specific requested transition does not have such an edge" in rendered
    assert "consistent with an upstream or outside-Hubitat relationship" in rendered
    assert "does not prove that Bedroom 1 FP300 sensor triggered" in rendered
    assert "does not identify a specific external hub or automation" in rendered


def test_shared_sensor_reporting_path_is_not_independent_corroboration() -> None:
    subject = {
        "label": "Hallway Light 1",
        "room": "Hallway",
        "correlationEvents": [
            {"name": "switch", "value": "off", "date": "2026-09-24T20:28:40.810+01:00"},
            {"name": "switch", "value": "on", "date": "2026-09-24T20:28:20.371+01:00"},
            {"name": "switch", "value": "off", "date": "2026-09-24T20:25:07.768+01:00"},
            {"name": "switch", "value": "on", "date": "2026-09-24T20:24:24.025+01:00"},
        ],
    }
    producer = {"label": "Matter Aqara M3", "id": "7718", "type": "device"}
    fp300 = {
        "label": "Hallway FP300 sensor",
        "room": "Hallway",
        "attribute": "motion",
        "events": [
            {"name": "motion", "value": "active", "date": "2026-09-24T20:28:21.335+01:00", "producedBy": producer},
            {"name": "motion", "value": "inactive", "date": "2026-09-24T20:28:40.685+01:00", "producedBy": producer},
            {"name": "motion", "value": "active", "date": "2026-09-24T20:24:25.487+01:00", "producedBy": producer},
            {"name": "motion", "value": "inactive", "date": "2026-09-24T20:25:07.636+01:00", "producedBy": producer},
        ],
    }
    soft = {
        "label": "Hallway Soft Sensor",
        "room": "Hallway",
        "attribute": "motion",
        "events": [
            {"name": "motion", "value": "inactive", "date": "2026-09-24T20:28:15.306+01:00", "producedBy": producer},
            {"name": "motion", "value": "active", "date": "2026-09-24T20:28:21.315+01:00", "producedBy": producer},
            {"name": "motion", "value": "inactive", "date": "2026-09-24T20:28:41.694+01:00", "producedBy": producer},
            {"name": "motion", "value": "active", "date": "2026-09-24T20:24:24.482+01:00", "producedBy": producer},
            {"name": "motion", "value": "inactive", "date": "2026-09-24T20:25:08.368+01:00", "producedBy": producer},
        ],
    }

    analysis = build_reporting_source_secondary_analysis(
        subject,
        transition="on",
        requested_boundary="2026-09-24T20:28:20.371+01:00",
        sensor_histories=[fp300, soft],
    )

    soft_end = next(
        row
        for row in analysis["sensors"][1]["oppositeCorrelations"]
        if row["signedDeltaSeconds"] == 0.884
    )
    assert soft_end["producedBy"]["label"] == "Matter Aqara M3"
    assert analysis["sensors"][0]["producerLabels"] == ["Matter Aqara M3"]
    assert analysis["sensors"][1]["producerLabels"] == ["Matter Aqara M3"]

    rendered = render_reporting_source_secondary_analysis(analysis)
    assert rendered is not None
    assert "0.884s after" in rendered
    assert "both reported into Hubitat through Matter Aqara M3" in rendered
    assert "should not be treated as independent upstream confirmations" in rendered
    assert "not the automation or action that initiated" in rendered


@pytest.mark.asyncio
async def test_bridge_reporting_source_runs_bounded_secondary_correlation_zero_model() -> None:
    mcp = _BedroomCorrelationMCP()
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
    assert counters.get("causal_native_log_reads", 0) == 0
    assert counters["causal_boundary_producer_provenance"] == 1
    assert counters["causal_reporting_source_correlation"] == 1
    assert counters["causal_room_plan"] == 1
    assert counters["causal_provenance_read"] == 1
    assert counters["causal_sensor_read"] == 1
    assert counters["causal_subject_pattern_read"] == 1
    assert counters["causal_sensor_aligned"] == 2
    assert counters["causal_deterministic_finalization"] == 1

    assert "**Main finding:**" in outcome.message
    assert "Matter Hue Bridge Pro" in outcome.message
    assert "**Reporting path:**" in outcome.message
    assert "**Motion/presence:**" in outcome.message
    assert "Bedroom 1 FP300 sensor: 2/3" in outcome.message
    assert "**Limit:**" in outcome.message
    assert "do not prove the exact automation/action" in outcome.message

    # The long forensic narrative remains in evidence/Technical Details rather
    # than the main answer.
    assert "**Bounded secondary correlation**" not in outcome.message
    assert "1.2s after" not in outcome.message
    assert "4.4s after" not in outcome.message

    assert not any(name == "hub_read_diagnostics" for name, _args in mcp.calls)
    event_calls = [
        args.get("args", {}).get("deviceId")
        for name, args in mcp.calls
        if name == "hub_read_devices" and args.get("tool") == "hub_list_device_events"
    ]
    assert event_calls.count("7840") == 3
    assert event_calls.count("7200") == 1
    assert event_calls.count("7300") == 1
