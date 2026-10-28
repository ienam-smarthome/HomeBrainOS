"""v0.18.149: V2 zero-read failure with generic live gateway schemas.

All operations are synthetic. No live Hubitat IO or provider model calls.
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
from investigation_v2.device_context import device_context_proposals
from investigation_v2.evidence import build_case_file
from investigation_v2.operation_discovery import discover_device_operations
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.receipt_projection import project_read_receipt


def generic_gateway(explicit_enum=None, *, write=False):
    properties = {
        "tool": {"type": "string"},
        "args": {"type": "object"},
    }
    if explicit_enum is not None:
        properties["tool"]["enum"] = explicit_enum
    return MCPTool(
        "hub_manage_devices" if write else "hub_read_devices",
        "Current-session live device gateway",
        {"type": "object", "properties": properties,
         "required": ["tool", "args"], "additionalProperties": False},
        annotations={"readOnlyHint": not write, "mutates": write},
    )


def discovery_tool():
    return MCPTool("hub_search_tools", "Read live capability mapping",
        {"type": "object",
         "properties": {"query": {"type": "string"}},
         "required": ["query"], "additionalProperties": False},
        annotations={"readOnlyHint": True})


class FakeMCP:
    def __init__(self, tools):
        self.tools = tools
    async def list_tools(self):
        return self.tools


class FakeExecutor:
    def __init__(self, mcp, *, multi_member=True, fail_search=False):
        self.mcp = mcp
        self.calls = []
        self.multi_member = multi_member
        self.fail_search = fail_search

    async def execute(self, name, arguments, *, tool, record_evidence):
        assert record_evidence is False
        self.calls.append((name, arguments))
        assert tool.name == name
        if name == "hub_search_tools":
            operation = arguments["query"]
            assert operation in ("hub_get_device", "hub_list_device_events")
            results = [{"tool": operation, "gateway": "hub_read_devices"}]
            if self.multi_member:
                results.append({"tool": operation, "gateway": "hub_manage_devices"})
            payload = {"results": results}
            if self.fail_search:
                payload = {"results": [{"tool": "hub_delete_device",
                                         "gateway": "hub_manage_devices"}]}
            response = MCPToolResult(name, arguments, raw={}, text="",
                                     data=payload, is_error=False)
        elif name == "hub_read_devices":
            assert arguments["args"]["deviceId"] == "7103"
            op = arguments["tool"]
            if op == "hub_get_device":
                payload = {"id": "7103", "attributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                    "switch": "off", "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
                    "brokerPassword": "SECRET_NOT_FOR_MODEL"}}
            elif op == "hub_list_device_events":
                assert arguments["args"]["hoursBack"] >= 340
                payload = {"deviceId": "7103", "events": [
                    {"deviceId": "7103", "name": "switch", "value": "off",
                     "date": "2026-10-12T00:30:01+00:00"}]}
            else:
                raise AssertionError("Unexpected operation")
            response = MCPToolResult(name, arguments, raw={}, text="",
                                     data=payload, is_error=False)
        else:
            raise AssertionError("Unknown tool requested")
        return ToolExecution(name=name, arguments=arguments, effect=ToolEffect.READ,
                             success=True, elapsed_ms=1, content="", result=response)


async def finished_model(case, round_index):
    assert round_index == 0
    return {"hypotheses": [], "reads": [], "finish": True}


@pytest.mark.asyncio
async def test_generic_manifest_discovery_yields_status_and_history_without_model():
    mcp = FakeMCP([generic_gateway(), discovery_tool()])
    executor = FakeExecutor(mcp)
    result = await run_read_only_investigation(
        question="Investigate Bedroom 3 Mesh",
        mcp=mcp, executor=executor, propose=finished_model,
        verified_entity_ids=("7103",), bootstrap_device_context=True,
        bootstrap_source_identity=False, max_rounds=1,
    )
    assert [n for n, _ in executor.calls] == [
        "hub_search_tools", "hub_search_tools", "hub_read_devices",
        "hub_read_devices", "hub_read_devices"]
    assert executor.calls[-1][1]["tool"] == "hub_list_device_events"
    assert "attribute" not in executor.calls[-1][1]["args"]
    assert result.executed_reads == 3
    assert len(result.case.device_snapshots) == 1
    assert len(result.case.records) >= 1
    assert "SECRET_NOT_FOR_MODEL" not in json.dumps(result.to_dict())
    assert sum(x.get("status") == "verified_live_discovery"
               for x in result.bootstrap_diagnostics) == 2
    assert sum(x.get("status") == "read_attempt_completed"
               for x in result.bootstrap_diagnostics) == 3


@pytest.mark.asyncio
async def test_unavailable_search_reports_real_reason_not_empty_success():
    mcp = FakeMCP([generic_gateway()])
    executor = FakeExecutor(mcp)
    result = await run_read_only_investigation(
        question="Investigate Bedroom 3 Mesh",
        mcp=mcp, executor=executor, propose=finished_model,
        verified_entity_ids=("7103",), bootstrap_device_context=True,
        bootstrap_source_identity=False, max_rounds=1,
    )
    assert result.executed_reads == 0
    assert not executor.calls
    assert any(x.get("reason") == "search_tool_unavailable"
               for x in result.bootstrap_diagnostics)
    assert any(x.get("reason") == "no_authorised_live_operation_or_schema"
               for x in result.bootstrap_diagnostics)


@pytest.mark.asyncio
async def test_unrelated_or_write_discovery_never_grants_read_permission():
    mcp = FakeMCP([generic_gateway(), discovery_tool()])
    executor = FakeExecutor(mcp, fail_search=True)
    result = await run_read_only_investigation(
        question="Investigate Bedroom 3 Mesh",
        mcp=mcp, executor=executor, propose=finished_model,
        verified_entity_ids=("7103",), bootstrap_device_context=True,
        bootstrap_source_identity=False, max_rounds=1,
    )
    assert result.executed_reads == 0
    assert all(name == "hub_search_tools" for name, _ in executor.calls)
    assert any(x.get("reason") == "search_no_exact_mapping"
               for x in result.bootstrap_diagnostics)


@pytest.mark.asyncio
async def test_explicit_live_enum_denial_cannot_be_overridden_by_search():
    mcp = FakeMCP([generic_gateway(["hub_list_devices"]), discovery_tool()])
    executor = FakeExecutor(mcp)
    discovered, detail = await discover_device_operations(
        await mcp.list_tools(), executor)
    assert discovered == {}
    assert executor.calls == []
    assert all(x["reason"] == "operation_not_in_live_enum" for x in detail)


@pytest.mark.asyncio
async def test_read_gateway_missing_is_not_assumed_from_manage_gateway():
    mcp = FakeMCP([generic_gateway(write=True), discovery_tool()])
    executor = FakeExecutor(mcp)
    result = await run_read_only_investigation(
        question="Investigate Bedroom 3 Mesh",
        mcp=mcp, executor=executor, propose=finished_model,
        verified_entity_ids=("7103",), bootstrap_device_context=True,
        max_rounds=1, bootstrap_source_identity=False,
    )
    assert result.executed_reads == 0
    assert executor.calls == []
    assert result.bootstrap_diagnostics[0]["reason"] == "read_gateway_unavailable"


def test_only_trusted_hubitat_bst_clock_can_expand_history_window():
    from investigation_v2.device_context import _last_reported_age_hours
    from datetime import datetime, timezone
    if datetime.now(timezone.utc).year != 2026:
        pytest.skip("this fixture exercises the October 2026 outage")
    case = build_case_file("Why?", [project_read_receipt(
        "hub_read_devices", {"tool": "hub_get_device", "args": {"deviceId": "7103"}},
        MCPToolResult("hub_read_devices", {}, raw={}, text="",
                      data={"id": "7103", "attributes": {
                          "switch": "off",
                          "lastSeen": "Mon Oct 12 01:30:01 BST 2026"}},
                      is_error=False),
        source_request_id="bst",
    )])
    assert _last_reported_age_hours(case, "7103") is not None
    assert _last_reported_age_hours(case, "7103") >= 300
