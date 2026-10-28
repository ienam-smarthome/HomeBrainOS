"""v0.18.145 evidence-first, no-device-writes regressions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.device_context import device_context_proposals
from investigation_v2.evidence import build_case_file
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.model_adapter import V2ModelProposer
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect


def manifest(write=False):
    return [MCPTool(
        "hub_read_devices" if not write else "hub_manage_devices",
        "Verified Hubitat gateway",
        {"type": "object", "properties": {
            "tool": {"type": "string", "enum": [
                "hub_get_device", "hub_list_device_events"]},
            "args": {"type": "object", "properties": {
                "deviceId": {"type": "string"},
                "attribute": {"type": "string"},
                "hoursBack": {"type": "integer", "maximum": 744},
                "limit": {"type": "integer", "maximum": 500},
            }, "required": ["deviceId"], "additionalProperties": False},
        }, "required": ["tool", "args"], "additionalProperties": False},
        annotations={"readOnlyHint": not write, "mutates": write})]


def receipt(op, data, request):
    tool = "hub_read_devices"
    return project_read_receipt(tool,
        {"tool": op, "args": {"deviceId": "7103"}},
        MCPToolResult(tool, {}, raw={}, text="PRIVATE_PASSWORD NEVER COPY",
                      data=data, is_error=False),
        source_request_id=request)


def test_snapshot_retains_only_safe_device_status_and_last_contact():
    stamp = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    event = receipt("hub_get_device", {"id": "7103", "attributes": {
        "switch": "off", "healthStatus": "offline",
        "mqttStatus": "connected", "lastSeen": stamp,
        "brokerPassword": "PRIVATE_PASSWORD",
        "ipAddress": "192.168.1.136", "customSecret": "SECRET"}},
        "status")
    assert event["details"]["deviceSnapshot"]["attributes"]["lastSeen"] == stamp
    case = build_case_file("Why offline?", [event])
    assert len(case.device_snapshots) == 1
    assert not case.records  # current observation cannot invent 14-day-old event
    text = json.dumps(case.to_dict())
    assert "PRIVATE_PASSWORD" not in text
    assert "192.168.1.136" not in text
    assert "mqttStatus" in text
    assert "healthStatus" in text
    hist = device_context_proposals(manifest(), ["7103"], case, stage="history")
    args = hist[0]["arguments"]["args"]
    assert args["hoursBack"] >= 336  # live lastSeen extends beyond 7-day default
    assert args["attribute"] == "switch"
    assert args["limit"] == 50


def test_manifest_write_and_ambiguous_target_cannot_trigger_any_reads():
    empty = build_case_file("Why offline?", [])
    assert device_context_proposals(manifest(write=True), ["7103"], empty, stage="current") == []
    assert device_context_proposals(manifest(), ["7103", "7104"], empty, stage="history") == []
    assert device_context_proposals([], ["7103"], empty, stage="current") == []


class FakeMCP:
    async def list_tools(self):
        return manifest()


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp = mcp
        self.calls = []

    async def execute(self, name, arguments, *, tool, record_evidence):
        assert record_evidence is False
        assert name == "hub_read_devices"
        op = arguments["tool"]
        self.calls.append((op, dict(arguments["args"])))
        stamp = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        if op == "hub_get_device":
            data = {"id": "7103", "attributes": {
                "switch": "off", "healthStatus": "offline",
                "mqttStatus": "connected", "lastSeen": stamp}}
        else:
            data = {"deviceId": "7103", "events": [
                {"deviceId": "7103", "name": "command-off", "type": "command",
                 "date": stamp, "producedBy": {"id": "3950"}},
                {"deviceId": "7103", "name": "switch", "value": "off",
                 "date": stamp},
            ]}
        result = MCPToolResult(name, arguments, raw={}, text="SECRET_UNSAFE",
                               data=data, is_error=False)
        return ToolExecution(name=name, arguments=arguments,
                             effect=ToolEffect.READ, success=True, elapsed_ms=1,
                             content="SECRET_UNSAFE", result=result)


class RejectedThenFinished:
    def __init__(self):
        self.feedback = []
        self.rounds = []
    def set_validation_feedback(self, reasons):
        self.feedback = reasons
    async def __call__(self, case, round_index):
        self.rounds.append((round_index, len(case.records),
                            len(case.device_snapshots)))
        if round_index == 0:
            return {"hypotheses": [], "reads": [{
                "tool": "imaginary_hub_tool",
                "arguments": {"tool": "hub_get_device", "args": {"deviceId": "7103"}},
                "discriminator": "Check actual target status",
                "information_gain": "Verify current source state",
                "hypothesis_ids": [],
            }], "finish": False}
        return {"hypotheses": [], "reads": [], "finish": True}


@pytest.mark.asyncio
async def test_live_gateway_preflight_stops_when_only_tool_is_unavailable():
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)
    model = RejectedThenFinished()
    output = await run_read_only_investigation(
        question="Why is my connected socket still offline?",
        mcp=mcp, executor=executor, propose=model,
        verified_entity_ids=["7103"], max_rounds=3,
        bootstrap_device_context=True, bootstrap_source_identity=False,
    )
    assert [op for op, _ in executor.calls] == [
        "hub_get_device", "hub_list_device_events"]
    assert executor.calls[1][1]["hoursBack"] >= 336
    assert output.stopped_because == "model_read_tools_unavailable"
    assert output.executed_reads == 2
    assert len(model.rounds) == 1
    assert model.rounds[0][1:] == (2, 1)
    assert model.feedback == []
    assert output.planning_diagnostics[0]["unavailable_model_tool_count"] == 1
    report = format_investigation_report(
        output.case, output.hypotheses, output.stopped_because)
    assert "Current device snapshot" in report
    assert "command" in report.lower()
    assert "physical bulb" not in report
    assert "SECRET_UNSAFE" not in json.dumps(output.to_dict())


@pytest.mark.asyncio
async def test_model_feedback_contains_only_host_known_validations():
    seen = []
    async def fake_chat(messages, tools):
        seen.append(json.loads(messages[-1]["content"]))
        return {"content": json.dumps({"hypotheses": [], "reads": [], "finish": True})}
    model = V2ModelProposer(fake_chat, manifest(), verified_entity_ids=["7103"])
    model.set_validation_feedback(["tool not in live MCP manifest",
                                   "SECRET_FAKE_GIVE_PASSWORD"])
    await model(build_case_file("why?", []), 1)
    assert seen[0]["previous_plan_validation"] == ["tool not in live MCP manifest"]
    assert "SECRET_FAKE" not in json.dumps(seen)
