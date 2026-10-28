"""v0.18.194 live replay: unscoped device-events and repeated malformed reads.

A resolved device and its source-backed warnings must not turn a hub/location
event list into target-specific history. No READ is executed unless the model
chooses a valid, fully scoped request, with independently verified IDs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPTool
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_read_scope import target_history_scope_problem
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG,
)

DEVICE=MCPTool("hub_read_devices","Device READ",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_device",
                                       "hub_list_device_events"]},
        "args":{"type":"object","additionalProperties":True}},
    "required":["tool","args"]},annotations={"readOnlyHint":True})

LOG={"entries":[
    {"level":"WARN","type":"dev","name":"Google Nest Hub",
     "time":"2026-10-28 19:55:19.194",
     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
    {"level":"WARN","type":"dev","name":"Google Nest Hub",
     "time":"2026-10-28 19:55:19.399",
     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
]}
WARN_RECEIPT=[{"read":1,"operation":"hub_get_logs","source_data":{
    "log_summary":{"warning_error_groups":[{
        "source_id":"7934","level":"WARN",
        "oldest_returned":"2026-10-28 19:55:19.194",
        "newest_returned":"2026-10-28 19:55:19.399"
    }]}}}]


def call(gateway, op=None, **args):
    if op:
        return {"function":{"name":gateway,"arguments":{
            "tool":op,"args":args}}}
    return {"function":{"name":gateway,"arguments":args}}


def test_unscoped_device_history_is_not_substituted_for_verified_device():
    issue=target_history_scope_problem(
        "hub_list_device_events",{"limit":100},["7934"],WARN_RECEIPT)
    assert issue=="target_device_history_scope_missing"
    assert target_history_scope_problem(
        "hub_list_device_events",{"limit":100,"deviceId":"7934"},
        ["7934"],WARN_RECEIPT) is None
    assert target_history_scope_problem(
        "hub_list_device_events",{"mode":"hub","limit":100},
        ["7934"],WARN_RECEIPT) is None
    assert target_history_scope_problem(
        "hub_list_device_events",{"limit":100},["7934"],[]) is None
    assert target_history_scope_problem(
        "hub_list_device_events",{"limit":100},[],WARN_RECEIPT) is None
    assert target_history_scope_problem(
        "hub_list_device_events",{"limit":100},["7934","7103"],
        WARN_RECEIPT) is None


@pytest.mark.asyncio
async def test_host_rejects_unscoped_history_then_model_chooses_correct_device_read():
    mcp=FakeMCP([DEVICE,READ_DIAG])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[LOG,{"events":[{
        "name":"command-setVolume",
        "date":"2026-10-28T17:42:22.698+0000",
        "producedBy":{"appId":4080,"name":"Calendar Notifier"},
    }]}])
    turn=0
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:
            return {"tool_calls":[call("homebrain_find_device",
                                       name="Google Nest Hub")]}
        if turn==2:
            return {"tool_calls":[call("hub_read_diagnostics",
                                       "hub_get_logs",deviceId="7934",
                                       level="warn",mode="past",limit=100)]}
        if turn==3:
            return {"tool_calls":[call("hub_read_devices",
                                       "hub_list_device_events",limit=100)]}
        if turn==4:
            assert "target_device_history_scope_missing" in messages[-1]["content"]
            assert "deviceId=7934" in messages[-1]["content"]
            return {"tool_calls":[call("hub_read_devices",
                                       "hub_list_device_events",
                                       deviceId="7934",limit=100)]}
        return {"content":"Verified app 4080 issued a past command; the warning cause remains unknown."}
    answer=await run_native_read_agent(question="Investigate this device warning",
                                      chat=model,mcp=mcp,executor=executor)
    diagnostics=answer["native_diagnostics"]
    assert diagnostics["reads_executed"]==2
    assert diagnostics["successful_reads"]==2
    assert diagnostics["rejected_scope_history_reads"]==1
    assert diagnostics["verified_typed_ids"]["app"]==["4080"]
    assert [entry[1]["tool"] for entry in executor.calls]==[
        "hub_get_logs","hub_list_device_events"]
    assert executor.calls[-1][1]["args"]["deviceId"]=="7934"


@pytest.mark.asyncio
async def test_two_missing_device_ids_stop_before_third_or_eight_second_synthesis():
    mcp=FakeMCP([DEVICE,READ_DIAG])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[LOG])
    round_count=0
    async def model(messages,tools):
        nonlocal round_count
        round_count+=1
        assert tools, "Should not call final synthesis with no new evidence"
        if round_count==1:
            return {"tool_calls":[call("homebrain_find_device",
                                       name="Google Nest Hub")]}
        if round_count==2:
            return {"tool_calls":[call("hub_read_diagnostics",
                                       "hub_get_logs",deviceId="7934",
                                       level="warn",mode="past",limit=100)]}
        if round_count in (3,4):
            return {"tool_calls":[call("hub_read_devices",
                                       "hub_get_device",mode="details")]}
        raise AssertionError("Too many invalid proposals accepted")
    result=await run_native_read_agent(question="Why is Google Nest Hub showing excessive load?",
                                       chat=model,mcp=mcp,executor=executor)
    d=result["native_diagnostics"]
    assert round_count==4
    assert d["rounds"]==4
    assert d["reads_executed"]==1
    assert d["stop_reason"]=="repeated_invalid_proposal"
    assert d["invalid_contract_attempts"]["hub_get_device"]==2
    assert d["final_synthesis_skipped_reason"]=="repeated_invalid_reads_with_target_warnings"
    assert d["final_synthesis_ms"]==0
    assert len(executor.calls)==1
    assert "Device 7934 generates excessive hub load" in result["answer"]["text"]


@pytest.mark.asyncio
async def test_explicit_hub_location_history_is_allowed_for_broad_investigation():
    mcp=FakeMCP([DEVICE])
    executor=FakeExecutor(mcp,[{"events":[{
        "name":"mode","value":"Night",
        "date":"2026-10-28T23:00:02.303+0000"}]}])
    counter=0
    async def model(messages,tools):
        nonlocal counter
        counter+=1
        if counter==1:
            return {"tool_calls":[call("hub_read_devices",
                                       "hub_list_device_events",
                                       mode="hub",limit=20)]}
        return {"content":"Hub mode changed to Night; no device caller identified."}
    result=await run_native_read_agent(question="What changed in the hub's modes?",
                                       chat=model,mcp=mcp,executor=executor)
    assert result["native_diagnostics"]["successful_reads"]==1
    assert result["native_diagnostics"]["rejected_scope_history_reads"]==0
    assert len(executor.calls)==1
