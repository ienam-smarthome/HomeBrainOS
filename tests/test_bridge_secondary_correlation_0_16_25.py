from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_query_service import DeviceQueryService  # noqa: E402
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _device(
    device_id: str,
    label: str,
    room: str,
    capabilities: list[str],
    *,
    attributes: dict | None = None,
    commands: list[str] | None = None,
) -> dict:
    return {
        "id": device_id,
        "label": label,
        "name": label,
        "room": room,
        "capabilities": list(capabilities),
        "attributes": dict(attributes or {}),
        "commands": list(commands or []),
    }


SUBJECT = _device(
    "7840",
    "Bedroom 1 Light",
    "Bedroom 1",
    ["Switch", "SwitchLevel"],
    attributes={"switch": "off", "level": 80},
    commands=["on", "off", "setLevel"],
)
DIMMER = _device(
    "7901",
    "Bedroom 1 dimmer",
    "Bedroom 1",
    ["PushableButton", "Battery"],
    attributes={"battery": 80},
)
FP300 = _device(
    "7902",
    "Bedroom 1 FP300 sensor",
    "Bedroom 1",
    ["PresenceSensor"],
    attributes={"presence": "present"},
)
SOFT_SENSOR = _device(
    "7903",
    "Bedroom 1 Soft Sensor",
    "Bedroom 1",
    ["MotionSensor"],
    attributes={"motion": "inactive"},
)


def test_presence_sensor_ranks_ahead_of_motion_soft_sensor_in_same_room() -> None:
    ranked = DeviceQueryService._room_trigger_sensor_candidates(
        [SOFT_SENSOR, FP300],
        "Bedroom 1",
    )

    assert [row["label"] for row in ranked[:2]] == [
        "Bedroom 1 FP300 sensor",
        "Bedroom 1 Soft Sensor",
    ]
    assert ranked[0]["suggestedHistoryAttributes"] == ["presence"]


def _switch_events() -> list[dict]:
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

    def row(value: str, date: str) -> dict:
        return {
            "name": "switch",
            "value": value,
            "description": f"Bedroom 1 Light switch is {value}",
            "date": date,
            "isStateChange": True,
            "type": "physical",
            "triggered": triggered,
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        }

    return [
        row("off", "2026-09-23T22:22:45.632+0100"),
        row("on", "2026-09-23T22:11:04.111+0100"),
        row("off", "2026-09-23T21:30:00.000+0100"),
        row("on", "2026-09-23T21:18:26.800+0100"),
        row("off", "2026-09-23T21:05:00.000+0100"),
        row("on", "2026-09-23T20:58:17.600+0100"),
        row("off", "2026-09-23T20:47:06.372+0100"),
        row("on", "2026-09-23T20:40:00.000+0100"),
        row("off", "2026-09-23T19:30:00.000+0100"),
        row("on", "2026-09-23T19:11:23.000+0100"),
        row("off", "2026-09-23T19:09:30.000+0100"),
        row("on", "2026-09-23T19:08:42.000+0100"),
    ]


def _dimmer_events() -> list[dict]:
    return [
        {
            "name": "pushed",
            "value": "1",
            "date": "2026-09-23T22:22:45.100+0100",
            "description": "button 1 pushed",
            "isStateChange": True,
            "type": "physical",
        },
        {
            "name": "pushed",
            "value": "1",
            "date": "2026-09-23T19:08:42.200+0100",
            "description": "button 1 pushed",
            "isStateChange": True,
            "type": "physical",
        },
    ]


def _fp300_events() -> list[dict]:
    return [
        {
            "name": "presence",
            "value": "present",
            "date": "2026-09-23T21:18:31.200+0100",
            "description": "presence active",
            "isStateChange": True,
        },
        {
            "name": "presence",
            "value": "present",
            "date": "2026-09-23T20:58:18.800+0100",
            "description": "presence active",
            "isStateChange": True,
        },
        {
            "name": "presence",
            "value": "not present",
            "date": "2026-09-23T20:47:06.292+0100",
            "description": "presence inactive",
            "isStateChange": True,
        },
    ]


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("bounded bridge correlation must not call provider")

    async def aclose(self) -> None:
        return None


