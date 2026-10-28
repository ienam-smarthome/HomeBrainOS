"""Live-derived causal evidence tests: callers vs internal driver mechanism.

A 28 October 2026 trace contains app-issued setVolume at 17:42:22.698,
driver-method setVolume WARN at 17:42:22.697 and broad runQ WARN windows.
runQ is not an observed command; inventing command-runQ is incorrect.
"""
from __future__ import annotations
import sys
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_evidence_coverage import gap_for_target
from investigation_v2.native_tool_protocol import operation_problem, guidance_for
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_read_agent import run_native_read_agent
from mcp_client import MCPTool
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor
import pytest

WARN={
    "log_summary":{"warning_error_groups":[
        {"source_id":"7934","source_type":"dev","level":"WARN",
         "message":"method runQ of child device ran for 147,429ms",
         "oldest_returned":"2026-10-28 17:04:48.106",
         "newest_returned":"2026-10-28 17:58:24.126"},
        {"source_id":"7934","source_type":"dev","level":"WARN",
         "message":"method setVolume of child device ran for 124,842ms",
         "oldest_returned":"2026-10-28 17:42:22.697",
         "newest_returned":"2026-10-28 17:42:22.697"},
    ]}
}
EVENTS={"events":[
    {"name":"command-setVolume","date":"2026-10-28T17:42:22.698+0000",
     "producedBy":{"appId":4080,"name":"00 Google Calendar Notifier"}},
    {"name":"command-playTrack","date":"2026-10-28T17:00:27.531+0000",
     "producedBy":{"appId":1679,
       "name":"Adhan Player span style='color:green' (LPT API: Fajr-05:08"}},
    {"name":"status","date":"2026-10-28T19:55:19.398+0000",
     "producedBy":{"deviceId":7934,"name":"Google Nest Hub"}},
]}
def witness(read,op,data,filters=None):
    return {"read":read,"operation":op,"source_data":data,"read_filters":filters or {}}


def test_known_command_issuers_not_mislabeled_unknown_due_to_runq():
    events=event_summary(EVENTS)
    receipts=[witness(1,"hub_get_logs",WARN),
              witness(2,"hub_list_device_events",events,{"deviceId":"7934"})]
    gap=gap_for_target(receipts,["7934"],can_read_events=True)
    assert gap is not None
    assert gap["kind"]=="target_driver_execution_mechanism_unverified"
    assert gap["actor_provenance_verified"] is True
    assert gap["observed_calling_app_ids"]==["1679","4080"]
    assert gap["method"]=="runQ"
    assert gap["candidate_read"]=="hub_get_app_config"
    assert gap["candidate_filters"]["appId"] in ("1679","4080")
    assert "command-runQ" not in str(gap)


def test_direct_matching_command_with_only_setvolume_is_not_an_issuer_gap():
    only={"log_summary":{"warning_error_groups":[WARN["log_summary"]["warning_error_groups"][1]]}}
    events=event_summary(EVENTS)
    assert gap_for_target([
        witness(1,"hub_get_logs",only),
        witness(2,"hub_list_device_events",events,{"deviceId":"7934"})
    ],["7934"],can_read_events=True) is None


def test_truly_missing_command_history_still_gets_bounded_history_probe():
    status_only=event_summary({"events":[EVENTS["events"][-1]]})
    gap=gap_for_target([
        witness(1,"hub_get_logs",WARN),
        witness(2,"hub_list_device_events",status_only,{"deviceId":"7934"})
    ],["7934"],can_read_events=True)
    assert gap["kind"]=="target_warning_event_window_uncovered"
    assert gap["candidate_read"]=="hub_list_device_events"


def test_driver_catalogue_does_not_take_device_id():
    call={"tool":"hub_list_drivers","args":{"deviceId":"7934"}}
    assert operation_problem("hub_read_apps_code",call)=="catalog_device_filter_unsupported"
    assert "hub_get_app_config" in guidance_for("catalog_device_filter_unsupported")
    assert operation_problem("hub_read_apps_code",{"tool":"hub_list_drivers","args":{}}) is None


def test_event_issuer_names_strip_html_rich_text_remnants():
    item=event_summary(EVENTS)
    by_id={a["appId"]:a for a in item["issuer_apps"]}
    assert by_id["1679"]["name"]=="Adhan Player"
    assert by_id["4080"]["name"]=="00 Google Calendar Notifier"
    assert all("span style" not in str(a) for a in item["issuer_apps"])


@pytest.mark.asyncio
async def test_normal_answer_discloses_driver_mechanism_not_unknown_caller():
    device_tool=MCPTool("hub_read_devices","Device reads",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_device_events"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    diagnostic_tool=MCPTool("hub_read_diagnostics","Diagnostic reads",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_logs"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    mcp=FakeMCP([device_tool,diagnostic_tool])
    async def get_ids():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=get_ids
    logs={"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-28 17:04:48.106",
        "message":"dev|7934|Google Nest Hub|method runQ ran for 147,429ms"
    },{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-28 17:42:22.697",
        "message":"dev|7934|Google Nest Hub|method setVolume ran for 124,842ms"
    }]}
    executor=FakeExecutor(mcp,[logs,EVENTS])
    turn=0
    def op(gateway,operation,**args):
        return {"function":{"name":gateway,"arguments":{
            "tool":operation,"args":args}}}
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:return {"tool_calls":[{"function":{
            "name":"homebrain_find_device","arguments":{"name":"Google Nest Hub"}}}]}
        if turn==2:return {"tool_calls":[op("hub_read_diagnostics","hub_get_logs",
                              level="warn",mode="past",deviceId="7934")]}
        if turn==3:return {"tool_calls":[op("hub_read_devices","hub_list_device_events",
                              deviceId="7934",limit=50)]}
        return {"content":"The caller apps are verified; the driver's internal runQ cause is unverified."}
    result=await run_native_read_agent(
        question="Why does this device have slow methods?",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    # Source report preserves distinct actor/mechanism uncertainty.
    assert "Verified callers; internal driver mechanism unresolved" in result["answer"]["text"]
    assert "driver_execution_cause_unverified" in result["answer"]["validation_issues"]
    assert "warning_window_actor_provenance_unverified" not in result["answer"]["validation_issues"]
    assert "command-runQ" not in result["answer"]["text"]
