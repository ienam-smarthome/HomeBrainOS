"""V2 0.18.138: generic short-label, relative-window and ON-time regressions.

No live hub, user tokens or device mutations. Every synthetic MCP response is
read-only and every resulting duration is based on switch state observations.
"""
from __future__ import annotations

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
from investigation_v2.test_service import resolve_verified_device_subjects
from investigation_v2.temporal_scope import explicit_incident_window
from investigation_v2.read_loop import scope_model_reads_to_verified_target
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.evidence import build_case_file
from investigation_v2.state_duration import is_state_duration_request, format_state_duration_report
from investigation_v2.evaluate import evaluate_v2_with_model

NOW=datetime(2026,10,26,12,14,55,tzinfo=timezone.utc)
QUESTION="How long has the TV been on today? Show ON/OFF sessions and total."
INVENTORY=[
    {"id":"4221","label":"TV","name":"TV"},
    {"id":"6923","label":"Block Media-Google-TV-Streamer"},
    {"id":"7805","label":"Livingroom Light 1"},
]


def test_unique_short_tv_noun_phrase_is_resolved_from_live_inventory():
    ids,labels,source=resolve_verified_device_subjects(QUESTION, INVENTORY)
    assert ids==("4221",)
    assert labels[0]["label"]=="TV"
    assert source=="question"
    with pytest.raises(ValueError):
        resolve_verified_device_subjects("Investigate TV playback",INVENTORY)
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_verified_device_subjects(QUESTION,INVENTORY+[{"id":"4004","label":"TV"}])


def test_today_scope_is_local_midnight_to_request_instant():
    w=explicit_incident_window(QUESTION,zone_name="Europe/London",now=NOW)
    assert w.start_utc=="2026-10-26T00:00:00+00:00"
    assert w.end_utc=="2026-10-26T12:14:55+00:00"
    assert w.contains("2026-10-26T09:37:35Z")
    assert not w.contains("2026-10-25T23:59:59Z")
    assert w.interpretation.startswith("today:")


def test_yesterday_respects_autumn_dst_25_hour_day():
    now=datetime(2026,10,26,11,tzinfo=timezone.utc)
    w=explicit_incident_window("How long was the lamp on yesterday?",
                               zone_name="Europe/London",now=now)
    assert w.start_utc=="2026-10-24T23:00:00+00:00"
    assert w.end_utc=="2026-10-26T00:00:00+00:00"
    assert (datetime.fromisoformat(w.end_utc)-datetime.fromisoformat(w.start_utc)).total_seconds()==25*3600


def test_only_time_queries_take_arithmetic_path():
    window=explicit_incident_window(QUESTION,zone_name="Europe/London",now=NOW)
    assert is_state_duration_request(QUESTION,window)
    assert is_state_duration_request("Total ON-time for the hallway light today",window)
    assert not is_state_duration_request("Why did the TV stay on today?",window)
    assert not is_state_duration_request("How long has the TV been on?",None)


def proposal(operation, args):
    return {"tool":"hub_read_devices","arguments":{"tool":operation,"args":args},
            "discriminator":"Read state history","information_gain":"Establish verified state"}


def test_device_id_autofill_requires_exactly_one_verified_id_and_no_override():
    missing=[proposal("hub_list_device_events",{"hoursBack":24,"limit":200})]
    completed=scope_model_reads_to_verified_target(missing,["4221"])
    assert completed[0]["arguments"]["args"]["deviceId"]=="4221"
    assert "deviceId" not in missing[0]["arguments"]["args"]
    assert scope_model_reads_to_verified_target(missing,["4221","7805"])==missing
    conflicting=[proposal("hub_get_device",{"deviceId":"9999"})]
    assert scope_model_reads_to_verified_target(conflicting,["4221"])==conflicting
    unrelated=[proposal("hub_get_other",{})]
    assert scope_model_reads_to_verified_target(unrelated,["4221"])==unrelated


def source(rows):
    return MCPToolResult("hub_read_devices",{},raw={},text="SECRET_TOKEN",
                         data={"deviceId":"4221","events":rows},is_error=False)


def switch(value,clock):
    return {"name":"switch","value":value,"date":clock,"deviceId":"4221"}


