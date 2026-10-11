from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_rule_decision_context import (  # noqa: E402
    app_log_window,
    configuration_text,
    execution_log_lines,
    linked_sensor_health_warning,
    proven_lighting_command,
    referenced_sensor_identities,
    render_rule_decision_context,
)
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


def _device(id_, label, room, caps=("Switch",), attrs=None, parent=None):
    row = {
        "id": str(id_), "label": label, "name": label, "room": room,
        "capabilities": list(caps), "attributes": attrs or {},
    }
    if parent is not None:
        row["parentDeviceId"] = str(parent)
    return row


def _identities():
    return [
        _device("7805", "Livingroom Light 1", "Living Room"),
        _device("7334", "FP2 Livingroom", "Living Room"),
        _device(
            "7771", "FP2 Livingroom sensor (homekit)", "Living Room",
            ("MotionSensor", "PresenceSensor"), parent="7334",
        ),
        _device(
            "7772", "FP2 Livingroom Lux (homekit)", "Living Room",
            ("IlluminanceMeasurement",), parent="7334",
        ),
        _device("7001", "FP300 Livingroom sensor", "Living Room", ("MotionSensor",)),
    ]


def _room_devices():
    return [
        _device(
            "7334", "FP2 Livingroom", "Living Room", (),
            {"healthStatus": "offline", "hapStatus": "connecting (live)"},
        ),
        _device(
            "7771", "FP2 Livingroom sensor (homekit)", "Living Room",
            ("MotionSensor",), {"motion": "active", "presence": "present"}, "7334",
        ),
        _device(
            "7001", "FP300 Livingroom sensor", "Living Room",
            ("MotionSensor",), {"motion": "active"},
        ),
    ]


def _config():
    return {
        "app": {"id": 3602, "label": "Lighting: livingroom low light"},
        "page": {
            "sections": [
                {
                    "title": "Trigger Events",
                    "paragraphs": [
                        "Mode changes to Afternoon, Late afternoon, or Sunset",
                        "Required Expression: FP2 Livingroom sensor (homekit) active "
                        "and FP2 Livingroom Lux (homekit) <= 40",
                    ],
                    "inputs": [],
                },
            ],
        },
    }


def _logs():
    return {
        "logs": [
            {
                "time": "2026-10-11T11:00:02.500Z",
                "message": "Triggered: mode changed to Afternoon",
            },
            {
                "time": "2026-10-11T11:00:03.010Z",
                "message": "Required Expression: true",
            },
            {
                "time": "2026-10-11T10:59:00Z",
                "message": "Triggered: unrelated old event",
            },
        ],
    }


def _command_focus():
    return {
        "action": "on",
        "boundaryRole": "start",
        "subject": "Livingroom Light 1",
        "stateBoundary": "2026-10-11T12:00:03.704+0100",
        "producer": {
            "label": "Lighting: livingroom low light",
            "id": "3602",
            "type": "app",
        },
        "command": {"date": "2026-10-11T12:00:03.035+0100"},
    }


def test_app_log_window_respects_local_offset():
    assert app_log_window(_command_focus()) == {
        "appId": "3602",
        "since": "2026-10-11T10:59:51.035Z",
        "until": "2026-10-11T11:00:09.035Z",
        "limit": 60,
    }


def test_log_analysis_uses_only_scoped_timestamp_aligned_messages():
    logs = execution_log_lines(_logs(), _command_focus())
    assert len(logs) == 2
    assert "12:00:02" in logs[0]
    assert "mode changed to Afternoon" in logs[0]
    assert "Required Expression: true" in logs[1]
    assert "unrelated old" not in str(logs)
    assert execution_log_lines({"logs": [
        {"message": "Triggered: no timestamp"},
    ]}, _command_focus()) == []


def test_rule_config_is_not_historical_execution_proof():
    excerpts, text = configuration_text(_config())
    assert any("Mode changes to Afternoon" in line for line in excerpts)
    assert "fp2 livingroom sensor (homekit)" in text
    answer = render_rule_decision_context(
        app_name="Lighting: livingroom low light",
        app_id="3602",
        configured=excerpts,
        logs=[],
        sensor_warnings=[],
    )
    assert "Trigger not independently verified" in answer
    assert "not proof of the historical evaluation" in answer
    assert "actually triggered by Afternoon" not in answer


def test_health_is_qualified_only_for_config_referenced_sensors():
    excerpts, text = configuration_text(_config())
    selected = referenced_sensor_identities(text, _identities(), "Living Room")
    names = {row["label"] for row in selected}
    assert names == {
        "FP2 Livingroom sensor (homekit)", "FP2 Livingroom Lux (homekit)"
    }
    warnings = linked_sensor_health_warning(selected, _room_devices())
    assert warnings
    assert "FP2 Livingroom" in " ".join(warnings)
    assert "currently offline/connecting" in " ".join(warnings)
    assert "FP300" not in " ".join(warnings)
    answer = render_rule_decision_context(
        app_name="Lighting: livingroom low light",
        app_id="3602",
        configured=excerpts, logs=[],
        sensor_warnings=warnings,
    )
    assert "not necessarily at the event time" in answer
    assert "cannot establish whether a retained sensor value caused" in answer


