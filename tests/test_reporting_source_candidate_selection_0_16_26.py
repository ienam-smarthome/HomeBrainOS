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


LIGHT = _device(
    "7840",
    "Bedroom 1 Light",
    "Bedroom 1",
    ["Switch", "Light", "SwitchLevel"],
    attributes={"switch": "off", "level": 45},
    commands=["on", "off", "setLevel"],
)
DIMMER = _device(
    "7901",
    "Bedroom 1 dimmer",
    "Button Controllers",
    ["PushableButton", "HoldableButton"],
)
BUTTON = _device(
    "7744",
    "Bedroom 1 button",
    "Button Controllers",
    ["PushableButton"],
)
FP300 = _device(
    "7774",
    "Bedroom 1 FP300 sensor",
    "Bedroom 1",
    ["PresenceSensor", "MotionSensor"],
    attributes={"motion": "active"},
)
FP300_HUMIDITY = _device(
    "7773",
    "Bedroom 1 FP300 humidity",
    "Bedroom 1",
    ["PresenceSensor", "HumidityMeasurement"],
    attributes={"humidity": 47},
)
FP300_LUX = _device(
    "7775",
    "Bedroom 1 FP300 lux",
    "Bedroom 1",
    ["PresenceSensor", "IlluminanceMeasurement"],
    attributes={"illuminance": 18},
)
SOFT = _device(
    "7756",
    "Bedroom 1 Soft Sensor",
    "Bedroom 1",
    ["MotionSensor"],
    attributes={"motion": "inactive"},
)
ALL_DEVICES = [
    LIGHT,
    DIMMER,
    BUTTON,
    FP300_HUMIDITY,
    FP300_LUX,
    FP300,
    SOFT,
]


def test_candidate_ranking_prefers_dimmer_and_physical_presence_source() -> None:
    controllers = DeviceQueryService._room_controller_candidates(
        ALL_DEVICES,
        "Bedroom 1",
    )
    sensors = DeviceQueryService._room_trigger_sensor_candidates(
        ALL_DEVICES,
        "Bedroom 1",
    )

    assert [row["label"] for row in controllers[:2]] == [
        "Bedroom 1 dimmer",
        "Bedroom 1 button",
    ]
    assert [row["matchBasis"] for row in controllers[:2]] == [
        "label-affinity",
        "label-affinity",
    ]

    assert [row["label"] for row in sensors[:2]] == [
        "Bedroom 1 FP300 sensor",
        "Bedroom 1 Soft Sensor",
    ]
    assert sensors[0]["suggestedHistoryAttributes"] == ["motion"]
    assert sensors[0]["exposedOccupancyAttribute"] == "motion"
    assert sensors[1]["suggestedHistoryAttributes"] == ["motion"]
    assert "Bedroom 1 FP300 humidity" not in {
        row["label"] for row in sensors
    }
    assert "Bedroom 1 FP300 lux" not in {
        row["label"] for row in sensors
    }


_SWITCH_ROWS = [
    ("off", "2026-09-24T08:14:38.289+0100"),
    ("on", "2026-09-24T08:06:14.134+0100"),
    ("off", "2026-09-24T08:05:54.228+0100"),
    ("on", "2026-09-24T08:01:41.288+0100"),
    ("off", "2026-09-24T08:01:29.245+0100"),
    ("on", "2026-09-24T07:59:22.538+0100"),
    ("off", "2026-09-24T07:44:38.516+0100"),
    ("on", "2026-09-24T07:43:03.256+0100"),
    ("off", "2026-09-24T07:38:37.369+0100"),
    ("on", "2026-09-24T07:34:34.671+0100"),
    ("off", "2026-09-24T07:33:42.372+0100"),
]


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
        for value, date in _SWITCH_ROWS
    ]


def _subject_detail_events() -> list[dict]:
    rows = list(_switch_events())
    recovery = [
        # Existing bridge-level-first pattern.
        ("2026-09-24T08:06:14.155+0100", 100, "2026-09-24T08:06:17.189+0100"),
        # Live alternate ordering: app command first, resulting level later.
        ("2026-09-24T08:01:42.296+0100", 45, "2026-09-24T08:01:41.353+0100"),
        ("2026-09-24T07:59:22.558+0100", 100, "2026-09-24T07:59:25.610+0100"),
        ("2026-09-24T07:43:03.276+0100", 100, "2026-09-24T07:43:06.330+0100"),
        ("2026-09-24T07:34:34.695+0100", 100, "2026-09-24T07:34:34.773+0100"),
    ]
    for level_time, level, command_time in recovery:
        rows.append({
            "name": "level",
            "value": level,
            "description": f"Bedroom 1 Light level is {level}",
            "date": level_time,
            "isStateChange": True,
            "type": "physical",
            "producedBy": {"name": "Matter Hue Bridge Pro", "deviceId": 7790},
        })
        rows.append({
            "name": "command-setLevel",
            "value": None,
            "description": "Command called: setLevel(45)",
            "date": command_time,
            "isStateChange": False,
            "type": "command",
            "producedBy": {
                "name": "Bedroom 1 (⚪ Lights Off)",
                "appId": 4015,
            },
        })
    rows.sort(key=lambda row: row["date"], reverse=True)
    return rows


