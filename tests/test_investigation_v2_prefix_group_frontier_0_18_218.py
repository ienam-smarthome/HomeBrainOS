"""v0.18.218 — source prefix candidates and bounded READ frontier.

The 29 Oct bathroom lookup returned six source names but marked an anchored
prefix group ambiguous, denying three specific reads, and the model then
wasted 20 seconds on a full device listing. This tests arbitrary names and
unknown IDs, not any known bathroom device inventory or hardcoded route.
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
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP,FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import DEVICE,native


def _names(area="Bathroom"):
    return [
        {"id":"9101","label":area+" Light 1"},
        {"id":"9102","label":area+" Light 2"},
        {"id":"9103","label":area+" Fan"},
        {"id":"9104","label":area+" Meter"},
        {"id":"9105","label":area+" Motion"},
        {"id":"9106","label":area+" Switch"},
    ]


def test_single_word_location_prefix_provides_six_read_candidates_not_ambiguity():
    result=choose_device("bathroom",_names())
    assert result["status"]=="candidate_group"
    assert result["match_basis"]=="source_name_prefix"
    assert [x["id"] for x in result["matches"]]==[
        "9101","9102","9103","9104","9105","9106"]
    assert result["group_membership_verified"] is False
    assert "state" in result["limits"]


@pytest.mark.parametrize("prefix",["Kitchen","Hallway","Livingroom"])
def test_prefix_candidates_apply_to_any_named_area_without_keyword_routing(prefix):
    result=choose_device(prefix,_names(prefix))
    assert result["status"]=="candidate_group"
    assert len(result["matches"])==6


def test_exact_duplicate_alias_stays_ambiguous_no_arbitrary_selection():
    items=[{"id":"9101","label":"Bathroom"},
           {"id":"9102","label":"Bathroom"},
           {"id":"9103","label":"Bathroom Light"}]
    result=choose_device("bathroom",items)
    assert result["status"]=="ambiguous"
    assert {r["id"] for r in result["matches"]}=={"9101","9102"}


def test_prefix_over_limit_does_not_grant_or_truncate_candidate_authority():
    items=[{"id":str(9100+i),"label":f"Hallway Device {i}"}
           for i in range(9)]
    result=choose_device("hallway",items)
    assert result["status"]=="candidate_group_too_large"
    assert result["count"]==9 and result["matches"]==[]


def test_prefix_candidates_do_not_imply_room_membership_or_state():
    lookup=[{"query":"bathroom","status":"candidate_group",
             "candidate_ids":["9101","9102"],"count":2}]
    blocker=subject_relevance_limit(lookup,[])
    assert blocker["reason"]=="candidate_group_incomplete"
    assert blocker["source_verified_candidate_reads"]==0
    assert "not proof of group membership" in blocker["text"]


@pytest.mark.asyncio
async def test_prefix_group_read_permission_never_auto_executes_or_expands_scope():
    mcp=FakeMCP([DEVICE])
    async def identities(): return _names()
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{
        "id":"9101","label":"Bathroom Light 1",
        "attributes":[{"name":"switch","value":"on"}]}])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[native(NAME,{"name":"bathroom"})]}
        if calls==2:
            assert '"candidate_group"' in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device",
                "args":{"deviceId":"9999","mode":"summary"}})]}
        if calls==3:
            assert "target_id_not_verified_from_live_source" in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device",
                "args":{"deviceId":"9101","mode":"summary"}})]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="Check bathroom device status.",chat=model,mcp=mcp,
        executor=executor,max_rounds=4)
    d=result["native_diagnostics"]
    assert len(executor.calls)==1
    assert d["named_identity_lookups"][0]["status"]=="candidate_group"
    assert d["verified_source_ids"]>=6
    assert "target_id_not_verified_from_live_source" in [
        r["code"] for r in d["failures"]]
    assert d["subject_relevance"]["reason"]=="candidate_group_incomplete"
    assert d["subject_relevance"]["source_verified_candidate_reads"]==1
    assert "9101" in result["report"]["text"]


@pytest.mark.asyncio
async def test_bounded_candidates_block_redundant_unscoped_list_and_allow_two_reads():
    mcp=FakeMCP([DEVICE])
    async def identities():
        return [{"id":"9101","label":"Hallway Light 1"},
                {"id":"9102","label":"Hallway Light 2"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"id":"9101","label":"Hallway Light 1","attributes":[
            {"name":"switch","value":"on"}]},
        {"id":"9102","label":"Hallway Light 2","attributes":[
            {"name":"switch","value":"off"}]}])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[native(NAME,{"name":"hallway"})]}
        if calls==2:
            assert '"candidate_group"' in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_devices","args":{}})]}
        if calls==3:
            assert '"bounded_identity_candidates_available"' in messages[-1]["content"]
            assert "9101, 9102" in messages[-1]["content"]
            return {"tool_calls":[
                native("hub_read_devices",{"tool":"hub_get_device",
                       "args":{"deviceId":"9101","mode":"summary"}}),
                native("hub_read_devices",{"tool":"hub_get_device",
                       "args":{"deviceId":"9102","mode":"summary"}})]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="Which hallway lights are on or off?",
        chat=model,mcp=mcp,executor=executor,max_rounds=4)
    d=result["native_diagnostics"]
    assert calls==4
    assert d["successful_reads"]==2
    assert d["reads_executed"]==2
    assert d["subject_relevance"]["status"]=="not_blocked"
    assert any(f["code"]=="bounded_identity_candidates_available"
               for f in d["failures"])
    assert all(args["tool"]=="hub_get_device"
               for _,args in executor.calls)
    assert "hub_list_devices" not in [args["tool"] for _,args in executor.calls]


@pytest.mark.asyncio
async def test_global_inventory_not_blocked_without_prior_identity_candidates():
    mcp=FakeMCP([DEVICE])
    executor=FakeExecutor(mcp,[{"devices":[]}])
    async def model(messages,tools):
        if len([m for m in messages if m.get("role")=="tool"])==0:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_devices","args":{}})]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="How many devices are in my Hubitat system?",
        mcp=mcp,executor=executor,chat=model,max_rounds=2)
    assert result["native_diagnostics"]["reads_executed"]==1
    assert executor.calls[0][1]["tool"]=="hub_list_devices"
