"""Regression: v0.18.186 target warnings were strong, but device mode
payloads were hidden and a final synthesis timed out after further failures.
The same host contracts apply to any device or diagnostic question.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0, str(APP))
from mcp_client import MCPTool, MCPToolResult
from investigation_v2.native_read_agent import _payload, run_native_read_agent
from investigation_v2.native_evidence_focus import focused_highlights
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor,
)
from investigation_v2.native_entity_lookup import NAME

DEVICE = MCPTool("hub_read_devices", "Read device", {
    "type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_get_device"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]}, annotations={"readOnlyHint": True})
LOGS = MCPTool("hub_read_diagnostics", "Read logs", {
    "type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_get_logs"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]}, annotations={"readOnlyHint": True})


def tool(name, arguments):
    return {"function": {"name": name, "arguments": arguments}}


def test_configuration_projection_preserves_driver_metadata_not_secrets_or_source():
    data = {
        "id": "7934", "label": "Google Nest Hub",
        "mode": "configuration",
        "deviceInfo": {
            "id": "7934", "driverName": "Google Cast",
            "namespace": "ienam", "manufacturer": "Google",
            "authToken": "this-must-remain-private",
            "ipAddress": "192.168.1.133",
        },
        "editableFields": [
            "logEnable", "descriptionText", "apiToken", "password"
        ],
        "preferences": {
            "logEnable": True, "refreshSeconds": 30,
            "accessToken": "DO_NOT_EXPOSE",
        },
        "driverSource": {
            "status": "available", "available": True,
            "code": "private full driver code should not appear",
            "driverName": "Google Cast",
        },
        "deviceInfoRead": {"status": "complete", "source": "/device/config/7934"},
    }
    result = MCPToolResult("hub_read_devices", {}, {}, "", data)
    projected = _payload(result, "hub_get_device")
    assert projected["device_mode"] == "configuration"
    assert projected["device_identity"]["driverName"] == "Google Cast"
    assert projected["device_identity"]["namespace"] == "ienam"
    assert projected["preference_names"] == ["logEnable", "refreshSeconds"]
    assert projected["editable_field_names"] == ["logEnable", "descriptionText"]
    assert projected["driver_source_content_omitted"] is True
    displayed = str(projected)
    assert "DO_NOT_EXPOSE" not in displayed
    assert "this-must-remain-private" not in displayed
    assert "192.168.1.133" not in displayed
    assert "private full driver code" not in displayed
    lines = focused_highlights(
        [{"read": 4, "operation": "hub_get_device", "source_data": projected}],
        ["7934"])
    assert "Google Cast" in "".join(lines)


def test_sectioned_details_keep_provenance_not_arbitrary_content():
    result = MCPToolResult("hub_read_devices", {}, {}, "", {
        "id": "7934", "mode": "details", "name": "Google Nest Hub",
        "sections": {
            "attributes": {"status": "complete", "source": "/device/fullJson/7934"},
            "data": {"status": "complete", "accessToken": "NOT_FOR_MODEL"},
        },
        "sectionRead": {"data": {"status": "complete", "source": "/device/fullJson/7934"}},
    })
    projected = _payload(result, "hub_get_device")
    assert projected["device_mode"] == "details"
    assert "data" in projected["sections_present"]
    assert projected["section_read_status"]["data"]["status"] == "complete"
    assert "NOT_FOR_MODEL" not in str(projected)


@pytest.mark.asyncio
async def test_two_failed_same_target_reads_stop_more_device_errors_and_skip_synthesis():
    mcp = FakeMCP([DEVICE, LOGS])
    async def identities():
        return [{"id": "7934", "label": "Google Nest Hub"}]
    mcp.get_device_identities = identities
    log = {"entries": [
        {"name": "Google Nest Hub", "type": "dev", "level": "WARN",
         "time": "2026-10-28 17:04:48.106",
         "message": "dev|7934|Google Nest Hub|method runQ ran for 147,429ms"},
        {"name": "Google Nest Hub", "type": "dev", "level": "WARN",
         "time": "2026-10-28 19:55:19.399",
         "message": "dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}
    ]}
    executor = FakeExecutor(mcp, [
        {"id": "7934", "label": "Google Nest Hub",
         "attributes": [{"name": "networkStatus", "value": "online"},
                        {"name": "status", "value": "idle"}]},
        log, None, None,
    ])
    turn = 0
    async def model(messages, tools):
        nonlocal turn
        turn += 1
        assert tools  # A needless final model-only synthesis would fail this test.
        if turn == 1:
            return {"tool_calls": [tool(NAME, {"name": "Google Nest Hub"})]}
        if turn == 2:
            return {"tool_calls": [
                tool("hub_read_devices", {
                    "tool": "hub_get_device",
                    "args": {"deviceId": "7934", "mode": "summary"},
                }),
                tool("hub_read_diagnostics", {
                    "tool": "hub_get_logs",
                    "args": {"deviceId": "7934", "mode": "past",
                             "level": "warn", "limit": 100},
                }),
            ]}
        # Different parameters: these are not exact duplicate calls.
        return {"tool_calls": [tool("hub_read_devices", {
            "tool": "hub_get_device",
            "args": {"deviceId": "7934", "mode": "details",
                     "sections": ["data", f"variant{turn}"]},
        })]}
    result = await run_native_read_agent(
        question="Why does Google Nest Hub cause excessive load?",
        chat=model, mcp=mcp, executor=executor, max_rounds=6,
    )
    diag = result["native_diagnostics"]
    assert diag["successful_reads"] == 2
    assert diag["reads_executed"] == 4
    assert len(executor.calls) == 4
    assert diag["blocked_repeat_errors"] >= 1
    assert diag["failed_scoped_operations"][0]["failures"] == 2
    assert diag["final_synthesis_skipped_reason"] == "source_evidence_at_investigation_limit"
    assert diag["final_synthesis"] == "host_evidence_fallback"
    assert "runQ" in result["answer"]["text"]
    assert "hub instability is not independently verified" in result["answer"]["text"]
