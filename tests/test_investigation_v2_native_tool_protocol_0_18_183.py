"""Integration regressions for real native MCP wire errors and synthesis failure."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPTool
from investigation_v2.native_read_agent import _guard, run_native_read_agent
from investigation_v2.native_tool_protocol import (
    operation_problem, guidance_for, source_highlights, evidence_fallback,
)
from test_investigation_v2_native_read_agent_0_18_181 import (
    READ_DIAG, FakeMCP, FakeExecutor, call,
)


def test_wire_log_level_is_a_single_value_not_comma_list():
    manifest={"hub_read_diagnostics": READ_DIAG}
    wrong={"tool":"hub_get_logs", "args":{"level":"WARN,ERROR", "limit":100}}
    assert _guard("hub_read_diagnostics",wrong,manifest,{},set())=="invalid_log_level"
    assert "separately" in guidance_for("invalid_log_level")
    assert operation_problem("hub_read_diagnostics",{
        "tool":"hub_get_logs","args":{"level":"warn"}}) is None


def test_read_gateway_cannot_write_persistent_metrics_snapshot():
    manifest={"hub_read_diagnostics": READ_DIAG}
    bad={"tool":"hub_get_metrics", "args":{"recordSnapshot":True}}
    assert _guard("hub_read_diagnostics",bad,manifest,{},set())=="write_side_effect_flag_forbidden"


@pytest.mark.asyncio
async def test_model_recovers_from_invalid_level_and_reads_severity():
    mcp=FakeMCP([READ_DIAG])
    results=[
        {"total":12000,"entries":[{"type":"dev","name":"Other","level":"INFO",
                                   "message":"dev|24|Other|temp 22"}]},
        {"total":12000,"entries":[{"type":"dev","name":"Bedroom 3 Mesh","level":"WARN",
                                   "message":"dev|7103|Bedroom 3 Mesh|Watchdog fired after 45945s"}]},
    ]
    executor=FakeExecutor(mcp,results)
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[call("hub_get_logs",limit=100)]}
        if step==2:
            return {"tool_calls":[call("hub_get_logs",level="WARN,ERROR",limit=100)]}
        if step==3:
            assert "single log level" in messages[-1]["content"]
            return {"tool_calls":[call("hub_get_logs",level="warn",limit=100)]}
        return {"content":"The returned warning is a watchdog; physical cause remains unverified."}
    output=await run_native_read_agent(
        question="check hub logs",chat=model,mcp=mcp,executor=executor)
    assert output["native_diagnostics"]["reads_executed"]==2
    assert executor.calls[1][1]["args"]["level"]=="warn"
    assert any(f["code"]=="invalid_log_level"
               for f in output["native_diagnostics"]["failures"])
    assert "watchdog" in output["answer"]["text"].lower()


@pytest.mark.asyncio
async def test_timeout_circuit_blocks_same_operation_even_when_args_differ():
    read_devices=MCPTool(
        "hub_read_devices","Read devices",
        {"type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_devices"]},
            "args":{"type":"object","additionalProperties":True},
        },"required":["tool","args"]},annotations={"readOnlyHint":True},
    )
    mcp=FakeMCP([read_devices,READ_DIAG])
    class SlowExecutor:
        def __init__(self):
            self.mcp=mcp
            self.calls=[]
        async def execute(self,name,arguments,**kwargs):
            self.calls.append((name,arguments))
            if arguments.get("tool")=="hub_list_devices":
                raise asyncio.TimeoutError()
            from mcp_client import MCPToolResult
            from tool_registry import ToolEffect
            result=MCPToolResult(name,arguments,{},"",{
                "entries":[{"level":"WARN","type":"dev","name":"Bedroom 3 Mesh",
                            "message":"dev|7103|Bedroom 3 Mesh|watchdog stale"}]})
            return SimpleNamespace(name=name,result=result,success=True,
                                   error=None,effect=ToolEffect.READ)
    executor=SlowExecutor()
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[{"function":{"name":"hub_read_devices",
                "arguments":{"tool":"hub_list_devices","args":{"limit":500}}}}]}
        if step==2:
            return {"tool_calls":[{"function":{"name":"hub_read_devices",
                "arguments":{"tool":"hub_list_devices","args":{"limit":20}}}}]}
        if step==3:
            return {"tool_calls":[call("hub_get_logs",level="warn",limit=50)]}
        return {"content":"A watchdog warning exists; its root cause remains unverified."}
    out=await run_native_read_agent(
        question="Investigate a device",chat=model,mcp=mcp,executor=executor)
    assert [x[1]["tool"] for x in executor.calls] == [
        "hub_list_devices","hub_get_logs"]
    assert "hub_read_devices:hub_list_devices" in out["native_diagnostics"]["timed_out_operations"]
    assert any(f["code"]=="operation_prior_timeout"
               for f in out["native_diagnostics"]["failures"])


@pytest.mark.asyncio
async def test_provider_synthesis_failure_keeps_source_answer_not_blank():
    mcp=FakeMCP([READ_DIAG])
    executor=FakeExecutor(mcp,[{
        "entries":[{"level":"WARN","type":"dev","name":"Bedroom 3 Mesh",
                    "time":"2026-10-28 20:02:21.268",
                    "message":"dev|7103|Bedroom 3 Mesh|Watchdog fired after 45945s without data"}],
        "total":9599,
    }])
    turns=0
    async def model(messages,tools):
        nonlocal turns
        turns+=1
        if not tools:
            raise RuntimeError("provider unavailable")
        return {"tool_calls":[call("hub_get_logs",level="warn",limit=100)]}
    out=await run_native_read_agent(
        question="Why is the device offline?",chat=model,mcp=mcp,
        executor=executor,max_rounds=3)
    assert out["native_diagnostics"]["final_synthesis"]=="host_evidence_fallback"
    assert "Bedroom 3 Mesh" in out["answer"]["text"]
    assert "45945s" in out["answer"]["text"]
    assert "root cause" in out["answer"]["text"]
    assert out["native_diagnostics"]["reads_executed"]==1


def test_fallback_preserves_actual_device_contact_and_watchdog_gaps():
    witnesses=[{"read":9,"operation":"hub_get_device","source_data":{
        "id":"7103","label":"Bedroom 3 Mesh",
        "attributes":[
            {"name":"lastSeen","value":"Mon Oct 12 01:30:01 BST 2026"},
            {"name":"healthStatus","value":"offline"},
            {"name":"deviceHealth","value":"stale"},
            {"name":"mqttStatus","value":"connected"},
            {"name":"switch","value":"off"},
        ]}},
        {"read":8,"operation":"hub_get_logs","source_data":{"log_summary":{
            "returned_rows":100,"level_counts_in_returned_rows":{"WARN":1},
            "warning_error_groups":[{
                "level":"WARN","source_name":"Bedroom 3 Mesh","source_id":"7103",
                "message":"Watchdog fired after 45945s without data",
            }]
        }}},
    ]
    facts=source_highlights(witnesses)
    assert "lastSeen=Mon Oct 12 01:30:01 BST 2026" in "\n".join(facts)
    assert "mqttStatus=connected" in "\n".join(facts)
    assert "45945s" in "\n".join(facts)
    assert "not a verified" in evidence_fallback(witnesses,[])
