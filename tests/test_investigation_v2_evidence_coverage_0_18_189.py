"""Live-shaped evidence gap, metrics projection and discovery coverage tests."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool, MCPToolResult
from investigation_v2.native_read_agent import _payload, run_native_read_agent
from investigation_v2.native_metrics_evidence import project_metrics
from investigation_v2.native_evidence_coverage import (
    gap_for_target, gateway_offers_operation, useful_discovery_fingerprint)
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, SEARCH)
from investigation_v2.native_entity_lookup import NAME

DEVICE=MCPTool("hub_read_devices", "Read device and events", {
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_device","hub_list_device_events"]},
        "args":{"type":"object","additionalProperties":True},
    },"required":["tool","args"]},annotations={"readOnlyHint":True})


def call(name, args):
    return {"function":{"name":name,"arguments":args}}


def read(gateway, op, **args):
    return call(gateway,{"tool":op,"args":args})


def test_metrics_are_numeric_and_safe_with_sample_limits():
    raw={
        "current":{
            "cpu":{"usagePct":17.3, "schedulerRunning":False},
            "memory":{"freeKB":820000,"totalKB":1024000},
            "dbSizeMB":195,"temperatureCelsius":46.6,
            "userName":"PRIVATE_DATA","accessToken":"VERY_PRIVATE",
            "endpoint":"http://private.example/",
        },
        "trends":{
            "cpu":[{"timestamp":"2026-10-28T19:00:00+0000","load":11.5,
                    "password":"PRIVATE_DATA"},
                   {"timestamp":"2026-10-28T19:01:00+0000","load":17.3}],
            "freeMemoryMB":[900,890,880],
        },
        "trendPointsAvailable":300,
        "historyFile":"/private/hub-metrics.csv",
    }
    projected=project_metrics(raw)
    assert projected["current"]["cpu"]["usagePct"]==17.3
    assert projected["current"]["cpu"]["schedulerRunning"] is False
    assert projected["current"]["memory"]["freeKB"]==820000
    assert projected["trends"]["cpu"][0]["load"]==11.5
    assert projected["trendPointsAvailable"]==300
    for secret in ("PRIVATE_DATA","VERY_PRIVATE","private.example","historyFile"):
        assert secret not in str(projected)
    live=_payload(MCPToolResult("hub_read_diagnostics",{},{},"",raw),
                  "hub_get_metrics")
    assert live["current"]["dbSizeMB"]==195
    assert "trends" in live
    from investigation_v2.native_evidence_focus import focused_highlights
    highlights=focused_highlights([
        {"read":3,"operation":"hub_get_metrics","source_data":live}
    ],["7934"])
    assert any("dbSizeMB" in line for line in highlights)
    assert any("trend samples" in line for line in highlights)
    assert any("attribution" in line for line in highlights)


def test_causal_coverage_requires_source_attested_target_logs_and_available_events():
    manifest={"hub_read_devices":DEVICE}
    available=gateway_offers_operation(manifest,{},"hub_list_device_events")
    assert available
    warning={"read":1,"operation":"hub_get_logs",
             "source_data":{"log_summary":{"warning_error_groups":[{
                 "source_id":"7934","level":"WARN",
                 "message":"method runQ ran for 147,429ms"}]}}}
    no_focus=gap_for_target([warning],[],can_read_events=True)
    assert no_focus is None
    assert gap_for_target([warning],["7934"],can_read_events=False) is None
    gap=gap_for_target([warning],["7934"],can_read_events=True)
    assert gap["kind"]=="target_warning_actor_provenance_unchecked"
    assert gap["supporting_warning_reads"]==[1]
    event={"read":2,"operation":"hub_list_device_events",
           "read_filters":{"deviceId":"7934"},"source_data":{"events":[]}}
    assert gap_for_target([warning,event],["7934"],
                          can_read_events=True) is None


def test_discovery_has_semantic_fingerprint_not_response_metadata():
    a={"results":[{"gateway":"hub_read_devices",
                   "tool":"hub_list_device_events"},
                  {"gateway":"hub_read_diagnostics","tool":"hub_get_metrics"}]}
    b={"results":list(reversed(a["results"])),
       "resultsCount":2,"query":"another phrase"}
    assert useful_discovery_fingerprint(a)==useful_discovery_fingerprint(b)


@pytest.mark.asyncio
async def test_after_six_rounds_model_can_choose_one_event_coverage_read():
    mcp=FakeMCP([DEVICE,READ_DIAG,SEARCH])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    logs={"entries":[
        {"level":"WARN","type":"dev","name":"Google Nest Hub",
         "time":"2026-10-28 17:42:22.697",
         "message":"dev|7934|Google Nest Hub|method setVolume ran for 124,842ms"}
    ]}
    metrics={"current":{"cpuLoad":17.0,"freeMemoryKB":850000},
             "trends":{"cpuLoad":[12.5,13.2,17.0]}}
    device={"id":"7934","label":"Google Nest Hub",
            "attributes":[{"name":"networkStatus","value":"online"}]}
    discovery={"results":[{"gateway":"hub_read_devices",
                           "tool":"hub_list_device_events"},
                          {"gateway":"hub_read_diagnostics",
                           "tool":"hub_get_metrics"}]}
    events={"events":[{"name":"command-setVolume",
                       "date":"2026-10-28T17:42:22.698+0000",
                       "producedBy":{"appId":4080,"name":"Calendar Notifier"}}]}
    executor=FakeExecutor(mcp,[logs,metrics,device,discovery,discovery,events])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[call(NAME,{"name":"Google Nest Hub"})]}
        if step==2:
            return {"tool_calls":[read("hub_read_diagnostics","hub_get_logs",
                                       mode="past",level="warn",deviceId="7934")]}
        if step==3:
            return {"tool_calls":[read("hub_read_diagnostics","hub_get_metrics")]}
        if step==4:
            return {"tool_calls":[read("hub_read_devices","hub_get_device",
                                       deviceId="7934")]}
        if step in (5,6):
            return {"tool_calls":[call("hub_search_tools",
                                       {"query":f"read evidence {step}"})]}
        if step==7:
            assert any("Evidence-coverage review" in m.get("content","")
                       for m in messages if m.get("role")=="user")
            assert "discovery_advice" in str(messages)
            return {"tool_calls":[read("hub_read_devices",
                                       "hub_list_device_events",
                                       deviceId="7934",limit=50)]}
        raise AssertionError("Extra model rounds must not be invoked")
    out=await run_native_read_agent(
        question="Investigate this device warning and its cause",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    diagnostics=out["native_diagnostics"]
    assert diagnostics["rounds"]==7
    assert diagnostics["reads_executed"]==6
    assert diagnostics["successful_reads"]==6
    assert diagnostics["causal_coverage_challenge_used"] is True
    assert diagnostics["causal_coverage_gap"] is None
    assert diagnostics["repeated_discovery"]==1
    assert diagnostics["verified_typed_ids"]["app"]==["4080"]
    assert "Calendar Notifier" in out["answer"]["text"]
    assert len(executor.calls)==6


@pytest.mark.asyncio
async def test_hub_wide_question_does_not_force_device_event_read():
    mcp=FakeMCP([READ_DIAG,DEVICE])
    executor=FakeExecutor(mcp,[{"current":{"freeMemoryKB":700000}}])
    steps=0
    async def model(messages,tools):
        nonlocal steps
        steps+=1
        if steps==1:
            return {"tool_calls":[read("hub_read_diagnostics","hub_get_metrics")]}
        return {"content":"Free memory was reported as 700000 KB."}
    out=await run_native_read_agent(
        question="Summarize memory on my hub",chat=model,mcp=mcp,
        executor=executor,max_rounds=6)
    assert out["native_diagnostics"]["causal_coverage_challenge_used"] is False
    assert out["native_diagnostics"]["rounds"]==2
    assert "700000" in out["answer"]["text"]