def _dimmer_events() -> list[dict]:
    return [
        {
            "name": "pushed",
            "value": "1",
            "date": "2026-09-24T08:14:38.100+0100",
            "description": "button 1 pushed",
            "isStateChange": True,
            "type": "physical",
        },
        {
            "name": "pushed",
            "value": "1",
            "date": "2026-09-24T07:44:38.300+0100",
            "description": "button 1 pushed",
            "isStateChange": True,
            "type": "physical",
        },
    ]


def _fp300_events() -> list[dict]:
    return [
        {
            "name": "motion",
            "value": "inactive",
            "date": "2026-09-24T08:14:38.215+0100",
            "description": "motion inactive",
            "isStateChange": True,
            "type": "physical",
        },
        {
            "name": "motion",
            "value": "active",
            "date": "2026-09-24T07:20:00.000+0100",
            "description": "motion active",
            "isStateChange": True,
            "type": "physical",
        },
    ]


def _soft_events() -> list[dict]:
    return [
        {
            "name": "motion",
            "value": "active",
            "date": "2026-09-24T08:10:00.000+0100",
            "description": "motion active",
            "isStateChange": True,
            "type": "physical",
        },
        {
            "name": "motion",
            "value": "inactive",
            "date": "2026-09-24T08:11:00.000+0100",
            "description": "motion inactive",
            "isStateChange": True,
            "type": "physical",
        },
    ]


class _NoProvider:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, _url: str, **kwargs):
        self.requests.append(dict(kwargs))
        raise AssertionError("0.16.26 reporting-source path must remain zero-model")

    async def aclose(self) -> None:
        return None


class _MorningBedroomMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        return [
            MCPTool(
                "hub_read_devices",
                "Read devices and event history.",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read diagnostics.",
                {"type": "object", "properties": {}},
            ),
        ]

    async def get_device_identities(self):
        return [dict(item) for item in ALL_DEVICES]

    def peek_device_identities(self):
        return [dict(item) for item in ALL_DEVICES]

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        assert name == "hub_read_devices", (name, arguments)
        leaf = arguments.get("tool")
        args = arguments.get("args") or {}

        if leaf == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"devices": [dict(item) for item in ALL_DEVICES]},
            )

        assert leaf == "hub_list_device_events", arguments
        device_id = str(args.get("deviceId") or "")
        attribute = args.get("attribute")

        if device_id == "7840" and attribute == "switch":
            events = _switch_events()
        elif device_id == "7840" and attribute == "command-on":
            events = []
        elif device_id == "7840" and attribute is None:
            events = _subject_detail_events()
        elif device_id == "7901":
            events = _dimmer_events()
        elif device_id == "7744":
            events = []
        elif device_id == "7774":
            events = _fp300_events()
        elif device_id in {"7773", "7775"}:
            raise AssertionError(
                ("non-occupancy FP300 child must not be queried", device_id)
            )
        elif device_id == "7756":
            events = _soft_events()
        else:
            raise AssertionError(("unexpected event read", device_id, attribute))

        return MCPToolResult(
            name,
            arguments,
            {},
            "ok",
            {"events": events, "count": len(events)},
        )


@pytest.mark.asyncio
async def test_morning_bridge_case_checks_two_candidates_and_downstream_recovery() -> None:
    mcp = _MorningBedroomMCP()
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
    assert counters["causal_provenance_read"] == 2
    assert counters["causal_sensor_read"] == 2
    assert counters["causal_subject_pattern_read"] == 1
    assert counters["causal_level_recovery_pattern"] == 5
    assert counters["causal_deterministic_finalization"] == 1

    message = outcome.message
    assert "Matter Hue Bridge Pro" in message
    assert "Bedroom 1 dimmer" in message
    assert "Bedroom 1 button" in message
    assert "Bedroom 1 FP300 sensor" in message
    assert "Bedroom 1 Soft Sensor" in message

    assert "same-room controller Bedroom 1 button" not in message
    assert "same-room controller Bedroom 1 dimmer" not in message
    assert "assigned to Hubitat room Button Controllers" in message

    assert "Bedroom 1 FP300 sensor" in message
    assert "no bounded correlation with the observed ON transitions" in message
    assert "inactive edge(s) shortly before observed OFF boundaries" in message

    assert "Downstream level-recovery pattern" in message
    assert "5 of 5 observed ON transition(s)" in message
    assert "4 level-first sequence(s)" in message
    assert "1 command-first sequence(s)" in message
    assert "resulting level 45" in message
    assert "Bedroom 1 (⚪ Lights Off)" in message
    assert "not evidence that the app initiated the ON" in message
    assert "specific requested ON transition also shows" in message

    assert "FP300 triggered" not in message
    assert "Aqara" not in message

    event_calls = [
        (
            str(args.get("args", {}).get("deviceId") or ""),
            args.get("args", {}).get("attribute"),
        )
        for name, args in mcp.calls
        if name == "hub_read_devices"
        and args.get("tool") == "hub_list_device_events"
    ]
    assert sum(1 for device_id, _attr in event_calls if device_id == "7840") == 3
    assert sum(1 for device_id, _attr in event_calls if device_id == "7901") == 1
    assert sum(1 for device_id, _attr in event_calls if device_id == "7744") == 1
    assert sum(1 for device_id, _attr in event_calls if device_id == "7774") == 1
    assert sum(1 for device_id, _attr in event_calls if device_id == "7773") == 0
    assert sum(1 for device_id, _attr in event_calls if device_id == "7775") == 0
    assert sum(1 for device_id, _attr in event_calls if device_id == "7756") == 1
    assert not any(name == "hub_read_diagnostics" for name, _ in mcp.calls)
