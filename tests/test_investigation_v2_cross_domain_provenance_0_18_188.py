"""General READ source-provenance regression, derived from a 28 Oct live trace.

A scoped device event has two possible actors: the device reporting state
and an automation issuing a command. Do not discard the second actor.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPTool, MCPToolResult
from investigation_v2.native_provenance import (
    event_summary, source_identities, correlated_command_warnings)
from investigation_v2.native_read_agent import _payload, _guard, run_native_read_agent
from investigation_v2.native_evidence_focus import focused_highlights, focused_fallback
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor)

READ_DEVICES=MCPTool("hub_read_devices","Device reads",{
    "type":"object","properties":{
       "tool":{"type":"string","enum":["hub_list_device_events","hub_get_device"]},
       "args":{"type":"object","additionalProperties":True},
    },"required":["tool","args"]},annotations={"readOnlyHint":True})
READ_APPS=MCPTool("hub_read_apps_code","App/source reads",{
    "type":"object","properties":{
       "tool":{"type":"string","enum":["hub_get_app_config","hub_get_source"]},
       "args":{"type":"object","additionalProperties":True},
    },"required":["tool","args"]},annotations={"readOnlyHint":True})

EVENTS={"count":7,"events":[
    {"name":"command-setVolume","date":"2026-10-28T17:42:22.698+0000",
     "description":"Command called: setVolume(10)",
     "producedBy":{"appId":4080,"name":"Calendar Notifier"}},
    {"name":"command-speak","date":"2026-10-28T17:40:09.874+0000",
     "description":"Private reminder: dentist at 5:50 PM",
     "producedBy":{"appId":4080,"name":"Calendar Notifier"}},
    {"name":"command-refresh","date":"2026-10-28T18:14:54.471+0000",
     "description":"Command called: refresh()",
     "producedBy":{"appId":1679,"name":"Adhan Player"}},
    {"name":"command-refresh","date":"2026-10-28T18:14:55.533+0000",
     "producedBy":{"appId":1679,"name":"Adhan Player"}},
    {"name":"command-playTrack","date":"2026-10-28T18:11:21.750+0000",
     "description":"Command called: playTrack(https://example.invalid/private.mp3)",
     "producedBy":{"appId":1679,"name":"Adhan Player"}},
    {"name":"volume","value":"10","date":"2026-10-28T17:42:22.699+0000",
     "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
    {"name":"command-speak","date":"2026-10-28T17:50:01.407+0000",
     "description":"Private details no model should receive",
     "producedBy":{"appId":4080,"name":"Calendar Notifier"}},
]}
WARN={"entries":[
    {"type":"dev","name":"Google Nest Hub","level":"WARN",
     "message":"dev|7934|Google Nest Hub|method setVolume of child device ran for 124,842ms",
     "time":"2026-10-28 17:42:22.697"},
    {"type":"dev","name":"Google Nest Hub","level":"WARN",
     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
     "time":"2026-10-28 17:39:59.838"},
]}

def test_app_issuers_survive_scoped_event_projection_without_private_content():
    obj=_payload(MCPToolResult("hub_read_devices",{}, {},"",EVENTS),
                 "hub_list_device_events")
    assert obj["count"]==7
    assert {r["appId"] for r in obj["issuer_apps"]}=={"4080","1679"}
    assert obj["issuer_apps"][0]["commands"]["speak"]==2
    assert obj["issuer_apps"][1]["commands"]["refresh"]==2
    assert "command-setVolume" in str(obj)
    for secret in ("dentist","private.mp3","Private details"):
        assert secret not in str(obj)

def test_event_issuer_app_id_attested_only_from_host_scoped_device_read():
    assert source_identities("hub_list_device_events",EVENTS)["app"]==set()
    identity=source_identities("hub_list_device_events",EVENTS,
                               scoped_device_id="7934")
    assert identity["app"]=={"4080","1679"}
    assert identity["device"]=={"7934"}
    assert "7934" not in identity["app"]
    typed={"device":{"7934"},"app":{"4080","1679"},"driver":set()}
    denied={"tool":"hub_get_app_config","args":{"appId":"7934"}}
    accepted={"tool":"hub_get_app_config","args":{"appId":"4080"}}
    assert _guard("hub_read_apps_code",denied,{"hub_read_apps_code":READ_APPS},
                  {},{"7934","4080"},typed)=="target_id_not_verified_from_live_source"
    assert _guard("hub_read_apps_code",accepted,{"hub_read_apps_code":READ_APPS},
                  {},{"7934","4080"},typed) is None
    source={"tool":"hub_get_source","args":{"type":"driver","id":"4080"}}
    assert _guard("hub_read_apps_code",source,{"hub_read_apps_code":READ_APPS},
                  {},{"7934","4080"},typed)=="target_id_not_verified_from_live_source"
    source["args"]["type"]="app"
    assert _guard("hub_read_apps_code",source,{"hub_read_apps_code":READ_APPS},
                  {},{"7934","4080"},typed) is None

def test_same_method_command_and_warning_form_correlation_not_causal_proof():
    evt=_payload(MCPToolResult("hub_read_devices",{},{},"",EVENTS),
                 "hub_list_device_events")
    log=_payload(MCPToolResult("hub_read_diagnostics",{},{},"",WARN),
                 "hub_get_logs")
    witnesses=[
        {"read":3,"operation":"hub_get_logs","source_data":log,
         "read_filters":{"deviceId":"7934","level":"warn"}},
        {"read":6,"operation":"hub_list_device_events","source_data":evt,
         "read_filters":{"deviceId":"7934"}},
    ]
    links=correlated_command_warnings(witnesses,{"7934"})
    assert len(links)==1
    assert links[0]["appId"]=="4080"
    assert links[0]["command"]=="setvolume"
    assert links[0]["wall_clock_delta_ms"]==1
    assert links[0]["causal_proof"] is False
    assert links[0]["time_zone_alignment_verified"] is False
    result="\n".join(focused_highlights(witnesses,["7934"]))
    assert "app ID 4080" in result
    assert "app ID 1679" in result
    assert "1ms wall-clock difference" in result
    assert "causation are unverified" in result
    assert "dentist" not in result
    fallback=focused_fallback(witnesses,[],["7934"])
    assert "Calendar Notifier" in fallback
    assert "Adhan Player" in fallback
    assert "not proof" in fallback
