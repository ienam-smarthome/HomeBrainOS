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
    event_summary, source_identities, correlated_command_warnings,
    dependent_summary, driver_summary)
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



def call(gateway, operation, **args):
    return {"function":{"name":gateway,"arguments":{
        "tool":operation,"args":args}}}


@pytest.mark.asyncio
async def test_model_can_follow_device_event_issuers_into_two_app_configs_and_source():
    mcp=FakeMCP([READ_DEVICES,READ_APPS])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        EVENTS,
        {"appId":"4080","name":"Calendar Notifier","enabled":True,
         "settings":{"targetDeviceId":"7934","apiKey":"private"}},
        {"appId":"1679","name":"Adhan Player","enabled":True},
        {"id":"4080","type":"app","name":"Calendar Notifier",
         "source":"def handler():\n    callDevice(...)\n"},
    ])
    round_no=0
    async def model(messages,tools):
        nonlocal round_no
        round_no+=1
        if round_no==1:
            return {"tool_calls":[{"function":{"name":"homebrain_find_device",
                                                "arguments":{"name":"Google Nest Hub"}}}]}
        if round_no==2:
            return {"tool_calls":[call("hub_read_devices",
                                      "hub_list_device_events",
                                      deviceId="7934",limit=50)]}
        if round_no==3:
            # Both app IDs were independently attested by producedBy.appId.
            assert '"appId": "4080"' in messages[-1]["content"]
            return {"tool_calls":[
                call("hub_read_apps_code","hub_get_app_config",appId="4080"),
                call("hub_read_apps_code","hub_get_app_config",appId="1679"),
            ]}
        if round_no==4:
            return {"tool_calls":[
                call("hub_read_apps_code","hub_get_source",type="app",id="4080")]}
        return {"content":("Two independently attested apps issued commands "
                           "to device 7934, but the driver execution cause "
                           "remains unverified.")}
    result=await run_native_read_agent(
        question="Which automations interact with the Google Nest Hub?",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    assert result["native_diagnostics"]["successful_reads"]==4
    assert result["native_diagnostics"]["reads_executed"]==4
    assert result["native_diagnostics"]["verified_typed_ids"]["app"]==["1679","4080"]
    assert result["native_diagnostics"]["verified_typed_ids"]["device"]==["7934"]
    assert [c[1]["tool"] for c in executor.calls]==[
        "hub_list_device_events","hub_get_app_config",
        "hub_get_app_config","hub_get_source"]
    assert result["native_diagnostics"]["failures"]==[]
    assert "two" in result["answer"]["text"].lower()


def test_source_ids_from_dependencies_and_drivers_are_typed_not_interchangeable():
    from investigation_v2.native_provenance import (
        dependent_summary, driver_summary, source_identities)
    dependency={"deviceId":"7934","appsUsing":[
        {"id":4080,"name":"Calendar Notifier"},
        {"appId":"1679","label":"Adhan Player"}]}
    assert source_identities("hub_list_device_dependents",dependency)["app"]==set()
    attest=source_identities("hub_list_device_dependents",dependency,
                              scoped_device_id="7934")
    assert attest["app"]=={"4080","1679"}
    assert "apps_using" in dependent_summary(dependency)
    drivers={"drivers":[{"id":"3907","name":"Google Cast"},
                        {"id":"3908","name":"Tasmota Device"}]}
    assert source_identities("hub_list_drivers",drivers)["driver"]=={"3907","3908"}
    assert "3907" not in attest["app"]
    assert driver_summary(drivers)["drivers"][0]["driverId"]=="3907"
