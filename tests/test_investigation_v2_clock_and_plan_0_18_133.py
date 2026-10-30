"""Adversarial v0.18.133 model clock and safe read-plan diagnostics.

No actual Hubitat or cloud model access; fixture is a trusted host receipt.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import sys

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.hypothesis_temporal_integrity import hypothesis_clock_issues
from investigation_v2.temporal_scope import explicit_incident_window
from investigation_v2.evidence import build_case_file
from investigation_v2.read_loop import _hypotheses,run_read_only_investigation
from investigation_v2.model_adapter import V2ModelProposer
from mcp_client import MCPTool
from tool_registry import ToolEffect


def fixture():
    return json.loads((Path(__file__).parent/"fixtures"/"investigation_v2_overnight.json").read_text())


def window():
    return explicit_incident_window("Overnight 24–25 October 2026",zone_name="Europe/London")


def case():
    data=fixture()
    return build_case_file(data["question"],data["receipts"])


def selected():
    records=case().records
    off=next(row for row in records if row.action=="command-off"
             and "00:41:40" in row.timestamp_original)
    later=next(row for row in records if row.action=="command-off"
               and "01:09:41" in row.timestamp_original)
    return off.record_id,later.record_id


def proposal(text,record_ids):
    return [{"id":"h1","explanation":text,
             "supporting_record_ids":list(record_ids),
             "conflicting_record_ids":[],
             "missing_discriminator":"Check independent delivery reports."}]


def test_model_free_text_cannot_silently_shift_bst_events_by_one_hour():
    ca=case()
    links=selected()
    bad="OFF commands at 23:41 and 00:09 never physically executed"
    assert hypothesis_clock_issues(bad,ca,links,window())==(
        "unqualified_hypothesis_clock",)
    assert _hypotheses(proposal(bad,links),ca,{},window())=={}


def test_correct_explicit_local_bst_times_are_allowed_when_cited():
    ca=case()
    links=selected()
    good="OFF commands at 00:41 BST and 01:09 BST may have failed."
    assert hypothesis_clock_issues(good,ca,links,window())==()
    assert list(_hypotheses(proposal(good,links),ca,{},window()))==["h1"]


def test_explicit_utc_conversion_is_allowed_only_with_matching_records():
    ca=case()
    links=selected()
    assert hypothesis_clock_issues("Off at 23:41 UTC",ca,links,window())==()
    assert hypothesis_clock_issues("Off at 00:41 GMT",ca,links,window())==(
        "hypothesis_clock_not_linked_to_record",)
    assert hypothesis_clock_issues("Off at 00:41 BST and 22:00 UTC",ca,links,window())==(
        "hypothesis_clock_not_linked_to_record",)
    assert hypothesis_clock_issues("Possible automation interference",ca,links,window())==()


@pytest.mark.asyncio
async def test_planner_exposes_nested_required_fields_and_rejects_native_tool_calls():
    schema={"type":"object","required":["tool","args"],"properties":{
        "tool":{"type":"string","enum":["hub_get_app_config"]},
        "args":{"type":"object","required":["appId"],"additionalProperties":False,
                "properties":{"appId":{"type":"string"},"mode":{"type":"string"}}}
    },"additionalProperties":False}
    messages=[]
    async def chat(msgs,tools):
        messages.append(msgs)
        return {"content":json.dumps({"hypotheses":[],"reads":[],"finish":True})}
    tool=MCPTool("hub_read_apps_code","READ",{**schema},annotations={"readOnlyHint":True})
    proposer=V2ModelProposer(chat,[tool],verified_entity_ids=["7805"],incident_window=window())
    await proposer(case(),0)
    prompt=json.loads(messages[0][1]["content"])
    description=next(x for x in prompt["available_tools"] if x["name"]=="hub_read_apps_code")
    assert description["properties"]["args"]["required"]==["appId"]
    assert description["properties"]["args"]["additionalProperties"] is False
    # The model cites canonical evidence IDs; the HOST validates exact
    # local/UTC conversion instead of making a slow model re-verify prose.
    assert "reference evidence IDs" in messages[0][0]["content"]
    assert "exact UTC/local times" in messages[0][0]["content"]


class MCP:
    async def list_tools(self):
        return [
            MCPTool("hub_manage_devices","Mutating",{"type":"object","properties":{
                "tool":{"type":"string","enum":["hub_call_device_command"]}}},
                annotations={"readOnlyHint":False}),
        ]


class Executor:
    def __init__(self,mcp):
        self.mcp=mcp
        self.calls=[]
    async def execute(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        raise AssertionError("No write gateway may run")


@pytest.mark.asyncio
async def test_invalid_read_claim_not_relabelled_as_completed_investigation():
    mcp=MCP()
    executor=Executor(mcp)
    async def proposer(_case,_round):
        return {"hypotheses":[],"reads":[{
            "tool":"hub_manage_devices",
            "arguments":{"tool":"hub_call_device_command","args":{"deviceId":"7805"}},
            "discriminator":"Try a forbidden write","information_gain":"Unsafe",
            "hypothesis_ids":[],
        }],"finish":True}
    result=await run_read_only_investigation(
        question="Inspect light safely",mcp=mcp,executor=executor,
        propose=proposer,verified_entity_ids=["7805"],max_rounds=1)
    assert result.stopped_because=="no_approved_discriminating_reads"
    assert "management/write gateways" in result.rejected_proposals[0]
    assert executor.calls==[]