ROWS=[
    switch("on","2026-10-26T09:37:35+0000"),
    switch("off","2026-10-26T10:08:59+0000"),
    switch("on","2026-10-26T10:31:42+0000"),
    switch("off","2026-10-26T11:14:16+0000"),
    switch("on","2026-10-26T11:15:19+0000"),
    {"name":"power","value":5,"date":"2026-10-26T12:00:00+0000","deviceId":"4221"},
]


def build(rows=ROWS):
    w=explicit_incident_window(QUESTION,zone_name="Europe/London",now=NOW)
    r=project_read_receipt("hub_read_devices",
                           {"tool":"hub_list_device_events",
                            "args":{"deviceId":"4221","limit":150}},
                           source(rows),source_request_id="fixture",incident_window=w)
    assert r["success"] is True
    return build_case_file(QUESTION,[r]),w


def test_three_reported_sessions_are_computed_without_model_derived_times():
    case,w=build()
    answer,ids=format_state_duration_report(case,w,device_label="TV")
    assert "2 h 13 min 34 sec" in answer
    assert "133.6 minutes" in answer
    assert "31 min 24 sec" in answer
    assert "42 min 34 sec" in answer
    assert "59 min 36 sec" in answer
    assert "(as-of; unverified current state)" in answer
    assert "not independently proven complete" in answer
    assert "actual TV viewing" in answer
    assert len(ids)==5
    assert "SECRET_TOKEN" not in answer


def test_no_switch_transition_cannot_be_sold_as_zero_duration():
    case,w=build([{"name":"power","value":5,"date":"2026-10-26T11:00:00Z","deviceId":"4221"}])
    text,ids=format_state_duration_report(case,w)
    assert "duration cannot be calculated" in text
    assert "0 min 0 sec" not in text
    assert ids==()


def test_unmatched_off_does_not_create_fabricated_pre_midnight_session():
    case,w=build([switch("off","2026-10-26T09:00:00Z"),
                  switch("on","2026-10-26T10:00:00Z"),
                  switch("off","2026-10-26T10:30:00Z")])
    text,_=format_state_duration_report(case,w)
    assert "30 min 0 sec" in text
    assert "earlier ON-time remains unknown" in text


class MCP:
    async def list_tools(self):
        return [MCPTool("hub_read_devices","Read event history",{
            "type":"object",
            "properties":{
                "tool":{"type":"string","enum":["hub_list_device_events"]},
                "args":{"type":"object","properties":{
                    "deviceId":{"type":"string"},
                    "hoursBack":{"type":"integer"},
                    "limit":{"type":"integer"}},
                    "required":["deviceId"],"additionalProperties":False}},
            "required":["tool","args"],"additionalProperties":False,
        },annotations={"readOnlyHint":True})]


class Executor:
    def __init__(self,mcp):
        self.mcp=mcp
        self.calls=[]
    async def execute(self,name,args,*,tool,record_evidence):
        assert record_evidence is False
        assert tool.annotations["readOnlyHint"] is True
        assert args["args"]["deviceId"]=="4221"
        self.calls.append(args)
        return ToolExecution(
            name=name,arguments=args,effect=ToolEffect.READ,success=True,
            elapsed_ms=1,content="",result=source(ROWS),
        )


@pytest.mark.asyncio
async def test_v2_answers_duration_without_llm_planning_or_unverified_device_control():
    mcp=MCP()
    ex=Executor(mcp)
    async def forbidden_chat(messages,tools):
        raise AssertionError("No LLM planning or arithmetic was needed for a state duration query")
    w=explicit_incident_window(QUESTION,zone_name="Europe/London",now=NOW)
    result=await evaluate_v2_with_model(
        explicitly_authorised=True,question=QUESTION,
        chat=forbidden_chat,mcp=mcp,executor=ex,
        verified_entity_ids=["4221"],verified_device_label="TV",
        incident_window=w,max_total_reads=8,
        enable_atomic_claim_validation=True,enable_evidence_narrative=True,
    )
    assert len(ex.calls)==2
    assert [x["args"]["limit"] for x in ex.calls]==[150,500]
    assert result.investigation.rounds==0
    assert result.investigation.stopped_because=="state_duration_history_collected"
    assert "2 h 13 min 34 sec" in result.report
    assert result.answer.root_cause_verified is False
    assert result.investigation.history_comparison["compared"] is True
    assert result.atomic_claim_review is None
