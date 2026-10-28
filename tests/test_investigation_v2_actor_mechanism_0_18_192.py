"""v0.18.192: source-specific driver mechanism outranks later generic warnings.

28 Oct v0.18.191 live sample:
- runQ WARN 17:04-17:58 with commands issued by apps 1679, 4080
- generic hub-load WARN 19:32-19:55, no matching issued commands
- subsequent command-refresh read repeats 11 events already in first page.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(ROOT))
from investigation_v2.native_evidence_coverage import (
    gap_for_target, repeated_event_evidence,
)
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_evidence_focus import focused_fallback
from investigation_v2.native_read_agent import run_native_read_agent
from mcp_client import MCPTool
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def read(n,operation,data,filters=None):
    return {"read":n,"operation":operation,"source_data":data,
            "read_filters":filters or {}}


def warnings():
    return {"log_summary":{"warning_error_groups":[
        {"source_type":"dev","source_id":"7934",
         "message":"dev|7934|Nest|method runQ ran for 147,429ms",
         "oldest_returned":"2026-10-28 17:04:48.106",
         "newest_returned":"2026-10-28 17:58:24.126"},
        {"source_type":"dev","source_id":"7934",
         "message":"dev|7934|Nest|Device 7934 generates excessive hub load",
         "oldest_returned":"2026-10-28 19:32:20.613",
         "newest_returned":"2026-10-28 19:55:19.399"},
    ]}}


def raw_events():
    return {"events":[
        {"name":"status","date":"2026-10-28T19:55:19.398+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"},
         "value":"idle"},
        {"name":"command-refresh","date":"2026-10-28T18:15:01.713+0000",
         "producedBy":{"appId":"1679","name":"Adhan Player"}},
        {"name":"command-refresh","date":"2026-10-28T18:14:58.731+0000",
         "producedBy":{"appId":"1679","name":"Adhan Player"}},
        {"name":"command-setVolume","date":"2026-10-28T17:42:22.698+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-speak","date":"2026-10-28T17:40:01.714+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-playTrack","date":"2026-10-28T17:00:27.531+0000",
         "producedBy":{"appId":"1679","name":"Adhan Player"}},
    ]}


def evidence():
    return [
        read(4,"hub_get_logs",warnings(),{"mode":"past","level":"warn"}),
        read(5,"hub_list_device_events",event_summary(raw_events()),
             {"deviceId":"7934","limit":50}),
    ]


def test_internal_driver_mechanism_priority_with_later_generic_warn():
    gap=gap_for_target(evidence(),["7934"],can_read_events=True)
    assert gap is not None
    assert gap["kind"]=="target_driver_execution_mechanism_unverified"
    assert gap["method"]=="runQ"
    assert gap["observed_calling_app_ids"]==["1679","4080"]
    assert gap["actor_provenance_verified"] is True
    assert gap["candidate_read"]=="hub_get_app_config"
    assert "command-runQ" not in str(gap)
    assert gap["unattributed_generic_warning_window"]["oldest"]=="2026-10-28 19:32:20.613"
    assert gap["unattributed_generic_warning_window"]["newest"]=="2026-10-28 19:55:19.399"


def test_generic_warning_without_any_attested_command_still_unattributed():
    only={"log_summary":{"warning_error_groups":warnings()["log_summary"]["warning_error_groups"][1:]}}
    hist=event_summary(raw_events())
    gap=gap_for_target([read(4,"hub_get_logs",only),
                        read(5,"hub_list_device_events",hist,{"deviceId":"7934"})],
                       ["7934"],can_read_events=True)
    assert gap["kind"]=="target_warning_command_issuer_unverified"
    assert gap["method"] is None


def test_command_refresh_filtered_subset_of_prior_events_is_redundant():
    all_events=event_summary(raw_events())
    subset=event_summary({"events":[raw_events()["events"][1],raw_events()["events"][2]]})
    prior=[read(5,"hub_list_device_events",all_events,{"deviceId":"7934","limit":50})]
    assert repeated_event_evidence(prior,subset,scoped_device_id="7934")
    assert not repeated_event_evidence(prior,subset,scoped_device_id="7103")
    new=event_summary({"events":[{"name":"command-refresh",
          "date":"2026-10-28T18:15:08.100+0000",
          "producedBy":{"appId":"1679","name":"Adhan Player"}}]})
    assert not repeated_event_evidence(prior,new,scoped_device_id="7934")
    partial={**subset,"count":100}
    assert not repeated_event_evidence(prior,partial,scoped_device_id="7934")


def test_fallback_app_issuers_deduplicate_across_history_reads():
    e=evidence()
    e.append(read(10,"hub_list_device_events",event_summary(
        {"events":raw_events()["events"][1:3]}),
        {"deviceId":"7934","attribute":"command-refresh"}))
    text=focused_fallback(e,[],["7934"])
    assert text is not None
    conclusion=text.split("Automations observed issuing commands to this device:",1)[1]
    assert conclusion.count("(app 1679)")==1
    assert conclusion.count("(app 4080)")==1
    assert "not proof" in text


@pytest.mark.asyncio
async def test_missing_device_id_reply_has_verified_target_hint_no_execution():
    device=MCPTool("hub_read_devices","Device read",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_device"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    mcp=FakeMCP([device])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[])
    counter=0
    async def model(messages,tools):
        nonlocal counter
        counter+=1
        if counter==1:
            return {"tool_calls":[{"function":{"name":"homebrain_find_device",
                                               "arguments":{"name":"Google Nest Hub"}}}]}
        if counter==2:
            return {"tool_calls":[{"function":{"name":"hub_read_devices",
               "arguments":{"tool":"hub_get_device","args":{"mode":"details"}}}}]}
        assert "deviceId=7934" in messages[-1]["content"]
        return {"content":"The detail read was not attempted because deviceId was missing."}
    out=await run_native_read_agent(question="Inspect Google Nest Hub",
                                   chat=model,mcp=mcp,executor=executor)
    assert executor.calls==[]
    assert out["native_diagnostics"]["reads_executed"]==0
    assert any(x.get("code")=="missing_required_operation_fields"
               for x in out["native_diagnostics"]["failures"])
