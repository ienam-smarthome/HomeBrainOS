"""Regression: device-centric V2 live replay must retain its verified subject."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPTool
from investigation_v2.native_focus_anchor import verified_device_focus
from investigation_v2.native_claim_verifier import claim_catalog
from investigation_v2.native_causal_claim_audit import incident_attribution_packet
from investigation_v2.native_incident_cooccurrence import incident_state_cooccurrences
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def test_verified_explicit_id_anchors_but_unrelated_audit_never_anchors():
    source={"id":"7934","label":"Google Nest Hub - [Google Nest Hub]"}
    assert verified_device_focus(
        "Investigate Google Nest Hub (device 7934)", "hub_get_device",
        {"deviceId":"7934"},source,{"7934"}
    ) == {"device_id":"7934","identity_basis":"explicit_verified_device_id"}
    assert verified_device_focus(
        "Review hub-wide errors", "hub_get_device",
        {"deviceId":"7934"},source,{"7934"}
    ) is None


def test_verified_name_anchors_without_id_in_question():
    assert verified_device_focus(
        "Why does Google Nest Hub show load warnings?", "hub_get_device",
        {"deviceId":"7934"},
        {"id":"7934","name":"Google Nest Hub - [Google Nest Hub]"}, {"7934"}
    ) == {"device_id":"7934","identity_basis":"explicit_verified_device_name"}


@pytest.mark.parametrize("source,verified",[
    ({"id":"7103","name":"Google Nest Hub"},{"7934"}),
    ({"id":"7934","name":"Google Nest Hub"},set()),
])
def test_no_focus_without_both_verified_id_and_matching_result(source,verified):
    assert verified_device_focus(
        "Investigate device 7934", "hub_get_device",
        {"deviceId":"7934"},source,verified) is None
    assert verified_device_focus(
        "Investigate device 7934", "hub_get_logs",
        {"deviceId":"7934"},source,{"7934"}) is None


def test_device_focus_filters_unrelated_warnings_and_recovers_timestamp_match():
    logs=compact_logs({"entries":[
        {"level":"WARN","type":"dev","name":"Bedroom 3 Mesh",
         "time":"2026-10-29 08:32:24.724",
         "message":"dev|7103|Bedroom 3 Mesh|Watchdog fired"},
        {"level":"WARN","type":"dev","name":"Google Nest Hub",
         "time":"2026-10-29 06:01:28.979",
         "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
    ]})
    witnesses=[
        {"read":1,"operation":"hub_get_device","read_filters":{"deviceId":"7934"},
         "source_data":{"id":"7934","attributes":[{"name":"status","value":"idle"}]}},
        {"read":2,"operation":"hub_get_logs","read_filters":{},
         "source_data":{"log_summary":logs}},
        {"read":3,"operation":"hub_list_device_events",
         "read_filters":{"deviceId":"7934"},
         "source_data":{"events":[{
             "name":"volume","value":"50",
             "date":"2026-10-29T06:01:28.979+0000",
             "producedBy":{"deviceId":"7934"},
         }]}}
    ]
    catalog=claim_catalog(witnesses,["7934"])
    assert all(c["scope"]!="7103" for c in catalog)
    assert any(c["scope"]=="7934" and c["kind"]=="warning" for c in catalog)
    packet=incident_attribution_packet(witnesses,["7934"])
    assert packet["warning_state_correlations"]["warnings_with_nearby_state_in_returned_sample"]==1
    assert packet["warning_state_correlations"]["instances"][0]["coincident_states"][0]["value"]=="50"


def _read(name, ops):
    return MCPTool(name, "READ ONLY", {
        "type":"object","properties":{
            "tool":{"type":"string","enum":ops},
            "args":{"type":"object","additionalProperties":True},
        }, "required":["tool","args"]
    },annotations={"readOnlyHint":True})


def _call(gateway,op,**args):
    return {"function":{"name":gateway,"arguments":{"tool":op,"args":args}}}


@pytest.mark.asyncio
async def test_complete_agent_keeps_device_focus_and_skips_discarded_synthesis():
    mcp=FakeMCP([
        _read("hub_read_devices",["hub_get_device","hub_list_device_events"]),
        _read("hub_read_diagnostics",["hub_get_logs"]),
    ])
    async def identities():
        return [{"id":"7934","name":"Google Nest Hub - [Google Nest Hub]",
                 "label":"Google Nest Hub - [Google Nest Hub]"}]
    mcp.get_device_identities=identities
    raw_warnings={"entries":[
        {"level":"WARN","type":"dev","name":"Ikea bedroom 3",
         "time":"2026-10-29 08:32:29.017",
         "message":"dev|3951|Ikea bedroom 3|Ikea bedroom 3 ... pong"},
        {"level":"WARN","type":"dev","name":"Google Nest Hub",
         "time":"2026-10-29 06:01:28.979",
         "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
    ]}
    events={"events":[{
        "name":"volume","value":"50",
        "date":"2026-10-29T06:01:28.979+0000",
        "producedBy":{"deviceId":"7934","name":"Google Nest Hub"},
    }]}
    executor=FakeExecutor(mcp,[
        {"id":"7934","name":"Google Nest Hub - [Google Nest Hub]",
         "label":"Google Nest Hub - [Google Nest Hub]",
         "attributes":[{"name":"networkStatus","value":"online"}]},
        raw_warnings, events,
    ])
    turns=0
    async def model(messages,tools):
        nonlocal turns
        turns+=1
        assert tools, "No discarded final synthesis is needed"
        if turns==1:
            return {"tool_calls":[_call("hub_read_devices","hub_get_device",deviceId="7934")]}
        if turns==2:
            return {"tool_calls":[
                _call("hub_read_diagnostics","hub_get_logs",
                      deviceId="7934",level="warn",mode="past",limit=100),
                _call("hub_read_devices","hub_list_device_events",deviceId="7934",limit=50),
            ]}
        raise AssertionError("Unexpected model-only follow-up")
    result=await run_native_read_agent(
        question="Investigate Google Nest Hub (device 7934) excessive hub-load warning",
        mcp=mcp,executor=executor,chat=model,max_rounds=3,max_reads=3)
    diag=result["native_diagnostics"]
    assert turns==2
    assert diag["focus_ids"]==["7934"]
    assert diag["verified_focus_receipts"]==[{
        "read":1,"device_id":"7934","identity_basis":"explicit_verified_device_id"}]
    assert diag["incident_attribution_evidence"]["warning_state_correlations"][
        "warnings_with_nearby_state_in_returned_sample"]==1
    assert diag["final_synthesis_ms"]==0
    assert diag["final_synthesis_skipped_reason"]=="host_authoritative_incident_evidence"
    assert "volume=50" in result["answer"]["text"]
    assert "Ikea bedroom 3 reported warning" not in result["answer"]["text"]
    assert len(executor.calls)==3
