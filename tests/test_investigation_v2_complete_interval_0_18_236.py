"""0.18.236: generic complete-cycle evidence and investigation regressions.

The user's test requested the most recent complete heat ON/OFF cycle, but
the model read 10 events containing a later thermostat mode OFF and no
matching heating-start/end states. It fell back to a battery and command
count after a 20s whole-device-list timeout and wrong rule-engine reads.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool
from investigation_v2.native_interval_coverage import (
    complete_interval_coverage, interval_reasoning_evidence,
    incomplete_interval_answer, requires_complete_interval)
from investigation_v2.native_entity_lookup import choose_device
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP,FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import native

QUESTION=("Investigate the most recent complete heating ON/OFF cycle. "
          "Explain why heating started, which room or radiator needed heat, "
          "why demand ended, and whether the thermostat behaved correctly.")

def event(name,date,value=None,who=None):
    e={"name":name,"date":date}
    if value is not None:
        e["value"]=value
    if who is not None:
        e["producedBy"]=who
    return e

DEVICE={"deviceId":"4382","name":"Thermostat"}
APP3970={"appId":"3970","name":"00 Smart Thermostat Scheduler"}
APP2710={"appId":"2710","name":"Heating: Thermostat OFF"}

def incomplete_events():
    return [
        event("thermostatMode","2026-10-29T22:30:01.844+00:00",
              "off",DEVICE),
        event("command-setThermostatMode","2026-10-29T22:30:01.589+00:00",
              who=APP2710),
        event("temperature","2026-10-29T15:23:29.087+00:00","21.0",DEVICE),
        event("temperature","2026-10-29T15:23:13.618+00:00","22.0",DEVICE),
        event("temperature","2026-10-29T15:20:08.080+00:00","21.0",DEVICE),
        event("temperature","2026-10-29T15:19:21.584+00:00","22.0",DEVICE),
        event("temperature","2026-10-29T15:19:06.166+00:00","21.0",DEVICE),
        event("temperature","2026-10-29T15:18:35.180+00:00","22.0",DEVICE),
        event("temperature","2026-10-29T15:18:19.710+00:00","21.0",DEVICE),
        event("temperature","2026-10-29T15:15:29.557+00:00","22.0",DEVICE),
    ]

def complete_events():
    return incomplete_events()+[
        event("thermostatOperatingState",
              "2026-10-29T14:48:36.785+00:00","heating",DEVICE),
        event("thermostatOperatingState",
              "2026-10-29T14:54:36.587+00:00","idle",DEVICE),
        event("heatingSetpoint",
              "2026-10-29T14:54:18.037+00:00","12.0",APP3970),
        event("heatingSetpoint",
              "2026-10-29T14:48:18.301+00:00","26.0",APP3970),
    ]

def witnessed(events):
    return [{"read":7,"operation":"hub_list_device_events",
             "read_filters":{"deviceId":"4382"},
             "source_data":{
                 "events":events,
                 "returned_event_rows":len(events),
                 "oldest_returned":min(e["date"] for e in events),
                 "newest_returned":max(e["date"] for e in events),
             }}]


def test_cannot_treat_evening_mode_off_as_a_completed_heating_cycle():
    c=complete_interval_coverage(QUESTION,witnessed(incomplete_events()),["4382"])
    assert c["status"]=="complete_interval_not_established"
    assert c["complete_interval_count"]==0
    text=incomplete_interval_answer(c)
    assert "Unable to verify a complete cycle" in text
    assert "battery" not in text
    assert "22:30" in text  # This is a returned history boundary, not the cycle cause.
    assert complete_interval_coverage("Is the battery healthy?",
                                      witnessed(incomplete_events()),["4382"]) is None
    assert requires_complete_interval(QUESTION)
    assert not requires_complete_interval("Run a comprehensive device health audit")


def test_complete_interval_pair_required_and_late_schedule_off_ignored():
    c=complete_interval_coverage(QUESTION,witnessed(complete_events()),["4382"])
    assert c["status"]=="complete_source_reported_interval_observed"
    assert c["complete_interval_count"]==1
    interval=c["most_recent_complete_interval"]
    assert interval["attribute"]=="thermostatOperatingState"
    assert interval["start"]["value"]=="heating"
    assert interval["end"]["value"]=="idle"
    assert interval["duration_seconds"]==360
    packet=interval_reasoning_evidence(c,witnessed(complete_events()))
    assert packet["incident_answer_evidence_present"] is True
    assert packet["material_event_count"]>=2
    assert {x["value"] for x in packet["material_event_examples"]
            if x["name"]=="thermostatOperatingState"}=={"heating","idle"}
    assert not any(x["date"].startswith("2026-10-29T22:30")
                   for x in packet["material_event_examples"])


def test_acronym_group_returns_verified_candidates_without_guessing_a_target():
    identities=[
        {"id":"41","label":"Bedroom 1 TRV"},
        {"id":"42","label":"Bedroom 2 TRV"},
        {"id":"43","label":"Livingroom TRV"},
        {"id":"44","label":"Smart Rad TRV W600"},
        {"id":"60","label":"Bedroom 3 Mesh"},
    ]
    result=choose_device("TRV",identities)
    assert result["status"]=="candidate_group"
    assert {x["id"] for x in result["matches"]}=={"41","42","43","44"}
    assert result["group_membership_verified"] is False
    assert choose_device("Mesh",identities)["status"]=="not_found"


READ=MCPTool("hub_read_devices","Read devices and history",
    {"type":"object","properties":{
        "tool":{"type":"string","enum":[
            "hub_list_devices","hub_get_device","hub_list_device_events"]},
        "args":{"type":"object","additionalProperties":True}},
     "required":["tool","args"]},
    annotations={"readOnlyHint":True})

@pytest.mark.asyncio
async def test_live_replay_cannot_publish_battery_as_complete_cycle():
    mcp=FakeMCP([READ])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"id":"4382","label":"Thermostat","attributes":[
            {"name":"battery","value":100},
            {"name":"healthStatus","value":"online"}]},
        {"events":incomplete_events()},
    ])
    turn=0
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:
            return {"tool_calls":[native("homebrain_find_device",
                 {"name":"Thermostat"})]}
        if turn==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_devices","args":{}})]}
        if turn==3:
            assert "bounded_identity_candidates_available" in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device","args":{"deviceId":"4382"}})]}
        if turn==4:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events","args":{"deviceId":"4382"}})]}
        if turn==5:
            assert "requested_complete_interval_coverage" in messages[-1]["content"]
            assert "complete_interval_not_established" in messages[-1]["content"]
            return {"content":"One schedule switched the thermostat off."}
        if turn==6:
            assert "COMPLETE operating interval" in messages[-1]["content"]
            return {"content":"The history cannot prove a full cycle."}
        raise AssertionError("Unnecessary model call after missing interval verified")
    result=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=6,max_reads=4,enable_model_reasoned_assessment=True)
    d=result["native_diagnostics"]
    assert [x[1]["tool"] for x in executor.calls]==[
        "hub_get_device","hub_list_device_events"]
    assert d["interval_coverage_challenge_used"] is True
    assert d["requested_complete_interval_coverage"]["complete_interval_count"]==0
    assert d["final_synthesis_skipped_reason"]=="explicit_complete_cycle_not_established"
    assert d["concise_answer_source"]=="requested_complete_interval_gap"
    assert "Unable to verify a complete cycle" in result["answer"]["text"]
    assert "100%" not in result["answer"]["text"]
    assert d["source_grounded_brief_published"] is False


@pytest.mark.asyncio
async def test_complete_cycle_can_reuse_native_model_cited_reasoning_without_date():
    mcp=FakeMCP([READ])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"events":complete_events()}])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[native("homebrain_find_device",
                {"name":"Thermostat"})]}
        if step==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events","args":{"deviceId":"4382"}})]}
        if step==3:
            assert "complete_source_reported_interval_observed" in messages[-1]["content"]
            return {"content":json.dumps({
                "hypothesis":"The thermostat reported heating and later idle after the scheduler lowered its heating target.",
                "confidence":"possible",
                "supporting_events":[
                    {"read":1,"name":"thermostatOperatingState",
                     "date":"2026-10-29T14:48:36.785+00:00"},
                    {"read":1,"name":"thermostatOperatingState",
                     "date":"2026-10-29T14:54:36.587+00:00"}],
                "alternative":"A different source could have modified the demand.",
                "next_check":"Read the scheduler decisions and independently verified room temperature history.",
            })}
        raise AssertionError("Unexpected extra model pass")
    result=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=4,max_reads=3,enable_model_reasoned_assessment=True)
    d=result["native_diagnostics"]
    assert step==3
    assert d["model_reasoned_assessment"]["accepted"] is True
    assert d["concise_answer_source"]=="model_cited_incident_assessment"
    assert "scheduler lowered" in result["answer"]["text"]


RULES=MCPTool("hub_read_rules","Read rules",
    {"type":"object","properties":{
        "tool":{"type":"string","enum":["hub_list_rules","hub_get_custom_rule"]},
        "args":{"type":"object","additionalProperties":True}},
     "required":["tool","args"]},annotations={"readOnlyHint":True})

@pytest.mark.asyncio
async def test_verified_rule_machine_type_blocks_custom_rule_inspection():
    mcp=FakeMCP([RULES])
    executor=FakeExecutor(mcp,[{"rules":[
        {"id":2710,"label":"Heating: Thermostat OFF","type":"Rule-5.1"}]}])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[native("hub_read_rules",{
                "tool":"hub_list_rules","args":{}})]}
        if step==2:
            return {"tool_calls":[native("hub_read_rules",{
                "tool":"hub_get_custom_rule","args":{"ruleId":2710}})]}
        return {"content":"No matching custom-rule read was available."}
    result=await run_native_read_agent(
        question="Explain how the heating Rule Machine automation operates",
        chat=model,mcp=mcp,executor=executor,max_rounds=3,max_reads=3)
    assert [x[1]["tool"] for x in executor.calls]==["hub_list_rules"]
    assert any(f["code"]=="wrong_rule_engine_type"
               for f in result["native_diagnostics"]["failures"])
