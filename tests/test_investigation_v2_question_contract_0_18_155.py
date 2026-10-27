"""v0.18.155: verified question contract and source-first controller follow-up.

Synthetic read-only MCP tests only: no Hubitat, cloud provider, or writes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.factual_objective import verified_factual_objective
from investigation_v2.factual_report import factual_report
from investigation_v2.evidence import build_case_file
from investigation_v2.source_identity import source_configuration_proposals
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.evaluate import evaluate_v2_with_model
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect


@pytest.mark.parametrize("question,expected", [
    ("Is Livingroom Light 2 currently on or off?", "status"),
    ("Is Livingroom Light 2 on?", "status"),
    ("What is Livingroom Light 2's current state?", "status"),
    ("When did Livingroom Light 2 last turn on and off?", "history"),
    ("When was Livingroom Light 2 last turned off?", "history"),
    ("What were Livingroom Light 2's most recent ON and OFF reports?", "history"),
    ("Why did Livingroom Light 2 turn on?", None),
    ("Why is Livingroom Light 2 currently off?", None),
    ("Is Livingroom Light 2 on, and why did it turn off?", None),
    ("Compare Livingroom Light 1 and Livingroom Light 2", None),
    ("Explain the rule controlling Livingroom Light 2", None),
])
def test_exact_factual_question_contract_or_fall_through(question, expected):
    assert verified_factual_objective(question, ["Livingroom Light 2"]) == expected


def test_no_trusted_identity_or_multiple_subjects_never_fast_path():
    assert verified_factual_objective("Is Light 2 on?", ["Livingroom Light 2"]) is None
    assert verified_factual_objective("Is Livingroom Light 2 on?",
                                      ["Livingroom Light 2", "Livingroom Light 1"]) is None


def manifest():
    return [MCPTool(
        "hub_read_devices", "Bounded device read", {
            "type": "object", "properties": {
                "tool": {"type": "string", "enum": [
                    "hub_get_device", "hub_list_device_events"]},
                "args": {"type": "object", "properties": {
                    "deviceId": {"type": "string"},
                    "attribute": {"type": "string"},
                    "hoursBack": {"type": "integer", "maximum": 744},
                    "limit": {"type": "integer", "maximum": 500},
                }, "required": ["deviceId"], "additionalProperties": False},
            }, "required": ["tool", "args"], "additionalProperties": False,
        }, annotations={"readOnlyHint": True, "mutates": False})]


class FakeMCP:
    async def list_tools(self):
        return manifest()


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp = mcp
        self.calls = []

    async def execute(self, name, arguments, *, tool, record_evidence):
        assert name == "hub_read_devices" and record_evidence is False
        assert tool.name == "hub_read_devices"
        operation = arguments["tool"]
        self.calls.append(operation)
        if operation == "hub_get_device":
            data = {"id": "7828", "attributes": {
                "switch": "off", "networkStatus": "online",
                "password": "MUST_NEVER_APPEAR"}}
        else:
            data = {"deviceId": "7828", "events": [
                {"deviceId": "7828", "name": "switch", "value": "on",
                 "date": "2026-10-26T21:59:17+00:00",
                 "producedBy": {"id": "7790"}},
                {"deviceId": "7828", "name": "switch", "value": "off",
                 "date": "2026-10-27T03:15:32+00:00",
                 "producedBy": {"id": "7790"}},
            ]}
        raw = MCPToolResult(name, arguments, raw={}, text="DANGEROUS_RAW",
                            data=data, is_error=False)
        return ToolExecution(name=name, arguments=arguments,
                             effect=ToolEffect.READ, success=True,
                             elapsed_ms=1, content="DANGEROUS_RAW", result=raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("objective,expected_reads", [
    ("status", ["hub_get_device"]),
    ("history", ["hub_get_device", "hub_list_device_events"]),
])
async def test_factual_question_reads_sources_without_calling_model(objective, expected_reads):
    mcp = FakeMCP()
    executor = FakeExecutor(mcp)

    async def model_must_not_run(*args, **kwargs):
        raise AssertionError("AI planning is not needed for a verified factual question")

    result = await evaluate_v2_with_model(
        explicitly_authorised=True,
        question=("Is Livingroom Light 2 currently on or off?"
                  if objective == "status" else
                  "When did Livingroom Light 2 last turn on and off?"),
        chat=model_must_not_run, mcp=mcp, executor=executor,
        verified_entity_ids=("7828",), verified_device_label="Livingroom Light 2",
        bootstrap_device_context=True, bootstrap_source_identity=True,
        factual_objective=objective,
        enable_atomic_claim_validation=True,
    )
    assert executor.calls == expected_reads
    assert result.investigation.planning_diagnostics == []
    assert result.investigation.rounds == 0
    assert result.investigation.stopped_because == f"factual_{objective}_collected"
    assert result.answer.root_cause_verified is False
    assert "MUST_NEVER_APPEAR" not in json.dumps(result.to_dict())
    assert "DANGEROUS_RAW" not in json.dumps(result.to_dict())
    if objective == "status":
        assert "reported OFF" in result.report
        assert "Last ON" not in result.report
    else:
        assert "Last ON report" in result.report
        assert "Last OFF report" in result.report
        assert "7790" in result.report
        assert "not necessarily the controlling automation" in result.report
        assert "Historical source completeness is unverified" in result.report


def test_history_without_events_does_not_claim_no_activity():
    case = build_case_file("When did Livingroom Light 2 last turn off?", [])
    report, ids = factual_report(case, "history", "Livingroom Light 2")
    assert "does not prove no change occurred" in report
    assert ids == ()


def test_named_command_issuer_remains_eligible_for_config_read():
    arguments = {"tool": "hub_list_device_events",
                 "args": {"deviceId": "7103", "hoursBack": 168, "limit": 50}}
    receipt = project_read_receipt("hub_read_devices", arguments,
        MCPToolResult("hub_read_devices", arguments, raw={}, text="",
                      data={"deviceId": "7103", "events": [{
                          "deviceId": "7103", "name": "command-on",
                          "type": "command", "date": "2026-10-24T20:51:12Z",
                          "producedBy": {"id": "3103"}}]},
                      is_error=False), source_request_id="button")
    case = build_case_file("Why is Bedroom 3 Mesh offline?", [receipt])
    case.app_identities["3103"] = "Ikea Rodret Dimmer (room 3): button 2 pushed"
    schema = {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_get_app_config"]},
        "args": {"type": "object", "properties": {
            "appId": {"type": "string"},
        }, "required": ["appId"], "additionalProperties": False},
    }, "required": ["tool", "args"], "additionalProperties": False}
    tools = [MCPTool("hub_read_apps_code", "Read app settings", schema,
                     annotations={"readOnlyHint": True, "mutates": False})]
    proposals = source_configuration_proposals(tools, case)
    assert len(proposals) == 1
    assert proposals[0]["arguments"]["tool"] == "hub_get_app_config"
    assert proposals[0]["arguments"]["args"]["appId"] == "3103"
    unsafe = [MCPTool("hub_read_apps_code", "Mutating", schema,
                      annotations={"readOnlyHint": False, "mutates": True})]
    assert source_configuration_proposals(unsafe, case) == []


def test_endpoint_reports_new_objective_and_keeps_causal_path():
    source = (APP / "app.py").read_text()
    section = source.split("async def v2_test(", 1)[1].split(
        '@app.post("/api/chat")', 1)[0]
    assert "verified_factual_objective(" in section
    assert "factual_objective=factual_objective" in section
    assert "model_investigation_attempted" in section
    assert "planning_timeout_seconds=(35.0 if factual_objective is None else 15.0)" in section
