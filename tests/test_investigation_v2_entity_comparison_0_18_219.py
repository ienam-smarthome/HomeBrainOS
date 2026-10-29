"""0.18.219: every member of a verified multi-entity READ is answerable.

Regression for 29 Oct V1 vs V2: V2 had 6/6 device reads and both OFF
lights but published first 9/15 attribute facts, dropping second light.
No group keyword routing, room membership inference or Hubitat writes.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.native_entity_group_answer import entity_group_answer
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP,FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import DEVICE,native,NAME

def _lookup(label="Bathroom"):
    return [{"status":"candidate_group","query":label,"count":6,
             "candidate_ids":["1079","7746","7754","7818","7821","7851"]}]

def _source(ident, label, caps, values, read):
    return {
        "read":read, "operation":"hub_get_device",
        "read_filters":{"deviceId":ident},
        "source_data":{
            "id":ident, "label":label, "name":"Device type",
            "capabilities":caps, "attributes":[
                {"name":name,"value":value} for name,value in values.items()
            ],
        },
    }

def _reads():
    return [
        _source("1079","Bathroom Button",["PushableButton","Battery"],
                {"battery":95,"healthStatus":"online"},1),
        _source("7746","Bathroom Hi-P sensor",["MotionSensor"],
                {"motion":"inactive","networkStatus":"online"},2),
        _source("7754","Bathroom Soft Sensor",["MotionSensor"],
                {"motion":"inactive","networkStatus":"online"},3),
        _source("7818","Bathroom Light 1",["Light","Switch","SwitchLevel"],
                {"level":60,"networkStatus":"online","switch":"off"},4),
        _source("7821","Bathroom Light 2",["Light","Switch","SwitchLevel"],
                {"level":60,"networkStatus":"online","switch":"off"},5),
        _source("7851","Bathroom Meter",["TemperatureMeasurement"],
                {"humidity":68,"networkStatus":"online","temperature":24.2},6),
    ]

def test_all_six_name_matched_entities_and_both_off_lights_survive():
    result=entity_group_answer(_lookup(),_reads())
    assert result["candidate_count"]==6
    assert result["verified_device_read_count"]==6
    assert result["matched_light_count"]==2
    assert result["evidence_reads"]==[1,2,3,4,5,6]
    text=result["text"]
    assert "Bathroom Light 1" in text and "Bathroom Light 2" in text
    assert text.count("switch=off")==2
    assert text.count("last reported level=60%")==2
    assert "Bathroom Meter" in text and "temperature=24.2°C" in text
    assert "Bathroom Button" in text and "battery=95%" in text
    assert "room membership" in text
    assert "Shower Light" not in text
    assert "currently at 60%" not in text
    assert text.count("(Read #")==6

@pytest.mark.parametrize("area",["Hallway","Kitchen","Bedroom"])
def test_generic_source_group_answer_has_no_named_room_routing(area):
    rows=_reads()
    for row in rows:
        row["source_data"]["label"]=row["source_data"]["label"].replace(
            "Bathroom",area)
    result=entity_group_answer(_lookup(area),rows)
    assert result is not None
    assert result["matched_light_count"]==2
    assert area+" Light 2" in result["text"]

def test_partial_group_and_mismatched_scoped_ids_cannot_claim_complete():
    assert entity_group_answer(_lookup(),_reads()[:-1]) is None
    bad=_reads()
    bad[4]["source_data"]["id"]="9999"
    assert entity_group_answer(_lookup(),bad) is None
    assert entity_group_answer(_lookup(),[]) is None

def test_duplicate_or_unattested_group_ids_and_unverified_lookup_rejected():
    bad=_lookup()
    bad[0]["candidate_ids"][-1]="7818"
    assert entity_group_answer(bad,_reads()) is None
    assert entity_group_answer([{"status":"ambiguous","query":"Bathroom",
                                  "candidate_ids":["7818","7821"]}],_reads()) is None

def test_stored_level_is_not_illuminated_brightness_and_no_light_by_name_alone():
    rows=_reads()
    rows[3]["source_data"]["capabilities"]=["Switch"]
    result=entity_group_answer(_lookup(),rows)
    assert result["matched_light_count"]==1
    assert result["text"].count("last reported level=60%")==1
    assert "Bathroom Light 1" in result["text"]

def test_missing_or_unbounded_attributes_are_not_invented():
    rows=_reads()
    rows[3]["source_data"]["attributes"]=[
        {"name":"switch","value":"flashing"},
        {"name":"level","value":150},
        {"name":"password","value":"secret"},
        {"name":"networkStatus","value":"offline; reboot now"}]
    result=entity_group_answer(_lookup(),rows)
    assert result is not None
    assert "reboot now" not in result["text"]
    assert "secret" not in result["text"]
    assert "level=150%" not in result["text"]
    assert "switch=flashing" not in result["text"]

@pytest.mark.asyncio
async def test_native_model_chosen_six_reads_answer_group_not_first_nine_facts():
    devices=[
        {"id":w["source_data"]["id"],"label":w["source_data"]["label"]}
        for w in _reads()
    ]
    mcp=FakeMCP([DEVICE])
    async def identities():return devices
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[w["source_data"] for w in _reads()])
    num=0
    async def model(messages,tools):
        nonlocal num
        num+=1
        if num==1:
            return {"tool_calls":[native(NAME,{"name":"Bathroom"})]}
        if num==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device",
                "args":{"deviceId":ident,"mode":"summary"}})
                for ident in ["1079","7746"]]}
        if num==3:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device",
                "args":{"deviceId":ident,"mode":"summary"}})
                for ident in ["7754","7818"]]}
        if num==4:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device",
                "args":{"deviceId":ident,"mode":"summary"}})
                for ident in ["7821","7851"]]}
        return {"content":"The light states are source-reported, but "
                "I cannot provide the strict JSON claim list."}
    out=await run_native_read_agent(
        question="Check the lights and other devices associated by name "
                 "with Bathroom. Read-only.",
        mcp=mcp,executor=executor,chat=model,
        max_rounds=5,max_reads=8)
    diag=out["native_diagnostics"]
    assert diag["successful_reads"]==6
    assert diag["subject_relevance"]["status"]=="not_blocked"
    assert diag["concise_answer_source"]=="verified_entity_group_comparison"
    assert diag["entity_group_summary"]["matched_light_count"]==2
    assert diag["entity_group_summary"]["verified_device_read_count"]==6
    assert "Bathroom Light 2" in out["answer"]["text"]
    assert out["answer"]["text"].count("switch=off")==2
    assert "Independent claim validation" in out["report"]["text"]
    assert all(call[1]["tool"]=="hub_get_device" for call in executor.calls)
