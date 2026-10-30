"""V2 incident-first retrieval, source honesty and readable report regressions.

All Hubitat and model dependencies are fakes. No live house controls are used.
"""
from __future__ import annotations
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.temporal_scope import explicit_incident_window
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.evidence import build_case_file
from investigation_v2.incident_retrieval import incident_first_proposals
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.forensic_metrics import forensic_metrics

FIXTURE=Path(__file__).parent/"fixtures"/"investigation_v2_overnight.json"


def window():
    return explicit_incident_window(
        "Why did Livingroom Light 1 remain on overnight on 24–25 October 2026?",
        zone_name="Europe/London")


def raw_result(rows):
    return MCPToolResult("hub_read_devices",{},raw={},text="SECRET NOT FOR THE MODEL",
                         data={"deviceId":"7805","events":rows},is_error=False)


def later_row(n):
    return {"name":"switch","value":"off",
            "date":f"2026-10-26T07:{n//60:02}:{n%60:02}+0000",
            "deviceId":"7805"}


def incident_rows():
    return [
      {"name":"command-on","type":"command","date":"2026-10-24T17:00:00+0000",
       "deviceId":"7805","producedBy":{"id":"7777"}},
      {"name":"command-off","type":"command","date":"2026-10-25T00:41:40+0100",
       "deviceId":"7805","producedBy":{"id":"4246"}},
      {"name":"command-setLevel","type":"command","date":"2026-10-25T00:49:52+0100",
       "deviceId":"7805","producedBy":{"id":"4019"}},
      {"name":"command-off","type":"command","date":"2026-10-25T01:09:41+0100",
       "deviceId":"7805","producedBy":{"id":"1251"}},
    ]


def test_historical_rows_survive_newer_events_before_page_limit():
    raw=[later_row(i) for i in range(175)]+incident_rows()
    receipt=project_read_receipt("hub_read_devices",
       {"tool":"hub_list_device_events","args":{"deviceId":"7805","limit":500}},
       raw_result(raw),source_request_id="hist",incident_window=window())
    names=[row["name"] for row in receipt["details"]["events"]]
    assert names==["command-on","command-off","command-setLevel","command-off"]
    assert receipt["details"]["sourceEventCount"]==179
    assert receipt["details"]["sourceOldestReturnedUtc"]=="2026-10-24T17:00:00+00:00"
    assert receipt["details"]["requestedWindowReached"] is True
    case=build_case_file("Test historical incident",[receipt])
    assert len(case.records)==4
    assert case.coverage[0].requested_window_reached is True
    assert all("2026-10-26" not in row.timestamp_utc for row in case.records)


def test_newer_only_page_is_not_mistaken_for_zero_historical_activity():
    receipt=project_read_receipt("hub_read_devices",
       {"tool":"hub_list_device_events","args":{"deviceId":"7805","limit":150}},
       raw_result([later_row(i) for i in range(150)]),
       source_request_id="recent",incident_window=window())
    case=build_case_file("Why overnight?",[receipt])
    assert case.records==[]
    assert case.coverage[0].succeeded is True
    assert case.coverage[0].returned_rows==0
    assert case.coverage[0].source_returned_rows==150
    assert case.coverage[0].requested_window_reached is False
    summary=format_investigation_report(case,[],"model_finished",window())
    assert "did not reach the incident start" in summary
    assert "does **not** prove that nothing happened" in summary
    assert forensic_metrics(case,window())["incident_start_coverage_unverified"] is True


def test_fixture_report_identifies_cross_controller_candidate_without_claiming_physical_state():
    obj=json.loads(FIXTURE.read_text())
    case=build_case_file(obj["question"],obj["receipts"])
    summary=format_investigation_report(case,[],"model_finished",window())
    assert "00:41:40" in summary
    assert "00:49:52" in summary
    assert "#4246" in summary and "#4019" in summary
    assert "Possible competing controllers" in summary
    assert "does not prove" in summary
    assert "What would settle it" in summary
    assert "2026-10-26T07:" not in summary
    assert len([x for x in case.records if x.stage=="command_issued"])==6
    check=forensic_metrics(case,window())
    assert check["incident_command_records"]==6
    assert check["causal_accuracy_verified"] is False


def manifest(*, require_attribute=False, mutation=False):
    attrs={"readOnlyHint":not mutation}
    args_props={"deviceId":{"type":"string"},"hoursBack":{"type":"integer"},
                "limit":{"type":"integer"},"attribute":{"type":"string"}}
    return [MCPTool("hub_read_devices","read only",{
      "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_list_device_events"]},
        "args":{"type":"object","properties":args_props,
                "required":["deviceId","attribute"] if require_attribute else ["deviceId"],
                "additionalProperties":False}},
        "required":["tool","args"],"additionalProperties":False,
      },annotations=attrs)]


def test_seed_uses_authoritative_manifest_and_never_grants_write():
    yes=incident_first_proposals(manifest(require_attribute=True),["7805"],window())
    assert yes[0]["arguments"]["args"]["attribute"]=="switch"
    assert yes[0]["arguments"]["args"]["deviceId"]=="7805"
    no=incident_first_proposals(manifest(mutation=True),["7805"],window())
    assert no==[]
    assert incident_first_proposals(manifest(),["not-valid"],window())==[]


class MCP:
    async def list_tools(self):
        return manifest()


class Executor:
    def __init__(self,mcp):
        self.mcp=mcp
        self.calls=[]
    async def execute(self,name,args,*,tool,record_evidence):
        self.calls.append(deepcopy(args))
        limit=args["args"]["limit"]
        # The first page is crowded with recent rows; the larger one reaches
        # the verified source incident, without trusting the model.
        rows=[later_row(i) for i in range(150)]
        if limit>=500:
            rows+=incident_rows()
        res=raw_result(rows)
        return ToolExecution(name=name,arguments=args,effect=ToolEffect.READ,
            success=True,elapsed_ms=2,content="IGNORE SECRET IN RESULT",result=res)


@pytest.mark.asyncio
async def test_incident_first_reads_then_model_sees_historical_evidence():
    mcp=MCP()
    ex=Executor(mcp)
    observed=[]
    async def propose(case,round_index):
        observed.append((round_index,len(case.records)))
        return {"hypotheses":[],"reads":[],"finish":True}
    result=await run_read_only_investigation(
      question="Investigate overnight 24–25 October 2026",
      mcp=mcp,executor=ex,propose=propose,
      verified_entity_ids=["7805"],
      max_rounds=1,max_total_reads=3,incident_window=window())
    assert [call["args"]["limit"] for call in ex.calls]==[150,500]
    assert result.executed_reads==2
    assert observed==[(0,4)]
    assert any(row.action=="command-off" for row in result.case.records)
    assert result.stopped_because=="model_finished"
    assert result.to_dict()["production_answer_used"] is False
    assert "SECRET" not in json.dumps(result.to_dict())

