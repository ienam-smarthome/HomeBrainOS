"""v0.18.190: warning-window-aligned evidence, not successful-read counts.

Live sample: 17:42:22 setVolume slow warning, latest 10 device status
events only 19:33-19:55, then repeated narrower log reads. The host must
offer a bounded model-selected command-event history, not claim actor
coverage from those later status events.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool
from investigation_v2.native_evidence_coverage import (
    gap_for_target, repeated_log_evidence,
)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeExecutor, FakeMCP, READ_DIAG, SEARCH
)
from investigation_v2.native_entity_lookup import NAME

DEV=MCPTool("hub_read_devices","Read-only device",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_device","hub_list_device_events"]},
        "args":{"type":"object","additionalProperties":True},
    },"required":["tool","args"]},annotations={"readOnlyHint":True})

def invoke(gateway,operation,**args):
    return {"function":{"name":gateway,"arguments":{
        "tool":operation,"args":args}}}

def src_log(method="setVolume",stamp="2026-10-28 17:42:22.697",
            count=1):
    return {"log_summary":{
        "warning_error_groups":[{
            "source_type":"dev","source_id":"7934","source_name":"Google Nest Hub",
            "message":f"dev|7934|Google Nest Hub|method {method} ran for 124,842ms",
            "level":"WARN","count":count,
            "oldest_returned":stamp,"newest_returned":stamp,
        }],
        "returned_rows":count,
    }}

def src_status_event():
    return {
        "issuer_apps":[],"count":10,
        "events":[
            {"name":"status","value":"idle",
             "date":"2026-10-28T19:55:19.398+0000",
             "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
            {"name":"status","value":"playing",
             "date":"2026-10-28T19:33:33.599+0000",
             "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
        ],"source_complete":False,
    }

def w(read,op,data,filters=None):
    return {"read":read,"operation":op,"source_data":data,
            "read_filters":filters or {}}

def test_recent_status_page_does_not_cover_earlier_slow_method_warning():
    receipts=[w(2,"hub_get_logs",src_log()),
              w(5,"hub_list_device_events",src_status_event(),
                {"deviceId":"7934","limit":10})]
    gap=gap_for_target(receipts,["7934"],can_read_events=True)
    assert gap["kind"]=="target_warning_event_window_uncovered"
    assert gap["warning_window"]["oldest"]=="2026-10-28 17:42:22.697"
    assert gap["event_windows_checked"][0]["oldest"].startswith("2026-10-28T19:33")
    assert gap["candidate_filters"]["deviceId"]=="7934"
    assert gap["candidate_filters"]["attribute"]=="command-setVolume"
    assert gap["candidate_filters"]["hoursBack"]==48
    assert gap["candidate_filters"]["limit"]==50
    assert gap["limitation"].find("not proof")>0


def test_issuer_at_warn_period_closes_specific_gap_without_proving_cause():
    first=[w(2,"hub_get_logs",src_log()),
           w(5,"hub_list_device_events",src_status_event(),{"deviceId":"7934"})]
    command={"events":[{
        "name":"command-setVolume","date":"2026-10-28T17:42:22.698+0000",
        "producedBy":{"appId":"4080","name":"Calendar Notifier"},
    }],"issuer_apps":[{"appId":"4080","name":"Calendar Notifier"}]}
    later=first+[w(9,"hub_list_device_events",command,{
        "deviceId":"7934","attribute":"command-setVolume","hoursBack":48,"limit":50,
    })]
    assert gap_for_target(later,["7934"],can_read_events=True) is None
    assert gap_for_target(first,["7934"],can_read_events=False) is None


def test_only_already_seen_group_timestamp_subsets_are_redundant():
    broad={"log_summary":{"warning_error_groups":[{
        "source_type":"dev","source_id":"7934",
        "message":"dev|7934|Google Nest Hub|method runQ ran for 147,429ms",
        "oldest_returned":"2026-10-28 17:04:48.106",
        "newest_returned":"2026-10-28 17:58:24.126","count":43
    }]}}
    contained={"log_summary":{"warning_error_groups":[{
        **broad["log_summary"]["warning_error_groups"][0],
        "oldest_returned":"2026-10-28 17:30:00.000",
        "newest_returned":"2026-10-28 17:50:00.000","count":13
    }]}}
    assert repeated_log_evidence([w(2,"hub_get_logs",broad)],contained) is True
    expanded={"log_summary":{"warning_error_groups":[{
        **broad["log_summary"]["warning_error_groups"][0],
        "newest_returned":"2026-10-28 18:30:00.000","count":44
    }]}}
    assert not repeated_log_evidence([w(2,"hub_get_logs",broad)],expanded)
    distinct={"log_summary":{"warning_error_groups":[{
        **broad["log_summary"]["warning_error_groups"][0],
        "message":"A different warning with same device ID"
    }]}}
    assert not repeated_log_evidence([w(2,"hub_get_logs",broad)],distinct)
    assert not repeated_log_evidence([],contained)


@pytest.mark.asyncio
async def test_model_one_extra_round_after_wrong_event_window_gets_app_issuer():
    mcp=FakeMCP([DEV,READ_DIAG,SEARCH])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    warning_rows={"entries":[{"type":"dev","name":"Google Nest Hub",
        "level":"WARN","time":"2026-10-28 17:42:22.697",
        "message":"dev|7934|Google Nest Hub|method setVolume ran for 124,842ms"}]}
    early_status={"events":[
        {"name":"status","date":"2026-10-28T19:55:19.398+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"},"value":"idle"},
        {"name":"status","date":"2026-10-28T19:33:33.599+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"},"value":"playing"},
    ]}
    command={"events":[{
        "name":"command-setVolume","date":"2026-10-28T17:42:22.698+0000",
        "producedBy":{"appId":4080,"name":"Calendar Notifier"},
        "description":"Private speech text must not be seen",
    }]}
    executor=FakeExecutor(mcp,[
        warning_rows,{"id":"7934","label":"Google Nest Hub",
                      "attributes":[{"name":"networkStatus","value":"online"}]},
        early_status,warning_rows,{"current":{"freeMemoryMB":834.33}},
        command,
    ])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if not tools:
            raise RuntimeError("No extra synthesis required")
        if step==1:
            return {"tool_calls":[{"function":{"name":NAME,
                                               "arguments":{"name":"Google Nest Hub"}}}]}
        if step==2:
            return {"tool_calls":[invoke("hub_read_diagnostics","hub_get_logs",
                                        deviceId="7934",mode="past",level="warn",limit=100)]}
        if step==3:
            return {"tool_calls":[invoke("hub_read_devices","hub_get_device",
                                        deviceId="7934")]}
        if step==4:
            return {"tool_calls":[invoke("hub_read_devices","hub_list_device_events",
                                        deviceId="7934",limit=10)]}
        if step==5:
            return {"tool_calls":[invoke("hub_read_diagnostics","hub_get_logs",
                                        deviceId="7934",mode="past",level="warn",limit=50)]}
        if step==6:
            return {"tool_calls":[invoke("hub_read_diagnostics","hub_get_metrics",limit=50)]}
        if step==7:
            review=[str(m.get("content","")) for m in messages
                    if m.get("role")=="user" and "Evidence coverage assessment" in str(m.get("content",""))]
            assert len(review)==1
            assert "target_warning_event_window_uncovered" in review[0]
            assert "command-setVolume" in review[0]
            return {"tool_calls":[invoke("hub_read_devices","hub_list_device_events",
                                        deviceId="7934",hoursBack=48,limit=50,
                                        attribute="command-setVolume")]}
        raise AssertionError("Exceeded single bounded extra model choice")
    result=await run_native_read_agent(
        question="Investigate the causal mechanism of this device's slow methods",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    d=result["native_diagnostics"]
    assert d["rounds"]==7
    assert d["successful_reads"]==6
    assert d["causal_coverage_challenge_used"] is True
    assert d["causal_coverage_gap"] is None
    assert d["redundant_log_subsets"]==1
    assert d["verified_typed_ids"]["app"]==["4080"]
    assert result["answer"]["validation_issues"]==[
        "model_claims_not_atomically_verified","historical_coverage_unverified"]
    assert executor.calls[-1][1]["args"]["attribute"]=="command-setVolume"
    assert executor.calls[-1][1]["args"]["hoursBack"]==48
    assert "Calendar Notifier" in result["answer"]["text"]
    assert "Private speech" not in result["answer"]["text"]


@pytest.mark.asyncio
async def test_unsolved_warning_window_is_visible_not_reported_as_causal_success():
    mcp=FakeMCP([DEV,READ_DIAG])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"entries":[{"level":"WARN","type":"dev","name":"Google Nest Hub",
           "time":"2026-10-28 17:42:22.697",
           "message":"dev|7934|Google Nest Hub|method setVolume ran for 124,842ms"}]},
        {"events":[{"name":"status","date":"2026-10-28T19:55:19.398+0000",
                    "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}}]},
    ])
    turn=0
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:
            return {"tool_calls":[{"function":{"name":NAME,
                                               "arguments":{"name":"Google Nest Hub"}}}]}
        if turn==2:
            return {"tool_calls":[invoke("hub_read_diagnostics","hub_get_logs",
                                        mode="past",level="warn",deviceId="7934")]}
        if turn==3:
            return {"tool_calls":[invoke("hub_read_devices","hub_list_device_events",
                                        deviceId="7934",limit=10)]}
        return {"content":"The cause of this incident is not independently verified."}
    result=await run_native_read_agent(
        question="What caused this device's slowdown?",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    assert result["native_diagnostics"]["causal_coverage_gap"]["kind"]=="target_warning_event_window_uncovered"
    assert "Evidence gap: event history" in result["answer"]["text"]
    assert "warning_window_actor_provenance_unverified" in result["answer"]["validation_issues"]
