"""Regression for a source-observed device caller vs unattributed generic WARN.

The live 28 October v0.18.192 test returned exactly three generic Nest Hub
load WARN rows near 19:55, whereas independently attested device commands
from two apps ended around 18:15 / 17:51. Those issuers cannot be erased,
but neither can be claimed responsible for a later generic warning.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(ROOT))

from investigation_v2.native_evidence_coverage import gap_for_target
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_evidence_focus import focused_fallback, focused_highlights
from investigation_v2.native_read_agent import _payload, run_native_read_agent
from investigation_v2.native_tool_protocol import guidance_for
from investigation_v2.native_metrics_evidence import project_memory_history
from mcp_client import MCPTool, MCPToolResult
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


WARNINGS={"entries":[
    {"level":"WARN","type":"dev","name":"Google Nest Hub",
     "time":"2026-10-28 19:55:19.194",
     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
    {"level":"WARN","type":"dev","name":"Google Nest Hub",
     "time":"2026-10-28 19:55:19.250",
     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
    {"level":"WARN","type":"dev","name":"Google Nest Hub",
     "time":"2026-10-28 19:55:19.399",
     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
]}


def history():
    entries=[
        {"name":"status","date":"2026-10-28T19:55:19.398+0000",
         "value":"idle","producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
        {"name":"command-refresh","date":"2026-10-28T18:15:01.713+0000",
         "producedBy":{"appId":1679,"name":"Adhan Player"}},
        {"name":"command-setVolume","date":"2026-10-28T17:42:22.698+0000",
         "producedBy":{"appId":4080,"name":"00 Google Calendar Notifier"}},
        {"name":"command-speak","date":"2026-10-28T17:40:01.714+0000",
         "producedBy":{"appId":4080,"name":"00 Google Calendar Notifier"}},
    ]
    # The gateway's 92 historical events include 80 projected rows; keep
    # this source cap distinct from the command issuer summary.
    entries.extend(
        {"name":"status","date":f"2026-10-23T04:{18+i//60:02d}:{i%60:02d}.258+0100",
         "value":"online","producedBy":{"deviceId":"7934","name":"Google Nest Hub"}}
        for i in range(88)
    )
    return {"events":entries}


def witness(idx, op, data, filt=None):
    return {"read":idx,"operation":op,"source_data":data,
            "read_filters":filt or {}}


def observations():
    wlog=_payload(MCPToolResult("hub_read_diagnostics",{},{},"",WARNINGS),
                  "hub_get_logs")
    evt=event_summary(history())
    return [
        witness(2,"hub_get_logs",wlog,{"deviceId":"7934","level":"warn","mode":"past"}),
        witness(3,"hub_list_device_events",evt,{"deviceId":"7934","limit":100}),
        witness(4,"hub_get_device",{"id":"7934",
                 "attributes":[{"name":"networkStatus","value":"online"},
                               {"name":"status","value":"idle"}]},
                 {"deviceId":"7934"}),
    ]


def test_generic_warning_distinguishes_verified_callers_from_incident_source():
    gap=gap_for_target(observations(),["7934"],can_read_events=True)
    assert gap is not None
    assert gap["kind"]=="target_generic_warning_origin_unverified"
    assert gap["device_command_issuers_verified"] is True
    assert gap["incident_window_issuer_verified"] is False
    assert gap["observed_calling_app_ids"]==["1679","4080"]
    # Current occurrence is the latest source-reported WARN timestamp, not
    # the continuous min-max span of multiple grouped warnings.
    assert gap["warning_window"]["oldest"]=="2026-10-28T19:55:19.399000"
    assert gap["warning_window"]["newest"]=="2026-10-28T19:55:19.399000"
    # A target-scoped WARN read already exists. Suggesting the same broad
    # query with only a larger limit would contradict the log-scope guard.
    assert gap["candidate_read"] is None
    assert gap["candidate_filters"] == {}
    assert "command-runQ" not in str(gap)
    assert "target_warning_command_issuer_unverified" not in str(gap)


def test_generic_warning_fallback_never_claims_slow_method_as_measured():
    report=focused_fallback(observations(),[],["7934"])
    assert "generic excessive-load warnings" in report
    assert "does not include an independently timed slow-driver method" in report
    assert "Adhan Player" in report and "Google Calendar Notifier" in report
    assert "not proof" in report
    assert "slow driver execution" not in report


def test_event_history_projection_discloses_80_of_92_cap():
    out=event_summary(history())
    assert out["count"]==92
    assert out["returned_event_rows"]==80
    assert out["event_rows_omitted_from_model"]==12
    lines=focused_highlights([
        witness(3,"hub_list_device_events",out,{"deviceId":"7934"})
    ],["7934"])
    assert "80 projected from 92" in "\n".join(lines)


def test_memory_history_reports_actual_numbers_or_timestamp_only_uncertainty():
    raw={"entries":[
        {"timestamp":"10-28 19:45:00","freeMemoryMB":834.2,
         "cpuLoad":0.65,"token":"NEVER_ECHO"},
        {"timestamp":"10-28 19:50:00","freeMemoryMB":832.0,
         "cpuLoad":0.70,"endpoint":"https://private.invalid"},
    ],"summary":{"truncated":True}}
    data=project_memory_history(raw)
    assert data["numeric_observation_rows"]==2
    assert data["entries"][0]["freeMemoryMB"]==834.2
    assert data["entries"][0]["cpuLoad"]==0.65
    assert data["summary"]["truncated"] is True
    assert "NEVER_ECHO" not in str(data)
    assert "private.invalid" not in str(data)
    source=_payload(MCPToolResult("hub_read_diagnostics",{},{},"",raw),
                    "hub_get_memory_history")
    assert source["numeric_observation_rows"]==2

    no_metrics=project_memory_history({"entries":[
        {"timestamp":"10-28 19:45:00"},
        {"timestamp":"10-28 19:50:00"}]})
    assert no_metrics["history_numeric_values_unavailable"] is True
    assert no_metrics["numeric_observation_rows"]==0


def test_operation_mismatch_guidance_identifies_correct_read_gateway():
    advice=guidance_for("operation_not_independently_discovered")
    assert "hub_read_devices" in advice
    assert "hub_read_apps_code" in advice


@pytest.mark.asyncio
async def test_model_receives_source_gap_while_round_budget_remains():
    devices=MCPTool("hub_read_devices","Read devices",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_device",
                                           "hub_list_device_events"]},
            "args":{"type":"object","additionalProperties":True},
        },"required":["tool","args"]},annotations={"readOnlyHint":True})
    diagnostics=MCPTool("hub_read_diagnostics","Read logs",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_logs"]},
            "args":{"type":"object","additionalProperties":True},
        },"required":["tool","args"]},annotations={"readOnlyHint":True})
    mcp=FakeMCP([devices, diagnostics])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[WARNINGS,history()])
    turn=0
    def op(gateway,tool,**fields):
        return {"function":{"name":gateway,"arguments":{
            "tool":tool,"args":fields}}}
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:
            return {"tool_calls":[{
                "function":{"name":"homebrain_find_device",
                            "arguments":{"name":"Google Nest Hub"}}}]}
        if turn==2:
            return {"tool_calls":[op("hub_read_diagnostics","hub_get_logs",
                                     level="warn",mode="past",deviceId="7934",limit=100)]}
        if turn==3:
            return {"tool_calls":[op("hub_read_devices","hub_list_device_events",
                                     deviceId="7934",limit=100)]}
        assert '"target_generic_warning_origin_unverified"' in messages[-1]["content"]
        assert '"observed_calling_app_ids"' in messages[-1]["content"]
        return {"content":"The two device callers are known, while the 19:55 generic "
                          "warning has no proven command issuer."}
    output=await run_native_read_agent(
        question="Why are there generic hub-load warnings for this device?",
        chat=model,mcp=mcp,executor=executor,max_rounds=6)
    diag=output["native_diagnostics"]
    assert diag["successful_reads"]==2
    assert diag["causal_coverage_gap"]["kind"]=="target_generic_warning_origin_unverified"
    assert "Verified device callers; generic warning origin unresolved" in output["answer"]["text"]
    assert "generic_warning_cause_unverified" in output["answer"]["validation_issues"]
    assert "warning_window_actor_provenance_unverified" not in output["answer"]["validation_issues"]
    assert len(executor.calls)==2