class _MCP:
    def __init__(self, *, fail_config=False, fail_logs=False):
        self.calls = []
        self.fail_config = fail_config
        self.fail_logs = fail_logs

    async def list_tools(self):
        return [
            MCPTool(
                name, "Hubitat read gateway",
                {"type": "object", "properties": {}},
            )
            for name in (
                "hub_read_devices", "hub_read_diagnostics", "hub_read_apps_code"
            )
        ]

    async def get_device_identities(self):
        return _identities()

    def peek_device_identities(self):
        return _identities()

    def peek_cached_devices(self):
        return []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        leaf, args = arguments["tool"], arguments.get("args") or {}
        if name == "hub_read_apps_code":
            assert leaf == "hub_get_app_config"
            assert args == {"appId": "3602", "includeSettings": False}
            if self.fail_config:
                return MCPToolResult(
                    name, arguments, {}, "error",
                    {"success": False, "error": "App config unavailable"},
                    is_error=True,
                )
            return MCPToolResult(name, arguments, {}, "ok", _config())

        if name == "hub_read_diagnostics":
            assert leaf == "hub_get_logs"
            assert args["appId"] == "3602"
            assert args["since"] == "2026-10-11T10:59:51.035Z"
            if self.fail_logs:
                return MCPToolResult(name, arguments, {}, "no logs", {"logs": []})
            return MCPToolResult(name, arguments, {}, "ok", _logs())

        assert name == "hub_read_devices"
        if leaf == "hub_list_devices":
            assert args == {"detailed": True, "roomFilter": "Living Room"}
            data = {"devices": _room_devices(), "count": 3}
        elif leaf == "hub_list_device_events":
            assert args["deviceId"] == "7805"
            attribute = args["attribute"]
            if attribute == "switch":
                events = [
                    {
                        "name": "switch", "value": "on",
                        "date": "2026-10-11T12:00:03.704+0100",
                        "isStateChange": True,
                    },
                    {
                        "name": "switch", "value": "off",
                        "date": "2026-10-11T01:30:00.000+0100",
                        "isStateChange": True,
                    },
                ]
            elif attribute == "command-on":
                events = [{
                    "name": "command-on",
                    "date": "2026-10-11T12:00:03.035+0100",
                    "isStateChange": False,
                    "description": "Command called: on()",
                    "producedBy": {
                        "label": "Lighting: livingroom low light",
                        "id": "3602", "type": "app",
                    },
                }]
            else:
                raise AssertionError(attribute)
            data = {"events": events, "count": len(events)}
        else:
            raise AssertionError((name, leaf, args))
        return MCPToolResult(name, arguments, {}, "ok", data)


class _NoProvider:
    async def post(self, *_args, **_kwargs):
        raise AssertionError("Proven lighting rule path must not call a model")

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_agent_preserves_command_provenance_and_explains_app_decision():
    mcp = _MCP()
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=_NoProvider(),
        require_sensitive_confirmation=False,
    )
    outcome = await agent.process_user_request_result(
        "why did livingroom light 1 turn on?"
    )
    message = outcome.message
    assert "**Cause:**" in message
    assert "Lighting: livingroom low light issued the ON command" in message
    assert "669 ms later" in message
    assert "### Why the automation decided to act" in message
    assert "mode changed to Afternoon" in message
    assert "Required Expression: true" in message
    assert "Configured triggers/conditions" in message
    assert "currently offline/connecting" in message
    assert "not necessarily at the event time" in message
    assert outcome.metrics["counters"].get("model_rounds", 0) == 0
    assert [(name, args["tool"]) for name, args in mcp.calls].count(
        ("hub_read_apps_code", "hub_get_app_config")
    ) == 1
    assert [(name, args["tool"]) for name, args in mcp.calls].count(
        ("hub_read_diagnostics", "hub_get_logs")
    ) == 1
    assert [(name, args["tool"]) for name, args in mcp.calls].count(
        ("hub_read_devices", "hub_list_devices")
    ) == 1


@pytest.mark.asyncio
async def test_unavailable_config_and_logs_never_invent_trigger():
    mcp = _MCP(fail_config=True, fail_logs=True)
    agent = UnifiedMCPAgent(
        mcp, "key", "model", ai_client=_NoProvider(),
        require_sensitive_confirmation=False,
    )
    outcome = await agent.process_user_request_result(
        "why did livingroom light 1 turn on?"
    )
    assert "Lighting: livingroom low light issued the ON command" in outcome.message
    assert "Trigger not independently verified" in outcome.message
    assert "configuration page" in outcome.message
    assert "mode changed to Afternoon" not in outcome.message
    assert "FP2" not in outcome.message
    assert any(
        r.get("success") is False
        and r.get("sub_tool") == "hub_get_app_config"
        for r in outcome.evidence
    )
