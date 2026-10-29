"""v0.18.217 general relevance: source-verified target required for answers.

The 29 Oct second V2 test searched 'bathroom lights', timed out on
hub_list_devices and produced an unrelated stale-device report. These
tests cover any failed named subject or source-verified candidate group.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_entity_lookup import choose_device,NAME
from investigation_v2.native_subject_relevance import subject_relevance_limit
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP,FakeExecutor,READ_DIAG)
from test_investigation_v2_native_entity_lookup_0_18_184 import DEVICE,native

def _lookup(status="not_found", candidates=()):
    return [{"query":"bathroom lights","status":status,"count":len(candidates),
             "candidate_ids":list(candidates)}]

def _read(id, value="off"):
    return {"read":1,"operation":"hub_get_device",
            "read_filters":{"deviceId":id},
            "source_data":{"id":id,"attributes":[
                {"name":"switch","value":value}]}}


def test_general_collective_names_return_independently_sourced_candidates():
    devices=[{"id":"9101","label":"Bathroom Light 1"},
             {"id":"9102","label":"Bathroom Light 2"},
             {"id":"9103","label":"Hallway Light 1"},
             {"id":"9104","label":"Bath Switch"}]
    result=choose_device("bathroom lights",devices)
    assert result["status"]=="candidate_group"
    assert [r["id"] for r in result["matches"]]==["9101","9102"]
    assert result["group_membership_verified"] is False
    assert choose_device("lights",devices)["status"]=="not_found"
    assert choose_device("hallway light 1",devices)["status"]=="unique"
    assert choose_device("bathroom motion",devices)["status"]=="not_found"


def test_collective_prefix_never_accepts_bad_ids_or_unbounded_group():
    results=choose_device("Bathroom lights",[
        {"id":"BAD","label":"Bathroom Light 1"},
        {"id":"9101","label":"Bathroom Light 2"}])
    assert [x["id"] for x in results["matches"]]==["9101"]
    many=[{"id":str(9100+i),"label":f"Bathroom Light {i}"}
          for i in range(9)]
    result=choose_device("Bathroom lights",many)
    assert result["status"]=="candidate_group_too_large"
    assert result["matches"]==[]


def test_unresolved_named_target_never_degrades_to_unrelated_hub_health_answer():
    evidence=[{"read":1,"operation":"hub_get_device_health",
               "source_data":{"staleDevices":[{"id":"3333"}],
                              "unknownDevices":[]}},
              {"read":2,"operation":"hub_get_logs",
               "source_data":{"log_summary":{"returned_rows":100}}}]
    result=subject_relevance_limit(
        _lookup(),evidence,failures=[{
            "operation":"hub_list_devices","code":"read_timeout"}])
    assert result["reason"]=="named_subject_not_verified"
    assert "bathroom lights" in result["text"]
    assert "timed out" in result["text"]
    assert "staleDevices" not in result["text"]
    assert "generic hub" in result["text"]


def test_bounded_candidate_group_requires_all_candidate_readings():
    lookup=_lookup("candidate_group",["9101","9102"])
    state=subject_relevance_limit(lookup,[_read("9101")])
    assert state["reason"]=="candidate_group_incomplete"
    assert state["candidate_count"]==2
    assert state["source_verified_candidate_reads"]==1
    assert subject_relevance_limit(
        lookup,[_read("9101"),_read("9102")]) is None
    assert subject_relevance_limit(lookup,[_read("9999")])[
        "source_verified_candidate_reads"]==0


def test_mismatching_scoped_return_does_not_make_candidate_verified():
    invalid=_read("9101")
    invalid["source_data"]["id"]="9102"
    assert subject_relevance_limit(
        _lookup("candidate_group",["9101"]),[invalid])[
            "source_verified_candidate_reads"]==0


def test_generic_health_without_model_requested_identity_is_unaffected():
    assert subject_relevance_limit([],[]) is None
    assert subject_relevance_limit(
        _lookup(),[_read("1234")],focus_ids=["1234"]) is None
    assert subject_relevance_limit(
        [{"query":"fan","status":"unique","candidate_ids":[]}],[]) is None


@pytest.mark.asyncio
async def test_second_question_replay_no_relevant_device_means_no_false_answer():
    mcp=FakeMCP([READ_DIAG])
    async def lookup():
        return [{"id":"7000","label":"Livingroom Light"}]
    mcp.get_device_identities=lookup
    executor=FakeExecutor(mcp,[{
        "staleDevices":[{"id":"7341","name":"HomeKit CAM",
                         "lastActivity":"2026-06-29T21:35:20+0100"}],
        "unknownDevices":[]}])
    steps=0
    async def model(messages,tools):
        nonlocal steps
        steps+=1
        if steps==1:
            return {"tool_calls":[native(NAME,{"name":"bathroom lights"})]}
        if steps==2:
            assert '"not_found"' in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_diagnostics",{
                "tool":"hub_get_device_health","args":{}})]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="What is the bathroom lights state? Read-only.",
        mcp=mcp,executor=executor,chat=model,max_rounds=3)
    assert result["native_diagnostics"]["subject_relevance"]["status"] == (
        "insufficient_target_relevance")
    assert result["native_diagnostics"]["concise_answer_source"] == (
        "unresolved_named_subject_evidence")
    assert "bathroom lights" in result["answer"]["text"]
    assert "generic hub" in result["answer"]["text"]
    assert "HomeKit CAM" not in result["answer"]["text"]
    assert "HomeKit CAM" in result["report"]["text"]
    assert len(executor.calls)==1
    assert steps==3


@pytest.mark.asyncio
async def test_collective_names_can_be_read_individually_no_full_hub_listing():
    mcp=FakeMCP([DEVICE])
    async def identities():
        return [{"id":"9101","label":"Bathroom Light 1"},
                {"id":"9102","label":"Bathroom Light 2"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"id":"9101","label":"Bathroom Light 1","attributes":[
            {"name":"switch","value":"on"}]},
        {"id":"9102","label":"Bathroom Light 2","attributes":[
            {"name":"switch","value":"off"}]},
    ])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[native(NAME,{"name":"bathroom lights"})]}
        if calls==2:
            assert '"candidate_group"' in messages[-1]["content"]
            return {"tool_calls":[
                native("hub_read_devices",{"tool":"hub_get_device",
                    "args":{"deviceId":"9101","mode":"summary"}}),
                native("hub_read_devices",{"tool":"hub_get_device",
                    "args":{"deviceId":"9102","mode":"summary"}}),
            ]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="Which bathroom lights are on? Read-only.",
        mcp=mcp,executor=executor,chat=model,max_rounds=3)
    assert result["native_diagnostics"]["subject_relevance"]["status"]=="not_blocked"
    assert result["native_diagnostics"]["successful_reads"]==2
    assert result["native_diagnostics"]["named_identity_lookups"][0][
        "candidate_ids"]==["9101","9102"]
    assert len(executor.calls)==2
    assert all(x[1]["tool"]=="hub_get_device" for x in executor.calls)
