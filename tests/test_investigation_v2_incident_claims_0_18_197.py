"""v0.18.197: causal rank must be supported by incident-time evidence.

Replay of 28 October 23:47:15 v0.18.196 investigation:
- 11 Adhan Player refresh commands around 18:14:51-18:15:01
- 11 playTrack calls spread over multiple days
- only generic Hubitat device WARNs around 19:55:19
- concurrent device-owned buffering/idle/mediaSource event transitions
- model inferred that Adhan was the 'most material offender' without
  runtime measurement, source code or incident-time commands.
"""
from __future__ import annotations
from pathlib import Path
import sys
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, unsupported_causal_ranking,
    evidence_safe_incident_explanation)
from investigation_v2.native_app_pages import app_pages_summary
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_read_agent import _payload, run_native_read_agent
from investigation_v2.native_evidence_focus import focused_highlights
from mcp_client import MCPTool, MCPToolResult
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


WARN={"log_summary":{"warning_error_groups":[{
    "source_type":"dev","source_id":"7934",
    "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
    "oldest_returned":"2026-10-28 19:55:19.194",
    "newest_returned":"2026-10-28 19:55:19.399",
    "count":3
}]}}
def events():
    rows=[
        {"name":"status","value":"buffering",
         "date":"2026-10-28T19:55:19.193+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
        {"name":"mediaSource","value":"None",
         "date":"2026-10-28T19:55:19.395+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
        {"name":"status","value":"idle",
         "date":"2026-10-28T19:55:19.398+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
    ]
    rows.extend({
        "name":"command-refresh","date":f"2026-10-28T18:14:{51+i:02d}.247+0000"
          if i<9 else f"2026-10-28T18:15:{i-9:02d}.247+0000",
        "producedBy":{"appId":1679,"name":"Adhan Player"}}
        for i in range(11))
    rows.extend({
        "name":"command-playTrack",
        "date":f"2026-10-{18+i:02d}T11:49:02.428+0000",
        "producedBy":{"appId":1679,"name":"Adhan Player"}}
        for i in range(11))
    rows.extend([
        {"name":"command-setVolume",
         "date":"2026-10-28T17:42:22.698+0000",
         "producedBy":{"appId":4080,"name":"00 Google Calendar Notifier"}},
        {"name":"command-speak",
         "date":"2026-10-28T17:50:09.540+0000",
         "producedBy":{"appId":4080,"name":"00 Google Calendar Notifier"}}
    ])
    return rows


def evidence():
    return [
        {"read":1,"operation":"hub_get_logs","source_data":WARN,
         "read_filters":{"mode":"past","level":"warn","limit":100}},
        {"read":3,"operation":"hub_list_device_events",
         "source_data":event_summary({"events":events()}),
         "read_filters":{"deviceId":"7934","limit":100}},
    ]


def test_causal_packet_tracks_separate_burst_not_playtrack_total():
    p=incident_attribution_packet(evidence(),["7934"])
    assert p["incident_type"]=="generic_device_warning"
    assert p["device_caller_app_ids"]==["1679","4080"]
    assert p["caller_identities_verified"] is True
    assert p["app_commands_within_warning_interval"]==0
    assert p["app_commands_within_five_minutes"]==0
    assert p["nearest_app_command_gap_seconds"]>5000
    burst=next(x for x in p["observed_command_bursts"]
               if x["command"]=="command-refresh")
    assert burst["count_in_burst"]>=9
    assert burst["gap_from_warning_end_seconds"]>5900
    assert not any(x["command"]=="command-playTrack"
                   for x in p["observed_command_bursts"])
    assert [e["name"] for e in p["device_events_within_two_seconds"]]==[
        "status","mediaSource","status"]
    assert p["independent_executed_method_or_cpu_attribution"] is False


def test_post_answer_claim_gate_rejects_ranking_but_keeps_observations():
    packet=incident_attribution_packet(evidence(),["7934"])
    assert unsupported_causal_ranking(
        "The most material offender is Adhan Player and its refresh loop.",packet)
    assert unsupported_causal_ranking(
        "The warning is most plausibly driven by command/event churn.",packet)
    assert unsupported_causal_ranking(
        "Two likely drivers of the generic warning are polling and status churn.",packet)
    assert not unsupported_causal_ranking(
        "App 1679 issued 11 refresh commands earlier that day. "
        "Their contribution to the warning is unverified.",packet)
    assert not unsupported_causal_ranking(
        "No root cause was verified.",packet)
    assert not unsupported_causal_ranking("The most material offender is X.",None)
    safe=evidence_safe_incident_explanation(packet)
    assert "cannot" not in safe or "cannot" in safe
    assert "does not identify" in safe
    assert "app 1679" in safe
    assert "buffering" in safe and "idle" in safe
    assert "most likely cause" in safe
    assert "app 4080" not in safe or "4080" in safe


def test_app_pages_only_navigation_and_no_private_form_or_html():
    raw={"success":True,
         "app":{"id":1679,"name":"Adhan Player",
                "settings":{"accessToken":"SHOULD_NOT_SHOW"}},
         "primaryPage":{"name":"settingsPage","html":"PRIVATE_HTML"},
         "pages":[{"name":"settingsPage","settings":"PRIVATE_FORM"},
                  {"name":"advancedPage","url":"https://private.invalid"}],
         "note":"PRIVATE_NOTES"}
    proj=app_pages_summary(raw)
    assert proj["reported_page_count"]==2
    assert proj["returned_app_id"]=="1679"
    assert proj["primary_page"]=="settingsPage"
    assert proj["page_names"]==["settingsPage","advancedPage"]
    assert proj["settings_values_projected"] is False
    assert proj["app_page_code_inspected"] is False
    assert proj["navigation_only"] is True
    assert all(x not in str(proj) for x in
               ("SHOULD_NOT_SHOW","PRIVATE_HTML","PRIVATE_FORM",
                "PRIVATE_NOTES","private.invalid"))
    from_adapter=_payload(MCPToolResult("hub_read_apps_code",{},{},"",raw),
                          "hub_list_app_pages")
    assert from_adapter==proj
    assert not from_adapter.get("projection_empty")
    message="\n".join(focused_highlights([{
        "read":5,"operation":"hub_list_app_pages","source_data":proj,
        "read_filters":{"appId":"1679"}}],["7934"]))
    assert "navigation" in message.lower()


@pytest.mark.asyncio
async def test_live_shaped_model_conclusion_is_withheld_when_causally_ranked():
    DIAG=MCPTool("hub_read_diagnostics","Read diagnostics",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_logs"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    DEV=MCPTool("hub_read_devices","Read device histories",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_device_events"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    mcp=FakeMCP([DIAG,DEV])
    async def identities():return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    log={"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-28 19:55:19.194",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"
    }]}
    executor=FakeExecutor(mcp,[log,{"events":events()}])
    turn=0
    def call(gateway,op=None,**kwargs):
        return {"function":{"name":gateway,"arguments":{
            "tool":op,"args":kwargs
        } if op else kwargs}}
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:return {"tool_calls":[call("homebrain_find_device",
                                             name="Google Nest Hub")]}
        if turn==2:return {"tool_calls":[call("hub_read_diagnostics","hub_get_logs",
                                             mode="past",level="warn",limit=100)]}
        if turn==3:return {"tool_calls":[call("hub_read_devices",
                                             "hub_list_device_events",
                                             deviceId="7934",limit=100)]}
        if turn==4:
            assert "incident_attribution_evidence" in messages[-1]["content"]
            return {"content":(
                "The most material offender is Adhan Player. "
                "The 19:55 warning is most plausibly driven by "
                "its high-frequency refresh calls, even though "
                "they happened an hour earlier.")}
        raise AssertionError("Unexpected additional model call")
    result=await run_native_read_agent(
        question="Investigate Google Nest Hub generic warning",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    d=result["native_diagnostics"]
    assert d["successful_reads"]==2
    assert d["unsupported_causal_ranking_withheld"] is True
    assert d["incident_attribution_evidence"]["app_commands_within_warning_interval"]==0
    assert d["final_synthesis"]=="source_bound_unattributed_incident"
    assert d["model_narrative_withheld_for_unattributed_incident"] is True
    assert any(c["id"]=="generic_warning_root_cause" and c["status"]=="unverified"
               for c in d["incident_claim_ledger"])
    assert "unsupported_causal_ranking_withheld" in result["answer"]["validation_issues"]
    assert result["answer"]["human_review_required"] is True
    assert "The most material offender" not in result["answer"]["text"]
    assert "Source-grounded causal assessment" in result["answer"]["text"]
    assert "cause remains unverified" in result["answer"]["text"].lower()
    assert len(executor.calls)==2


@pytest.mark.asyncio
async def test_fact_only_model_answer_is_preserved():
    DIAG=MCPTool("hub_read_diagnostics","Read diagnostics",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_logs"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    DEV=MCPTool("hub_read_devices","Read device histories",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_device_events"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    mcp=FakeMCP([DIAG,DEV])
    async def identities():return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"entries":[{"level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-28 19:55:19.194",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}]},
        {"events":events()},
    ])
    step=0
    def tool(gateway,op=None,**kwargs):
        return {"function":{"name":gateway,"arguments":{
            "tool":op,"args":kwargs
        } if op else kwargs}}
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:return {"tool_calls":[tool("homebrain_find_device",
                                             name="Google Nest Hub")]}
        if step==2:return {"tool_calls":[tool("hub_read_diagnostics",
                                             "hub_get_logs",mode="past",
                                             level="warn",limit=100)]}
        if step==3:return {"tool_calls":[tool("hub_read_devices",
                                             "hub_list_device_events",
                                             deviceId="7934",limit=100)]}
        return {"content":"11 refresh events were observed earlier. "
                          "Their causal connection to the generic warning is unknown."}
    result=await run_native_read_agent(
        question="Review this device's warnings",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    assert result["native_diagnostics"]["unsupported_causal_ranking_withheld"] is False
    assert "11 command-refresh events" in result["answer"]["text"]
    assert result["native_diagnostics"]["model_narrative_withheld_for_unattributed_incident"] is True
    assert "unattributed_incident_model_narrative_withheld" in result["answer"]["validation_issues"]
