"""v0.18.198: source authority does not depend on which words the LLM uses.

Live 29 Oct v0.18.197 answer said "most material lead" and
"driven chiefly" despite source packet = unattributed; the earlier
word-based heuristic missed it. This fixture exercises the actual
6-read/6-round model path and no-history boundary.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, incident_claim_ledger,
    source_bound_incident_required, evidence_safe_incident_explanation,
    unsupported_causal_ranking,
)
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_read_agent import run_native_read_agent
from mcp_client import MCPTool
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor
from test_investigation_v2_incident_claims_0_18_197 import events

def warning():
    return {"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-28 19:55:19.194",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"},
        {"level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":"2026-10-28 19:55:19.399",
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}]}

def witness(op,d,idx=1,filters=None):
    return {"read":idx,"operation":op,"source_data":d,"read_filters":filters or {}}

def packet():
    log={"log_summary":{"warning_error_groups":[{
        "source_id":"7934",
        "message":"Device 7934 generates excessive hub load",
        "oldest_returned":"2026-10-28 19:55:19.194",
        "newest_returned":"2026-10-28 19:55:19.399"}]}}
    return incident_attribution_packet([
        witness("hub_get_logs",log,1),
        witness("hub_list_device_events",event_summary({"events":events()}),2,
                {"deviceId":"7934"}),
    ],["7934"])

def test_live_phrase_evasion_is_irrelevant_to_source_publication():
    p=packet()
    assert p["nearest_app_command_gap_seconds"]>5900
    assert not unsupported_causal_ranking(
        "The most material lead is Adhan Player; the device is driven chiefly "
        "by Adhan Player and Google Calendar Notifier.",p)
    assert source_bound_incident_required(p) is True
    ledger=incident_claim_ledger(p)
    assert ledger[0]["evidence_reads"]==[1]
    assert ledger[1]["evidence_reads"]==[2]
    assert ledger[-1]["status"]=="unverified"
    rendered=evidence_safe_incident_explanation(p)
    assert "Adhan Player" in rendered
    assert "Google Calendar Notifier" in rendered
    assert "command-refresh" in rendered
    assert "most material lead" not in rendered
    assert "driven chiefly" not in rendered
    assert "approximately 100" in rendered
    assert "No changes were made." in rendered

def test_missing_command_history_does_not_prove_no_callers():
    log={"log_summary":{"warning_error_groups":[{
        "source_id":"7934","message":"excessive hub load",
        "oldest_returned":"2026-10-28 19:55:19.194",
        "newest_returned":"2026-10-28 19:55:19.399"}]}}
    p=incident_attribution_packet([witness("hub_get_logs",log)],["7934"])
    assert source_bound_incident_required(p) is True
    assert p["caller_identities_verified"] is False
    assert p["scoped_event_history_available"] is False
    assert p["device_caller_app_ids"]==[]
    summary=evidence_safe_incident_explanation(p)
    assert "No device-scoped event history was recovered" in summary
    assert "This does not establish" in summary
    ledger=incident_claim_ledger(p)
    assert ledger[2]["status"]=="not_checked"
    assert ledger[1]["status"]=="not_established"

def test_non_load_warning_preserves_model_authority():
    log={"log_summary":{"warning_error_groups":[{
        "source_id":"7934","message":"Device unavailable for 10 minutes",
        "oldest_returned":"2026-10-28 19:55:19.194",
        "newest_returned":"2026-10-28 19:55:19.399"}]}}
    p=incident_attribution_packet([witness("hub_get_logs",log)],["7934"])
    assert p is None
    assert source_bound_incident_required(p) is False

@pytest.mark.asyncio
async def test_live_model_claim_most_material_lead_withheld_without_word_patch():
    diag=MCPTool("hub_read_diagnostics","Diagnostics",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_logs"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    device=MCPTool("hub_read_devices","Device",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_device_events"]},
            "args":{"type":"object","additionalProperties":True}},
        "required":["tool","args"]},annotations={"readOnlyHint":True})
    mcp=FakeMCP([diag,device])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[warning(),{"events":events()}])
    step=0
    def call(gateway,operation=None,**kw):
        return {"function":{"name":gateway,"arguments":{
            "tool":operation,"args":kw} if operation else kw}}
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:return {"tool_calls":[call("homebrain_find_device",
                                             name="Google Nest Hub")]}
        if step==2:return {"tool_calls":[call("hub_read_diagnostics",
                                             "hub_get_logs",mode="past",
                                             level="warn",deviceId="7934",limit=100)]}
        if step==3:return {"tool_calls":[call("hub_read_devices",
                                             "hub_list_device_events",
                                             deviceId="7934",limit=100)]}
        assert "incident_attribution_evidence" in messages[-1]["content"]
        return {"content":(
            "The most material lead is Adhan Player's repeated refresh polling. "
            "The device is clearly command-heavy, driven chiefly by Adhan "
            "Player and Google Calendar Notifier, and its MediaTransport "
            "churn is another contributor. No mechanism is proven.")}
    result=await run_native_read_agent(
        question="Why is Google Nest Hub generating excessive hub-load warnings?",
        chat=model,mcp=mcp,executor=executor)
    d=result["native_diagnostics"]
    answer=result["answer"]["text"]
    assert len(executor.calls)==2
    assert d["successful_reads"]==2
    assert d["unsupported_causal_ranking_withheld"] is False
    assert d["model_narrative_withheld_for_unattributed_incident"] is True
    assert d["final_synthesis"]=="source_bound_unattributed_incident"
    assert "unattributed_incident_model_narrative_withheld" in result["answer"]["validation_issues"]
    assert result["answer"]["human_review_required"] is True
    assert "most material lead" not in answer
    assert "driven chiefly" not in answer
    assert "What caused the warning? Not yet established." in answer
    assert "11 command-refresh" in answer
    assert "source-bound evidence" in answer
    assert all(c["evidence_reads"] for c in d["incident_claim_ledger"]
               if c["status"]!="not_checked")
