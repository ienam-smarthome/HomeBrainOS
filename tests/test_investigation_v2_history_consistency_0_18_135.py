"""0.18.135 — V2 history source drift, evidence projection and stalled model fallback.

All fake tools. Never touches an actual Hubitat device, source or provider.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.evidence import build_case_file
from investigation_v2.temporal_scope import explicit_incident_window
from investigation_v2.read_loop import run_read_only_investigation, compare_history_samples
from investigation_v2.source_identity import source_configuration_proposals
from investigation_v2.evaluate import evaluate_v2_with_model

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"tests/fixtures/investigation_v2_overnight.json"


def question():
    return "Investigate Livingroom Light 1 overnight 24–25 October 2026"


def window():
    return explicit_incident_window(question(),zone_name="Europe/London")


def event(name, clock, producer="4019"):
    return {"name":name, "type":"command","date":clock,
            "deviceId":"7805","producedBy":{"id":producer}}


E_OFF=event("command-off","2026-10-25T00:41:40+0100","4246")
E_LEVEL=event("command-setLevel","2026-10-25T00:49:52+0100","4019")
E_BUTTON=event("command-off","2026-10-25T01:09:41+0100","1251")


def receipt(rows, *, limit=150, source_request_id="snap1"):
    result=MCPToolResult("hub_read_devices",{},raw={},text="UNTRUSTED_TOKEN",
                         data={"deviceId":"7805","events":rows},is_error=False)
    return project_read_receipt(
        "hub_read_devices",
        {"tool":"hub_list_device_events","args":{"deviceId":"7805","limit":limit}},
        result,source_request_id=source_request_id,incident_window=window())


def test_second_independent_history_sample_can_recover_command_not_in_first():
    before=receipt([E_OFF,E_BUTTON],source_request_id="first")
    after=receipt([E_OFF,E_LEVEL,E_BUTTON],limit=500,source_request_id="second")
    # One HTTP response containing earlier events never proves completeness.
    assert before["details"]["requestedWindowReached"] is None
    case=build_case_file(question(),[before,after])
    assert len(case.records)==3
    assert [x.action for x in case.records]==["command-off","command-setLevel","command-off"]
    compare=compare_history_samples([before,after])
    assert compare["different"] is True
    assert compare["first_only_event_count"]==0
    assert compare["second_only_event_count"]==1
    assert compare["source_complete_verified"] is False
    assert "UNTRUSTED_TOKEN" not in json.dumps(compare)


def test_projection_drop_counters_distinguish_rejected_vs_off_window_raw_rows():
    bad=[
      event("command-off","2026-10-25T00:41:40+0100","4246"),
      event("command-off","2026-10-26T07:25:00+0000"),
      {"deviceId":"7805","name":"BAD SCRIPT!","date":"2026-10-25T00:46:00+0100"},
      {"deviceId":"7806","name":"command-off","date":"2026-10-25T00:40:00+0100"},
      {"deviceId":"malformed","name":"command-off","date":"2026-10-25T00:42:00+0100"},
    ]
    result=receipt(bad)
    cnt=result["details"]["sourceProjectionDropCounts"]
    assert cnt["outside_incident"]==1
    assert cnt["invalid_name_or_time"]==1
    assert cnt["wrong_target"]==1
    assert cnt["invalid_device_id"]==1
    assert cnt["retention_cap"]==0
    case=build_case_file(question(),[result])
    assert case.coverage[0].projection_drop_counts==cnt
    assert len(case.records)==1
    assert "BAD SCRIPT" not in json.dumps(case.to_dict())


def app_schema(*, mutates=False, operation=True):
    return MCPTool("hub_read_apps_code","Read apps",{
      "type":"object",
      "properties":{
         "tool":{"type":"string","enum":["hub_list_apps","hub_get_app_config"]
                                   if operation else ["hub_list_apps"]},
         "args":{"type":"object","properties":{"appId":{"type":"string"}},
                 "required":["appId"],"additionalProperties":False},
      },"required":["tool","args"],"additionalProperties":False,
    },annotations={"readOnlyHint":not mutates})


def test_attested_unlabelled_issuer_may_propose_one_read_only_config():
    original=json.loads(FIXTURE.read_text())
    case=build_case_file(original["question"],original["receipts"])
    case.app_identities={"1251":"button 1 pushed","4246":"Night Idle OFF TEST"}
    proposed=source_configuration_proposals([app_schema()],case)
    assert len(proposed)==1
    # Historical LMC source is attested by events, but absent from current
    # installed-app list. This is an ID for a READ, not execution permission.
    assert proposed[0]["arguments"]=={
        "tool":"hub_get_app_config","args":{"appId":"4019"},
    }
    assert source_configuration_proposals([app_schema(mutates=True)],case)==[]
    assert source_configuration_proposals([app_schema(operation=False)],case)==[]


class MCP:
    def __init__(self):
        self.calls=[]
    async def list_tools(self):
        return [MCPTool("hub_read_devices","Read only",{
          "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_device_events"]},
            "args":{"type":"object","properties":{
              "deviceId":{"type":"string"},"hoursBack":{"type":"integer"},
              "limit":{"type":"integer"}},
              "required":["deviceId"],"additionalProperties":False},
          },"required":["tool","args"]},annotations={"readOnlyHint":True})]


class Executor:
    def __init__(self,mcp):
        self.mcp=mcp
        self.calls=[]
    async def execute(self,name,args,*,tool,record_evidence):
        assert record_evidence is False
        self.calls.append(args)
        records=[E_OFF,E_BUTTON]
        if args["args"]["limit"]==500:
            records=[E_OFF,E_LEVEL,E_BUTTON]
        return ToolExecution(
          name=name, arguments=args,effect=ToolEffect.READ,
          success=True,elapsed_ms=1,content="NO_RAW",
          result=MCPToolResult(name,args,raw={},text="PRIVATE",
                               data={"deviceId":"7805","events":records},is_error=False))


@pytest.mark.asyncio
async def test_incident_history_snapshots_are_both_read_and_union_retained():
    mcp=MCP()
    executor=Executor(mcp)
    called=[]
    async def proposer(case,round_index):
        called.append(len(case.records))
        return {"hypotheses":[],"reads":[],"finish":True}
    result=await run_read_only_investigation(
       question=question(),mcp=mcp,executor=executor,propose=proposer,
       verified_entity_ids=["7805"],incident_window=window(),
       max_rounds=1,max_total_reads=3,
    )
    assert [r["args"]["limit"] for r in executor.calls]==[150,500]
    assert called==[3]
    assert result.history_comparison["different"] is True
    assert result.history_comparison["second_only_event_count"]==1
    assert len(result.case.records)==3
    assert result.stopped_because=="model_finished"


class PassiveMCP:
    async def list_tools(self):
        return []


class PassiveExecutor:
    def __init__(self,mcp):
        self.mcp=mcp
    async def execute(self,*args,**kwargs):
        raise AssertionError("No tool may be executed")


@pytest.mark.asyncio
async def test_stalled_planner_skips_all_followup_model_synthesis_and_repair():
    original=json.loads(FIXTURE.read_text())
    mcp=PassiveMCP()
    calls=[]
    async def slow_chat(messages,tools):
        calls.append(len(messages))
        await asyncio.sleep(2)
        raise AssertionError("model should be cancelled on budget")
    evaluated=await evaluate_v2_with_model(
        explicitly_authorised=True,question=original["question"],
        chat=slow_chat,mcp=mcp,executor=PassiveExecutor(mcp),
        verified_entity_ids=["7805"],initial_receipts=original["receipts"],
        planning_timeout_seconds=1.0,bootstrap_source_identity=False,
        max_rounds=1,enable_atomic_claim_validation=True,
        enable_evidence_narrative=True,
    )
    assert calls==[2]
    assert evaluated.investigation.stopped_because=="planning_timeout"
    assert evaluated.atomic_claim_review is None
    assert evaluated.narrative_audit is None
    assert "model_planner_unavailable_host_fallback" in evaluated.answer.validation_issues
    assert "00:49:52" in evaluated.answer.text
    assert evaluated.answer.root_cause_verified is False
    assert evaluated.report.startswith("**Finding**")


def test_stage_mismatch_is_not_source_event_loss():
    original=json.loads(FIXTURE.read_text())
    from investigation_v2.atomic_claims import review_atomic_claims
    case=build_case_file(original["question"],original["receipts"])
    before=len(case.records)
    actual=next(r for r in case.records if r.stage=="command_issued")
    wrong={"id":"myclaim","kind":"observation","record_id":actual.record_id,
           "expected":{"stage":"state_reported","action":actual.action,
                       "value":actual.value,"target_id":actual.target_id,
                       "producer_id":actual.producer_id,"timestamp_utc":actual.timestamp_utc,
                       "time_basis":actual.time_basis}}
    review=review_atomic_claims(case,[],[wrong])
    assert review.rejected[0].reason=="mismatched_stage"
    assert len(case.records)==before
