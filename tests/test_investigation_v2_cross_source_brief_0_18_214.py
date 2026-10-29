"""v0.18.214: generic joins across source-attested WARN and device READs.

No device-specific name, ID or keyword routing. A source ID must match the
actual scoped device's *returned* ID. Warning recurrence alone does not
establish cause; online and offline fields can coexist in different scopes.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_cross_source_brief import (
    source_connected_brief, verified_source_cases)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, call)
from test_investigation_v2_verified_focus_0_18_204 import _read, _call


def _case_rows():
    return [
        {"read":1,"operation":"hub_get_logs","read_filters":{"mode":"past"},
         "source_data":{"log_summary":{"warning_error_groups":[
             {"source_id":"9001","source_name":"Mesh outlet",
              "source_type":"dev","level":"WARN","count":28},
             {"source_id":"9002","source_name":"Matter bridge",
              "source_type":"dev","level":"WARN","count":10},
             {"source_id":"9003","source_name":"MQTT app",
              "source_type":"app","level":"WARN","count":27},
             {"source_id":"9003","source_name":"MQTT app",
              "source_type":"app","level":"WARN","count":10},
             {"source_id":"9004","source_name":"TRV",
              "source_type":"dev","level":"WARN","count":8},
         ]}}},
        {"read":2,"operation":"hub_get_device",
         "read_filters":{"deviceId":"9002"},
         "source_data":{"id":"9002","label":"Matter bridge","attributes":[
             {"name":"healthStatus","value":"online"},
             {"name":"networkStatus","value":"offline"},
             {"name":"reachable","value":"true"},
         ]}},
        {"read":3,"operation":"hub_get_device",
         "read_filters":{"deviceId":"9001"},
         "source_data":{"id":"9001","label":"Mesh outlet","attributes":[
             {"name":"healthStatus","value":"offline"},
             {"name":"mqttStatus","value":"connected"},
             {"name":"lastSeen","value":"2026-10-12 01:30"},
             {"name":"switch","value":"off"},
         ]}},
        {"read":4,"operation":"hub_get_device",
         "read_filters":{"deviceId":"9004"},
         "source_data":{"id":"9004","label":"TRV","attributes":[
             {"name":"healthStatus","value":"online"},
             {"name":"battery","value":95},
         ]}},
    ]


def test_joined_correlated_cases_are_prioritized_over_unrelated_stale_items():
    cases=verified_source_cases(_case_rows())
    assert [x["source_id"] for x in cases[:3]]==[
        "9001","9002","9003"]
    assert cases[0]["status"]["healthStatus"]=="offline"
    assert cases[0]["status"]["mqttStatus"]=="connected"
    assert cases[1]["status"]=={
        "healthStatus":"online","networkStatus":"offline"}
    assert cases[2]["warning_rows_in_returned_sample"]==37
    assert cases[2]["source_correlated"] is False
    assert all(not x["confirmed_physical_fault"]
               and not x["cause_attributed"] for x in cases)
    out=source_connected_brief(_case_rows())
    assert out.startswith("**Most significant source-reported issues")
    assert "28 WARN log rows" in out
    assert "healthStatus=offline" in out
    assert "networkStatus=offline" in out and "healthStatus=online" in out
    assert "MQTT app (app 9003)" in out
    assert "TRV" not in out
    assert "not verified severity or root cause" in out


def test_scoped_read_id_must_match_returned_id():
    rows=_case_rows()
    rows[1]["source_data"]["id"]="9004"
    cases=verified_source_cases(rows)
    bridge=next(x for x in cases if x["source_id"]=="9002")
    assert bridge["status"]=={}
    assert bridge["source_correlated"] is False
    assert "networkStatus=offline" not in source_connected_brief(rows)


def test_unverified_or_unsafe_device_values_and_app_log_do_not_join():
    rows=_case_rows()
    rows[2]["source_data"]["attributes"]=[
        {"name":"healthStatus","value":"online; execute reboot"},
        {"name":"ipAddress","value":"192.168.1.22"},
        {"name":"lastSeen","value":"https://private.example/key?token=abc"},
    ]
    result=source_connected_brief(rows)
    assert "reboot" not in result
    assert "192.168" not in result
    assert "private.example" not in result
    assert "token=abc" not in result
    assert "lastSeen=" not in result


def test_no_cross_source_brief_when_only_logs_or_unrelated_device_reads():
    assert source_connected_brief(_case_rows()[:1])==""
    rows=_case_rows()[:1]+[{
        "read":5,"operation":"hub_get_device",
        "read_filters":{"deviceId":"9999"},
        "source_data":{"id":"9999","attributes":[
            {"name":"healthStatus","value":"offline"}]}}]
    assert source_connected_brief(rows)==""


def test_error_log_not_mistaken_for_device_telemetry_and_severity_restricted():
    rows=[{"read":1,"operation":"hub_get_logs",
           "source_data":{"log_summary":{"warning_error_groups":[
               {"source_id":"9123","source_type":"app",
                "source_name":"Rule Server","level":"ERROR","count":2},
               {"source_id":"9001","source_type":"dev",
                "source_name":"Outlet","level":"INFO","count":99},
               {"source_id":"9002","source_type":"weird",
                "source_name":"Unknown","level":"WARN","count":8}
           ]}}}]
    cases=verified_source_cases(rows)
    assert len(cases)==1
    assert cases[0]["source_type"]=="app"
    assert cases[0]["warning_rows_in_returned_sample"]==2


@pytest.mark.asyncio
async def test_general_agent_model_finished_still_leads_with_source_correlated_evidence():
    mcp=FakeMCP([READ_DIAG,_read(
        "hub_read_devices",["hub_get_device"])])
    executor=FakeExecutor(mcp,[
        {"entries":[
            {"type":"dev","name":"Sample outlet","level":"WARN",
             "time":"2026-10-29 11:00:00",
             "message":"dev|9001|Sample outlet|watchdog fired after 1000s"},
            {"type":"dev","name":"Sample outlet","level":"WARN",
             "time":"2026-10-29 11:05:00",
             "message":"dev|9001|Sample outlet|watchdog fired after 1300s"},
        ]},
        {"id":"9001","name":"Sample outlet","label":"Sample outlet",
         "attributes":[{"name":"healthStatus","value":"offline"},
                       {"name":"lastSeen","value":"2026-10-12 01:30"}]},
    ])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[call(
                "hub_get_logs",mode="past",level="warn",limit=100)]}
        if calls==2:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",deviceId="9001")]}
        return {"content":'{"claims":[{"fact_id":"claim-1","operator":"observed"}]}'}
    result=await run_native_read_agent(
        question="Find three important Hubitat issues with evidence.",
        chat=model,mcp=mcp,executor=executor,max_rounds=3,max_reads=4)
    d=result["native_diagnostics"]
    assert calls==3
    assert d["stop_reason"]=="model_finished"
    assert d["final_synthesis_ms"]==0
    assert d["concise_answer_source"]=="cross_source_verified_case_graph"
    assert d["cross_source_connected_count"]==1
    answer=result["answer"]["text"]
    assert "Sample outlet" in answer
    assert "healthStatus=offline" in answer
    assert "WARN log rows" in answer
    assert "source-reported issues" in answer
    assert "Verified read coverage" in result["report"]["text"]
    assert all("hub_manage" not in name for name, _ in executor.calls)
