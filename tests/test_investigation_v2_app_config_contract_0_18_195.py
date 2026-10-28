"""v0.18.195 nested app-page evidence and source READ contract repair.

28 Oct v0.18.194 test: hub_get_app_config(appId=1679) succeeded but
raw nested 'app' was discarded; two hub_get_source attempts omitted
id and type and then stopped. Model still selects every read itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool, MCPToolResult
from investigation_v2.native_read_agent import (
    _payload, run_native_read_agent)
from investigation_v2.native_read_contracts import read_contract_feedback
from investigation_v2.native_evidence_focus import focused_highlights
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG)

READ_DEV=MCPTool("hub_read_devices","Device data",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_list_device_events","hub_get_device"]},
        "args":{"type":"object","additionalProperties":True}},
    "required":["tool","args"]},annotations={"readOnlyHint":True})
READ_CODE=MCPTool("hub_read_apps_code","Apps and source",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_app_config","hub_get_source"]},
        "args":{"type":"object","additionalProperties":True}},
    "required":["tool","args"]},annotations={"readOnlyHint":True})

CONFIG={
    "success":True,
    "page":{"name":"settingsPage"},
    "app":{
        "id":1679,"name":"Adhan Player",
        "label":"Adhan Player","enabled":True,"paused":False,
        "type":"userApp",
        "settings":{
            "refreshInterval":10,"logDebug":True,
            "accessToken":"PRIVATE_CREDENTIAL",
            "accountEmail":"private@example.test"},
        "inputs":{"speechDevice":7934,"password":"PRIVATE_VALUE"}},
    "childApps":[{"id":7829,"name":"Child one"}],
    "endpoint":"https://local.private.invalid/api",
    "settingsKeyCount":4,
    "settingsNote":"PRIVATE_PERSONAL_NOTE",
}
WARN={"entries":[{"level":"WARN","type":"dev",
    "name":"Google Nest Hub",
    "time":"2026-10-28 19:55:19.194",
    "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}]}
EVENTS={"events":[{
    "name":"command-refresh","date":"2026-10-28T18:15:01.713+0000",
    "producedBy":{"appId":1679,"name":"Adhan Player"}},
    {"name":"command-setVolume",
     "date":"2026-10-28T17:42:22.698+0000",
     "producedBy":{"appId":4080,"name":"Google Calendar Notifier"}}]}


def call(gateway, tool=None, **args):
    if tool is None:
        return {"function":{"name":gateway,"arguments":args}}
    return {"function":{"name":gateway,"arguments":{"tool":tool,"args":args}}}


def test_nested_app_page_is_interpreted_without_secret_values():
    output=_payload(MCPToolResult("hub_read_apps_code",{},{},"",CONFIG),
                    "hub_get_app_config")
    assert output["id"]=="1679"
    assert output["name"]=="Adhan Player"
    assert output["app_section_present"] is True
    assert output["page_name"]=="settingsPage"
    assert output["enabled"] is True
    assert output["paused"] is False
    assert output["settings_key_count"]==4
    assert output["child_app_count"]==1
    assert output["child_app_ids"]==["7829"]
    assert output["app_settings_field_names"]==["refreshInterval","logDebug"]
    assert output["app_inputs_field_names"]==["speechDevice"]
    assert output["settings_values_projected"] is False
    assert output["source_complete"] is False
    assert output.get("projection_empty") is not True
    for private in ("PRIVATE_", "private@", "private.invalid", "settingsNote",
                    "accessToken", "accountEmail", "password", "endpoint"):
        assert private not in str(output)


def test_legacy_flat_app_config_still_retains_identity():
    raw={"id":"4080","label":"Google Calendar Notifier",
         "settings":{"sendNotification":True,"oauthToken":"PRIVATE"}}
    info=_payload(MCPToolResult("hub_read_apps_code",{},{},"",raw),
                  "hub_get_app_config")
    assert info["id"]=="4080"
    assert info["label"]=="Google Calendar Notifier"
    assert info["settings_field_names"]==["sendNotification"]
    assert info["app_section_present"] is False
    assert "PRIVATE" not in str(info)


def test_missing_source_fields_present_only_verified_typed_ids():
    typed={"device":{"7934"},"app":{"1679","4080"},"driver":set()}
    incomplete={"tool":"hub_get_source","args":{}}
    r=read_contract_feedback("hub_read_apps_code",incomplete,typed)
    assert r["missing_required_fields"]==["id","type"]
    assert r["required_shape"]["args"]["type"]=="app|driver"
    assert r["verified_id_choices"]["app"]==["1679","4080"]
    assert r["verified_id_choices"]["driver"]==[]
    assert "7934" not in str(r)
    assert r["host_execution_attempted"] is False
    assert read_contract_feedback("hub_read_apps_code",{
        "tool":"hub_get_source","args":{"id":"1679","type":"app"}},typed) is None


@pytest.mark.asyncio
async def test_model_repairs_one_source_call_using_verified_app_identity():
    mcp=FakeMCP([READ_DEV,READ_CODE,READ_DIAG])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[WARN,EVENTS,CONFIG,{
        "id":"1679","type":"app","name":"Adhan Player",
        "source":"def refresh() { privateApiToken='NEVER_SHOW'; runIn(60,'refresh') }"
    }])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[call("homebrain_find_device",
                                       name="Google Nest Hub")]}
        if step==2:
            return {"tool_calls":[call("hub_read_diagnostics","hub_get_logs",
                                       mode="past",level="warn",deviceId="7934")]}
        if step==3:
            return {"tool_calls":[call("hub_read_devices",
                                       "hub_list_device_events",
                                       deviceId="7934",limit=50)]}
        if step==4:
            return {"tool_calls":[call("hub_read_apps_code",
                                       "hub_get_app_config",appId="1679")]}
        if step==5:
            assert '"requested_app_id": "1679"' in messages[-1]["content"]
            assert "Adhan Player" in messages[-1]["content"]
            assert "PRIVATE_CREDENTIAL" not in str(messages)
            return {"tool_calls":[call("hub_read_apps_code",
                                       "hub_get_source")]}
        if step==6:
            assert "required_read_contract" in messages[-1]["content"]
            assert '"type": "app|driver"' in messages[-1]["content"]
            assert '"1679"' in messages[-1]["content"]
            assert '"4080"' in messages[-1]["content"]
            return {"tool_calls":[call("hub_read_apps_code",
                                       "hub_get_source",type="app",id="1679")]}
        if step==7:
            assert "source_content_available" in messages[-1]["content"]
            assert "NEVER_SHOW" not in str(messages)
            return {"content":("Two calling apps are verified. The app source "
                               "was obtained as metadata only; the internal "
                               "driver cause remains unverified.")}
        raise AssertionError("Unexpected model call")
    result=await run_native_read_agent(question="Investigate the Google Nest Hub warnings",
                                       chat=model,mcp=mcp,executor=executor,
                                       max_rounds=8)
    d=result["native_diagnostics"]
    assert d["successful_reads"]==4
    assert d["reads_executed"]==4
    assert d["verified_typed_ids"]["app"]==["1679","4080"]
    assert [entry[1]["tool"] for entry in executor.calls]==[
        "hub_get_logs","hub_list_device_events","hub_get_app_config",
        "hub_get_source"]
    assert result["answer"]["validation_issues"]
    app_receipt=next(w for w in d["read_summaries"]
                     if w["operation"]=="hub_get_app_config")
    assert app_receipt["source_data"]["requested_app_id_verified"] is True
    assert app_receipt["source_data"]["source_app_id_matches_request"] is True
    text="\n".join(focused_highlights(d["read_summaries"],["7934"]))
    assert "verified app config READ for app ID 1679" in text
    assert "Adhan Player" in text
    assert "PRIVATE_CREDENTIAL" not in str(result)
    assert "NEVER_SHOW" not in str(result)


def test_app_config_with_mismatched_source_id_never_claims_identity_match():
    raw={"app":{"id":"9999","name":"Different app"},
         "page":{"name":"settingsPage"}}
    projected=_payload(MCPToolResult("hub_read_apps_code",{},{},"",raw),
                       "hub_get_app_config")
    projected["requested_app_id"]="1679"
    projected["requested_app_id_verified"]=True
    projected["source_app_id_matches_request"]=False
    w=[{"read":1,"operation":"hub_get_app_config",
        "read_filters":{"appId":"1679"},"source_data":projected}]
    lines="\n".join(focused_highlights(w,["7934"]))
    assert "does NOT match" in lines
    assert "verified app config READ" not in lines
