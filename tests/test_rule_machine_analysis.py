"""End-to-end acceptance gate for read-only Rule Machine app analysis."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from homebrain_agent import UnifiedMCPAgent
from mcp_client import MCPToolResult
from rule_machine_analysis import parse_rule_analysis_request, render_rule_analysis


def _device(id_, label, *, attrs=None, parent=None):
    record = {
        "id": str(id_), "label": label, "name": label, "room": "Living Room",
        "capabilities": ["MotionSensor", "PresenceSensor", "IlluminanceMeasurement"],
        "attributes": attrs or {},
    }
    if parent:
        record["parentDeviceId"] = str(parent)
    return record


def _identities():
    return [
        _device("7339", "FP2 Livingroom Lux (homekit)", parent="7334"),
        _device("7340", "FP2 Livingroom sensor (homekit)", parent="7334"),
        _device("7334", "FP2 Livingroom"),
    ]


def _config():
    return {
        "success": True,
        "app": {"id": 3602, "label": "Lighting: livingroom low light"},
        "page": {"sections": [
            {"title": "Trigger Events", "paragraphs": [
                "Mode changes to Afternoon, Late afternoon, Sunset",
                "IF (FP2 Livingroom sensor (homekit) motion is active AND "
                "FP2 Livingroom Lux (homekit) is <= 40) "
                "THEN On: Livingroom Light 1 END-IF",
            ], "inputs": []},
        ]},
    }


class _RuleMCP:
    def __init__(self, *, fail_config=False, absent_parent=False):
        self.calls = []
        self.fail_config = fail_config
        self.absent_parent = absent_parent

    async def get_cached_devices(self):
        return _identities()

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        assert name in {"hub_read_apps_code", "hub_read_devices"}
        assert arguments["tool"] in {"hub_get_app_config", "hub_get_device"}
        if name == "hub_read_apps_code":
            assert arguments == {
                "tool": "hub_get_app_config",
                "args": {"appId": "3602", "includeSettings": False},
            }
            return MCPToolResult(
                name, arguments, {}, "ok",
                {"error": "no authorization", "success": False}
                if self.fail_config else _config(),
                is_error=self.fail_config,
            )
        device_id = arguments["args"]["deviceId"]
        assert device_id in {"7334", "7339", "7340"}
        payloads = {
            "7334": _device("7334", "FP2 Livingroom", attrs={
                "healthStatus": "offline", "hapStatus": "connecting (live)",
            }),
            "7339": _device(
                "7339", "FP2 Livingroom Lux (homekit)",
                attrs={"illuminance": 0}, parent="7334",
            ),
            "7340": _device(
                "7340", "FP2 Livingroom sensor (homekit)",
                attrs={"motion": "active", "presence": "present"}, parent="7334",
            ),
        }
        result = payloads[device_id]
        if self.absent_parent and device_id == "7334":
            return MCPToolResult(
                name, arguments, {}, "unavailable",
                {"success": False, "error": "Not authorised"}, is_error=True,
            )
        return MCPToolResult(name, arguments, {}, "ok", result)


def test_parser_covers_requested_app_and_read_only_parent_but_not_writes():
    assert parse_rule_analysis_request(
        "Analyse Rule Machine app 3602 and verify FP2 parent device ID 7334. Read-only."
    ) == ("3602", "7334")
    assert parse_rule_analysis_request("review app 3602") == ("3602", None)
    assert parse_rule_analysis_request("why did Livingroom Light 1 turn on?") is None
    assert parse_rule_analysis_request("disable rule machine app 3602") is None
    assert parse_rule_analysis_request("check livingroom status and states") is None


@pytest.mark.asyncio
async def test_agent_rule_analysis_single_direct_config_read_and_parent_health():
    mcp = _RuleMCP()
    agent = UnifiedMCPAgent(mcp, "key")
    answer = await agent.process_user_request_result(
        "Analyse Rule Machine app 3602, verify parent device ID 7334, "
        "and determine whether retained FP2 values could allow a ghost action. Read-only.",
        session_id="rule-analysis-3602",
    )
    msg = answer.message
    assert "Lighting: livingroom low light" in msg
    assert "Mode changes to Afternoon" in msg
    assert "IF (FP2 Livingroom" in msg
    assert "FP2 Livingroom (ID 7334): Offline" in msg
    assert "healthStatus: offline" in msg
    assert "hapStatus: connecting (live)" in msg
    assert "FP2 Livingroom Lux (homekit) (ID 7339)" in msg
    assert "FP2 Livingroom sensor (homekit) (ID 7340)" in msg
    assert "Last reported, freshness unverified: illuminance=0" in msg
    assert "Last reported, freshness unverified: motion=active, presence=present" in msg
    assert "Possibly" in msg
    assert "Historical cause remains unverified" in msg
    assert "will execute" not in msg
    assert len(mcp.calls) == 4
    assert sum(a["tool"] == "hub_get_app_config" for _, a in mcp.calls) == 1
    assert sorted(
        a["args"]["deviceId"]
        for _, a in mcp.calls if a["tool"] == "hub_get_device"
    ) == ["7334", "7339", "7340"]
    assert answer.metrics["counters"].get("model_rounds", 0) == 0
    assert len(answer.evidence) == 4
    assert all(entry["effect"] == "read" for entry in answer.evidence)


@pytest.mark.asyncio
async def test_missing_app_config_is_partial_and_does_not_invent_rule_logic():
    mcp = _RuleMCP(fail_config=True)
    agent = UnifiedMCPAgent(mcp, "key")
    answer = await agent.process_user_request_result(
        "Analyse Rule Machine app 3602 and verify parent device ID 7334.",
        session_id="config-error-case",
    )
    assert "Investigation status: PARTIAL" in answer.message
    assert "Configuration unavailable" in answer.message
    assert "Mode changes to Afternoon" not in answer.message
    assert "Required expression" not in answer.message
    assert "Requested parent FP2 Livingroom (ID 7334): Offline" in answer.message
    assert len(mcp.calls) == 2
    assert answer.evidence[0]["success"] is False
    assert answer.metrics["counters"].get("model_rounds", 0) == 0


@pytest.mark.asyncio
async def test_unreadable_parent_is_unknown_not_offline_and_children_qualified():
    mcp = _RuleMCP(absent_parent=True)
    agent = UnifiedMCPAgent(mcp, "key")
    answer = await agent.process_user_request_result(
        "Analyse Rule Machine app 3602 and verify parent device ID 7334",
        session_id="unreadable-parent-case",
    )
    assert "Linked parent Device 7334 (ID 7334): Connection unverified" in answer.message
    assert "Parent health unverified" in answer.message
    assert "Investigation status: PARTIAL" in answer.message
    assert "Linked parent Device 7334 (ID 7334): Offline" not in answer.message
    assert answer.metrics["counters"].get("model_rounds", 0) == 0


def test_no_config_never_proves_any_specific_rule_trigger():
    result = render_rule_analysis(
        "3602", None, [], {}, explicit_parent_id=None,
    )
    assert "Configuration unavailable" in result
    assert "Mode changes" not in result
    assert "PARTIAL" in result
    assert "could" not in result.lower() or "Possibly" in result
