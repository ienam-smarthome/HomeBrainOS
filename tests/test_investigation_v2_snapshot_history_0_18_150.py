"""v0.18.150: verified status cannot disappear from synthesis when history is empty.

Synthetic MCP calls only; no real Hubitat access, device writes, or paid model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.synthesis import assemble_grounded_answer
from investigation_v2.evaluate import evaluate_v2_with_model


def gateway():
    return MCPTool(
        "hub_read_devices", "Read verified device data",
        {"type": "object", "properties": {
            "tool": {"type": "string", "enum": [
                "hub_get_device", "hub_list_device_events"]},
            "args": {"type": "object", "properties": {
                "deviceId": {"type": "string"},
                "hoursBack": {"type": "integer", "maximum": 744},
                "attribute": {"type": "string"},
                "limit": {"type": "integer", "maximum": 500},
            }, "required": ["deviceId"], "additionalProperties": False},
        }, "required": ["tool", "args"], "additionalProperties": False},
        annotations={"readOnlyHint": True},
    )


def current_response():
    return {"id": "7103", "attributes": {
        "healthStatus": "offline", "deviceHealth": "unknown",
        "mqttStatus": "connected", "switch": "off",
        "power": 8, "energy": 35.85,
        "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
        "brokerPassword": "NEVER_EXPOSE_THIS_SECRET",
        "secretApiKey": "NEVER_EXPOSE_THIS_SECRET",
    }}


def current_receipt():
    name = "hub_read_devices"
    args = {"tool": "hub_get_device", "args": {"deviceId": "7103"}}
    result = MCPToolResult(name, args, raw={}, text="NEVER_EXPOSE_THIS_SECRET",
                           data=current_response(), is_error=False)
    return project_read_receipt(name, args, result, source_request_id="current")


def test_synthesis_preserves_current_status_without_inventing_a_timed_event():
    case = build_case_file("Why is Bedroom 3 Mesh offline?", [current_receipt()])
    assert case.records == []
    assert len(case.device_snapshots) == 1
    output = assemble_grounded_answer(case, [], {
        "selected_record_ids": [], "hypothesis_order": [],
    })
    for sample in ("healthStatus=offline", "mqttStatus=connected",
                   "deviceHealth=unknown", "switch=off",
                   "lastSeen=Mon Oct 12 01:30:01 BST 2026"):
        assert sample in output.text
    assert "historical event or proof of physical reachability" in output.text
    assert "Reported power/energy values may be stale" in output.text
    assert "No source-backed time-stamped event" in output.text
    assert "NEVER_EXPOSE_THIS_SECRET" not in output.text


class FakeMCP:
    async def list_tools(self):
        return [gateway()]


class FakeExecutor:
    def __init__(self, mcp, *, recover_unfiltered=True):
        self.mcp = mcp
        self.calls = []
        self.recover_unfiltered = recover_unfiltered

    async def execute(self, name, arguments, *, tool, record_evidence):
        assert name == "hub_read_devices"
        assert record_evidence is False
        assert tool.name == name
        assert arguments["args"]["deviceId"] == "7103"
        self.calls.append(dict(arguments))
        operation = arguments["tool"]
        if operation == "hub_get_device":
            data = current_response()
        elif operation == "hub_list_device_events":
            assert arguments["args"]["limit"] <= 50
            if arguments["args"].get("attribute") == "switch":
                data = {"deviceId": "7103", "events": []}
            else:
                data = {"deviceId": "7103", "events": (
                    [{"deviceId": "7103", "name": "healthStatus",
                      "value": "offline",
                      "date": "2026-10-12T00:33:46+00:00"}]
                    if self.recover_unfiltered else []
                )}
        else:
            raise AssertionError("Unapproved tool")
        return ToolExecution(
            name=name, arguments=arguments, effect=ToolEffect.READ,
            success=True, elapsed_ms=1, content="", result=MCPToolResult(
                name, arguments, raw={}, text="NEVER_EXPOSE_THIS_SECRET",
                data=data, is_error=False,
            ),
        )


async def model_finished(_case, _round):
    return {"hypotheses": [], "reads": [], "finish": True}


@pytest.mark.asyncio
async def test_empty_switch_history_retries_one_bounded_unfiltered_page():
    mcp = FakeMCP()
    exe = FakeExecutor(mcp)
    result = await run_read_only_investigation(
        question="Investigate Bedroom 3 Mesh", mcp=mcp, executor=exe,
        propose=model_finished, verified_entity_ids=("7103",),
        max_rounds=1, bootstrap_device_context=True,
        bootstrap_source_identity=False,
    )
    assert result.executed_reads == 3
    assert [x["tool"] for x in exe.calls] == [
        "hub_get_device", "hub_list_device_events", "hub_list_device_events",
    ]
    assert exe.calls[1]["args"]["attribute"] == "switch"
    assert "attribute" not in exe.calls[2]["args"]
    assert len(result.case.records) == 1
    assert result.case.records[0].action == "healthStatus"
    assert result.case.records[0].value == "offline"
    assert result.case.coverage[1].source_returned_rows == 0
    assert any(x.get("stage") == "history_unfiltered" and
               x.get("status") == "read_attempt_completed"
               for x in result.bootstrap_diagnostics)
    assert "NEVER_EXPOSE_THIS_SECRET" not in json.dumps(result.to_dict())


@pytest.mark.asyncio
async def test_both_histories_empty_still_keeps_current_observations():
    mcp = FakeMCP()
    exe = FakeExecutor(mcp, recover_unfiltered=False)
    result = await run_read_only_investigation(
        question="Investigate Bedroom 3 Mesh", mcp=mcp, executor=exe,
        propose=model_finished, verified_entity_ids=("7103",),
        max_rounds=1, bootstrap_device_context=True,
        bootstrap_source_identity=False,
    )
    assert result.executed_reads == 3
    assert len(result.case.records) == 0
    assert len(result.case.device_snapshots) == 1
    assert all(c.source_complete is not True for c in result.case.coverage)


@pytest.mark.asyncio
async def test_snapshot_only_evaluation_skips_model_atomic_claim_and_repair():
    mcp = FakeMCP()
    exe = FakeExecutor(mcp, recover_unfiltered=False)
    calls = []
    async def chat(_messages, _tools):
        calls.append(True)
        if len(calls) > 1:
            raise AssertionError("No unsupported atomic synthesis/repair round")
        return {"content": json.dumps({
            "hypotheses": [], "reads": [], "finish": True,
        })}
    outcome = await evaluate_v2_with_model(
        explicitly_authorised=True, question="Investigate Bedroom 3 Mesh",
        chat=chat, mcp=mcp, executor=exe,
        verified_entity_ids=("7103",), max_rounds=1,
        bootstrap_device_context=True, bootstrap_source_identity=False,
        enable_atomic_claim_validation=True,
        enable_evidence_narrative=True,
    )
    assert len(calls) == 1
    assert outcome.atomic_claim_review is None
    assert outcome.answer.root_cause_verified is False
    assert "healthStatus=offline" in outcome.answer.text
    assert "current_snapshot_without_timed_history" in outcome.answer.validation_issues
    assert "no source-backed" in outcome.answer.text.lower()
    assert "NEVER_EXPOSE_THIS_SECRET" not in json.dumps(outcome.to_dict())


def test_unsupported_and_sensitive_snapshot_fields_never_leave_source_adapter():
    case = build_case_file("Investigate", [current_receipt()])
    assert "NEVER_EXPOSE_THIS_SECRET" not in json.dumps(case.to_dict())
    assert "brokerPassword" not in json.dumps(case.to_dict())