class _BedroomBridgeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.identities = [SUBJECT, DIMMER, FP300, SOFT_SENSOR]

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices. hub_list_devices and hub_list_device_events.",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics. hub_get_logs.",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_device_identities(self):
        return [dict(item) for item in self.identities]

    def peek_device_identities(self):
        return [dict(item) for item in self.identities]

    def peek_cached_devices(self):
        return [dict(item) for item in self.identities]

    async def get_cached_devices(self):
        return [dict(item) for item in self.identities]

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        operation = arguments.get("tool")
        args = arguments.get("args") or {}

        if operation == "hub_list_devices":
            data = {"devices": [dict(item) for item in self.identities]}
            return MCPToolResult(name, arguments, {}, "ok", data)

        assert operation == "hub_list_device_events", arguments
        device_id = str(args.get("deviceId") or "")
        attribute = str(args.get("attribute") or "")

        if device_id == "7840" and attribute == "switch":
            events = _switch_events()
        elif device_id == "7840" and attribute == "command-on":
            events = []
        elif device_id == "7901" and attribute == "pushed":
            events = _dimmer_events()
        elif device_id == "7902" and attribute == "presence":
            events = _fp300_events()
        else:
            raise AssertionError(("unexpected history request", device_id, attribute))

        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


@pytest.mark.asyncio
async def test_bridge_reporting_source_adds_bounded_controller_and_fp300_correlation() -> None:
    mcp = _BedroomBridgeMCP()
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
    assert counters["causal_boundary_producer_provenance"] == 1
    assert counters["causal_secondary_correlation"] == 1
    assert counters["causal_secondary_room_read"] == 1
    assert counters["causal_secondary_controller_read"] == 1
    assert counters["causal_secondary_sensor_read"] == 1
    assert counters["causal_secondary_repeated_sensor_pattern"] == 1
    assert counters["causal_deterministic_finalization"] == 1
    assert counters.get("causal_native_log_reads", 0) == 0

    assert "Matter Hue Bridge Pro" in outcome.message
    assert "reporting path into Hubitat" in outcome.message
    assert "Bedroom 1 dimmer" in outcome.message
    assert "Bedroom 1 FP300 sensor" in outcome.message
    assert "2 ON/start" in outcome.message
    assert "1 OFF/end" in outcome.message
    assert "4.4s after" in outcome.message
    assert "1.2s after" in outcome.message
    assert "0.08s before" in outcome.message
    assert "plausible hypothesis" in outcome.message
    assert "not proof that the sensor directly caused the light" in outcome.message

    assert "the FP300 caused" not in outcome.message
    assert "Aqara M3 caused" not in outcome.message

    diagnostics = [
        call for call in mcp.calls
        if call[0] == "hub_read_diagnostics"
    ]
    assert diagnostics == []

    subject_switch_calls = [
        arguments
        for name, arguments in mcp.calls
        if name == "hub_read_devices"
        and arguments.get("tool") == "hub_list_device_events"
        and str(arguments.get("args", {}).get("deviceId")) == "7840"
        and arguments.get("args", {}).get("attribute") == "switch"
    ]
    assert len(subject_switch_calls) == 1

    history_receipts = [
        receipt for receipt in outcome.evidence
        if receipt.get("tool") == "homebrain_device_history"
    ]
    subject_receipts = [
        receipt for receipt in history_receipts
        if receipt.get("details", {}).get("label") == "Bedroom 1 Light"
    ]
    assert len(subject_receipts) == 1
    assert subject_receipts[0]["arguments"]["limit"] == 12

    summaries = [
        receipt for receipt in outcome.evidence
        if receipt.get("tool") == "homebrain_causal_secondary_correlation"
    ]
    assert len(summaries) == 1
    sensor = summaries[0]["details"]["sensor"]
    assert sensor["label"] == "Bedroom 1 FP300 sensor"
    assert sensor["startAlignments"] == 2
    assert sensor["endAlignments"] == 1
    assert sensor["startAfterSubject"] == 2
