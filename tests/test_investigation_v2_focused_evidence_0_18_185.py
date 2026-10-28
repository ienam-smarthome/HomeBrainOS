"""Live-shaped multi-domain focus and stale-evidence integration regressions."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool
from investigation_v2.native_evidence_focus import (
    focused_highlights, focused_fallback, focused_model_view, read_fingerprint,
)
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_entity_lookup import NAME
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor

DEVICE=MCPTool("hub_read_devices","read device",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_device"]},
        "args":{"type":"object","additionalProperties":True}
    },"required":["tool","args"]},annotations={"readOnlyHint":True})
DIAG=MCPTool("hub_read_diagnostics","read logs",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_logs"]},
        "args":{"type":"object","additionalProperties":True}
    },"required":["tool","args"]},annotations={"readOnlyHint":True})

NEST={"id":"7934","label":"Google Nest Hub - [Google Nest Hub]",
      "attributes":[{"name":"networkStatus","value":"online"},
                    {"name":"status","value":"idle"}]}
MESH={"id":"7103","label":"Bedroom 3 Mesh",
      "attributes":[{"name":"lastSeen","value":"Mon Oct 12 01:30:01 BST 2026"},
                    {"name":"healthStatus","value":"offline"},
                    {"name":"deviceHealth","value":"stale"},
                    {"name":"mqttStatus","value":"connected"},
                    {"name":"dataAgeSeconds","value":162325}]}
LOG={"log_summary":{
    "returned_rows":100,"warning_error_group_count":4,
    "warning_error_groups":[
        {"source_id":"7103","source_name":"Bedroom 3 Mesh","level":"WARN",
         "message":"Watchdog fired after 48059s without data","count":33},
        {"source_id":"7934","source_name":"Google Nest Hub - [Google Nest Hub]",
         "level":"WARN","message":"Device 7934 generates excessive hub load","count":22},
        {"source_id":"7934","source_name":"Google Nest Hub - [Google Nest Hub]",
         "level":"WARN","message":"method runQ ran for 147,429ms","count":16},
        {"source_id":"4129","source_name":"SenseCap D1 Settings","level":"WARN",
         "message":"HTTP 408 timeout","count":9}
    ],"level_counts_in_returned_rows":{"WARN":100},"truncated_or_partial":True}}
    
def test_target_evidence_prioritises_relevant_warn_and_ignores_other_device():
    receipts=[
        {"read":1,"operation":"hub_get_device","source_data":NEST},
        {"read":2,"operation":"hub_get_logs","source_data":LOG},
        {"read":3,"operation":"hub_get_device","source_data":dict(NEST)},
    ]
    facts=focused_highlights(receipts,["7934"])
    text="\n".join(facts)
    assert "runQ ran for 147,429ms" in text
    assert "generates excessive hub load" in text
    assert "Bedroom 3 Mesh" not in text
    assert "SenseCap D1" not in text
    assert sum("networkStatus=online" in line for line in facts)==1
    model_view=focused_model_view("hub_get_logs",LOG,["7934"])
    assert model_view["log_summary"]["target_group_count"]==2
    assert model_view["log_summary"]["other_group_count"]==2
    assert len(LOG["log_summary"]["warning_error_groups"])==4
    conclusion=focused_fallback(receipts,[],["7934"])
    assert "runQ" in conclusion
    assert "wider" in conclusion
    assert "not independently verified" in conclusion

def test_mesh_lastseen_and_broker_are_stale_not_proof_of_physical_power():
    receipts=[{"read":1,"operation":"hub_get_device","source_data":MESH},
              {"read":2,"operation":"hub_get_logs","source_data":LOG}]
    answer=focused_fallback(receipts,[],["7103"])
    assert "lastSeen=Mon Oct 12 01:30:01 BST 2026" in answer
    assert "mqttStatus=connected" in answer
    assert "reported offline" in answer
    assert "not established" in answer
    assert "different clocks/update" in answer
    assert "most likely" not in answer

def test_only_current_device_snapshots_are_deduplicated():
    assert read_fingerprint("hub_get_device",NEST)==read_fingerprint("hub_get_device",dict(NEST))
    assert read_fingerprint("hub_get_logs",LOG) is None
    assert read_fingerprint("hub_get_device",{"id":"7934","attributes":[]}) is None

@pytest.mark.asyncio
async def test_live_model_repeats_snapshots_but_host_retains_focused_answer():
    mcp=FakeMCP([DEVICE,DIAG])
    async def identities():
        return [{"id":"7934","label":"Google Nest Hub - [Google Nest Hub]"}]
    mcp.get_device_identities=identities
    log_data={"entries":[
        {"type":"dev","name":"Bedroom 3 Mesh","level":"WARN",
         "message":"dev|7103|Bedroom 3 Mesh|Watchdog fired after 48059s"},
        {"type":"dev","name":"Google Nest Hub - [Google Nest Hub]",
         "level":"WARN","message":"dev|7934|Google Nest Hub - [Google Nest Hub]|Device 7934 generates excessive hub load"},
        {"type":"dev","name":"Google Nest Hub - [Google Nest Hub]",
         "level":"WARN","message":"dev|7934|Google Nest Hub - [Google Nest Hub]|method runQ ran for 147,429ms"},
    ]}
    executor=FakeExecutor(mcp,[NEST,log_data,NEST,NEST])
    step=0
    def tool(name,arguments):
        return {"function":{"name":name,"arguments":arguments}}
    async def model(messages,tools):
        nonlocal step
        step+=1
        if not tools:
            raise RuntimeError("Final provider unavailable")
        if step==1:
            return {"tool_calls":[tool(NAME,{"name":"Google Nest Hub"})]}
        if step==2:
            return {"tool_calls":[tool("hub_read_devices",{
                "tool":"hub_get_device","args":{"deviceId":"7934","mode":"summary"}})]}
        if step==3:
            return {"tool_calls":[tool("hub_read_diagnostics",{
                "tool":"hub_get_logs","args":{"level":"warn","limit":100}})]}
        if step==4:
            return {"tool_calls":[tool("hub_read_devices",{
                "tool":"hub_get_device","args":{"deviceId":"7934","mode":"configuration"}})]}
        return {"tool_calls":[tool("hub_read_devices",{
            "tool":"hub_get_device","args":{"deviceId":"7934","mode":"details"}})]}
    out=await run_native_read_agent(
        question="Why does Google Nest Hub generate load warnings?",
        chat=model,mcp=mcp,executor=executor,max_rounds=7)
    assert out["native_diagnostics"]["stop_reason"]=="no_new_source_evidence"
    assert out["native_diagnostics"]["redundant_evidence_reads"]==2
    assert out["native_diagnostics"]["final_synthesis"]=="host_evidence_fallback"
    assert out["native_diagnostics"]["focus_ids"]==["7934"]
    assert out["resolved_devices"]==["7934"]
    answer=out["answer"]["text"]
    assert "excessive hub load" in answer
    assert "runQ" in answer
    assert "Bedroom 3 Mesh" not in out["native_diagnostics"]["source_highlights"]
    assert "physical" in answer or "reported online" in answer or "wider" in answer
