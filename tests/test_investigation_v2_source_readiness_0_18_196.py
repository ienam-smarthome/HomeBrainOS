"""Live-derived v0.18.196 tests: source usability and duplicate log utility."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.native_source_readiness import (
    source_read_summary, repeated_broad_log_scope)
from investigation_v2.native_evidence_focus import focused_highlights
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_tool_protocol import guidance_for
from mcp_client import MCPTool
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor,
)

DIAG=MCPTool("hub_read_diagnostics","Diagnostics",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_logs"]},
        "args":{"type":"object","additionalProperties":True}},
    "required":["tool","args"]},annotations={"readOnlyHint":True})
APP_SOURCE=MCPTool("hub_read_apps_code","Source",{
    "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_source"]},
        "args":{"type":"object","additionalProperties":True}},
    "required":["tool","args"]},annotations={"readOnlyHint":True})


def witness(limit=100, scope=None, count=71):
    return {"read":1,"operation":"hub_get_logs",
            "read_filters":{
                "mode":"past","level":"warn","limit":limit,
                **(scope or {}),
            },
            "source_data":{"log_summary":{
                "returned_rows":count,"warning_error_groups":[
                    {"level":"WARN","source_id":"7934",
                     "message":"Device generates excessive hub load"}]}}}


def test_source_gateway_success_without_code_is_not_code_analysis():
    result=source_read_summary(
        {"status":"success","appId":"1679"},
        requested_type="app",requested_id="1679")
    assert result["gateway_status"]=="success"
    assert result["source_read_status"]=="no_source_text_in_returned_payload"
    assert result["source_content_available"] is False
    assert result["source_read_usable_for_method_reasoning"] is False
    assert result["requested_source_type"]=="app"
    assert result["requested_source_id"]=="1679"
    assert result["returned_source_id"]=="1679"
    assert result["source_id_matches_request"] is True
    msg="\n".join(focused_highlights([{
        "read":6,"operation":"hub_get_source",
        "source_data":result
    }],["7934"]))
    assert "no_source_text_in_returned_payload" in msg
    assert "cannot support implementation" in msg


def test_bounded_complete_source_yields_names_not_raw_code_or_secrets():
    body=("def refresh() {\n"
          "    privateToken = 'SHOULD_NOT_APPEAR'\n"
          "    runQ()\n"
          "}\n"
          "def runQ() {\n"
          "    log.debug 'EXECUTION_NOT_PROVEN'\n"
          "}\n")
    result=source_read_summary({
        "success":True,"appId":"1679",
        "totalLength":len(body),"offset":0,
        "sourceCode":body,
    },requested_type="app",requested_id="1679")
    assert result["source_read_usable_for_method_reasoning"] is True
    assert result["source_complete"] is True
    assert result["source_content_available"] is True
    assert "sourceCode" not in str(result)
    assert "SHOULD_NOT_APPEAR" not in str(result)
    assert "EXECUTION_NOT_PROVEN" not in str(result)
    assert "refresh" in result["declared_method_names"]
    assert "runQ" in result["declared_method_names"]
    assert "cause" in result["source_interpretation_limit"]


def test_source_partial_or_identity_mismatch_fail_closed():
    body="def runQ(){\n log.debug 'the callback ran and stalled'\n}\n"
    for value in (
        {"source":body,"success":True,"totalLength":len(body)+20,
         "offset":0,"appId":"1679"},
        {"source":body,"success":True,"totalLength":len(body),
         "offset":20,"appId":"1679"},
        {"source":body,"success":True,"totalLength":len(body),
         "offset":0,"appId":"4080"},
    ):
        p=source_read_summary(value,requested_type="app",
                              requested_id="1679")
        assert p["source_read_usable_for_method_reasoning"] is False
        assert p["source_complete"] is False
        assert "declared_method_names" not in p
        assert "log.debug" not in str(p)


def test_broad_warning_log_repeat_only_limit_blocks_not_distinct_windows():
    historical=[witness()]
    assert repeated_broad_log_scope(
        {"mode":"past","level":"warn","limit":200},historical)
    assert not repeated_broad_log_scope(
        {"mode":"past","level":"warn","limit":200,
         "deviceId":"7934"},historical)
    assert not repeated_broad_log_scope(
        {"mode":"past","level":"warn","limit":200,
         "since":"2026-10-28 17:00"},historical)
    assert not repeated_broad_log_scope(
        {"mode":"past","level":"warn","limit":200,
         "cursor":"previous"},historical)
    assert not repeated_broad_log_scope(
        {"mode":"devices","level":"warn","limit":200},historical)
    assert not repeated_broad_log_scope(
        {"mode":"past","level":"error","limit":200},historical)
    assert not repeated_broad_log_scope(
        {"mode":"past","level":"warn","limit":100},historical)
    assert not repeated_broad_log_scope(
        {"mode":"past","level":"warn","limit":200},[witness(count=100)])
    assert "since/until" in guidance_for("repeated_broad_log_scope")


def call(gateway, operation, **kwargs):
    return {"function":{"name":gateway,"arguments":{
        "tool":operation,"args":kwargs}}}


@pytest.mark.asyncio
async def test_model_log_repeat_rejected_before_hub_then_source_read_declares_absent_code():
    mcp=FakeMCP([DIAG,APP_SOURCE])
    executor=FakeExecutor(mcp,[
        {"entries":[{"type":"dev","name":"Google Nest Hub",
                     "level":"WARN","time":"2026-10-28 19:55:19.399",
                     "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load"}]},
        {"status":"success","appId":"1679"},
    ])
    # Source identity must be separately attested, not inferred from the
    # model's request. Use a source-backed log producer app ID in first read.
    # First log is device-specific, so it attests the target device ID;
    # a separate app log line attests app 1679.
    executor.outputs[0]["entries"].append({
        "type":"app","name":"Adhan Player","level":"WARN",
        "time":"2026-10-28 19:55:19.401",
        "message":"app|1679|Adhan Player|Some unrelated warning",
    })
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[call("hub_read_diagnostics","hub_get_logs",
                                       mode="past",level="warn",limit=100)]}
        if step==2:
            return {"tool_calls":[call("hub_read_diagnostics","hub_get_logs",
                                       mode="past",level="warn",limit=200)]}
        if step==3:
            assert "repeated_broad_log_scope" in messages[-1]["content"]
            return {"tool_calls":[call("hub_read_apps_code","hub_get_source",
                                       type="app",id="1679")]}
        return {"content":"The source read returned metadata only, so implementation is unverified."}
    result=await run_native_read_agent(
        question="Investigate current hub warnings and caller source",
        chat=model,mcp=mcp,executor=executor,
        max_rounds=6)
    d=result["native_diagnostics"]
    assert d["successful_reads"]==2
    assert len(executor.calls)==2
    assert d["failures"][0]["code"]=="repeated_broad_log_scope"
    src=next(w["source_data"] for w in d["read_summaries"]
             if w["operation"]=="hub_get_source")
    assert src["source_read_status"]=="no_source_text_in_returned_payload"
    assert src["source_read_usable_for_method_reasoning"] is False
    assert src["requested_source_id"]=="1679"
