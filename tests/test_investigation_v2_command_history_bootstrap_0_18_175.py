"""Causal V2 must inspect command-capable history before model planning.

The Oct 28 Livingroom Light 2 incident showed 11 switch observations but no
command events because the first history read filtered attribute=switch.
The same device's unfiltered history contains a command-off with appId 4020.
No physical control, AI/source inference, or real Hubitat access.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.read_loop import run_read_only_investigation
from investigation_v2.evidence import build_case_file
from investigation_v2.device_context import device_context_proposals


TARGET="7828"
EVENTS=[
    {"deviceId":TARGET,"name":"switch","value":"on",
     "date":"2026-10-27T23:17:54.524+00:00","producedBy":{"id":"7790"}},
    {"deviceId":TARGET,"name":"switch","value":"off",
     "date":"2026-10-28T00:14:57.111+00:00","producedBy":{"id":"7790"}},
]
COMMAND={
    "deviceId":TARGET,"name":"command-off","type":"command",
    "date":"2026-10-28T00:14:56.868+00:00",
    "producedBy":{"id":"4020"},
}


class FakeMCP:
    def __init__(self, *, accepts_attribute=True, with_window=True):
        attrs={"deviceId":{"type":"string"},
               "hoursBack":{"type":"integer"},"limit":{"type":"integer"},
               "mode":{"type":"string","enum":["status"]}}
        if accepts_attribute:
            attrs["attribute"]={"type":"string"}
        if with_window:
            attrs["since"]={"type":"string"}
            attrs["until"]={"type":"string"}
        self.manifest=[MCPTool(
            "hub_read_devices","read-only device gateway",
            {"type":"object","properties":{
                "tool":{"type":"string","enum":["hub_get_device","hub_list_device_events"]},
                "args":{"type":"object","properties":attrs,
                        "required":["deviceId"],"additionalProperties":False},
            },"required":["tool","args"],"additionalProperties":False},
            annotations={"readOnlyHint":True, "mutates":False},
        )]

    async def list_tools(self):
        return self.manifest


class FakeExecutor:
    def __init__(self, mcp):
        self.mcp=mcp
        self.calls=[]

    async def execute(self, name, arguments, **kwargs):
        assert name=="hub_read_devices"
        assert kwargs["record_evidence"] is False
        operation=arguments["tool"]
        args=arguments["args"]
        assert args["deviceId"]==TARGET
        self.calls.append((operation,dict(args)))
        if operation=="hub_get_device":
            data={"device":{"id":TARGET,"attributes":{
                "switch":"off","networkStatus":"online"}}}
        else:
            data={"deviceId":TARGET,"events":(
                EVENTS if args.get("attribute")=="switch"
                else EVENTS+[COMMAND])}
        response=MCPToolResult(name,arguments,raw={},text="UNTRUSTED",data=data)
        return ToolExecution(name=name,arguments=arguments,
            effect=ToolEffect.READ,success=True,elapsed_ms=5,content="",
            result=response)


async def done(_case, _round):
    return {"hypotheses":[],"reads":[],"finish":True}


@pytest.mark.asyncio
async def test_nonempty_switch_filtered_history_triggers_command_capable_source_read():
    mcp=FakeMCP()
    exe=FakeExecutor(mcp)
    result=await run_read_only_investigation(
        question="Investigate why Livingroom Light 2 turned OFF most recently.",
        mcp=mcp,executor=exe,propose=done,verified_entity_ids=(TARGET,),
        bootstrap_device_context=True,bootstrap_source_identity=True,
        max_rounds=1,max_total_reads=8,
    )
    assert [op for op,_ in exe.calls]==[
        "hub_get_device","hub_list_device_events","hub_list_device_events"]
    assert exe.calls[1][1]["attribute"]=="switch"
    assert "attribute" not in exe.calls[2][1]
    assert exe.calls[2][1]["since"].startswith("2026-10-27T22:14:")
    assert exe.calls[2][1]["until"].startswith("2026-10-28T02:14:")
    commands=[r for r in result.case.records if r.stage=="command_issued"]
    assert len(commands)==1
    assert commands[0].producer_id=="4020"
    assert commands[0].action=="command-off"
    reports=[r for r in result.case.records
             if r.stage=="state_reported" and r.action=="switch" and r.value=="off"]
    assert reports and reports[-1].producer_id=="7790"
    assert any(d.get("stage")=="history_command_context"
               and d.get("command_records_found")==1
               for d in result.bootstrap_diagnostics)
    assert result.executed_reads==3
    assert result.stopped_because=="model_finished"


@pytest.mark.asyncio
async def test_command_history_does_not_require_since_until_support():
    mcp=FakeMCP(with_window=False)
    exe=FakeExecutor(mcp)
    result=await run_read_only_investigation(
        question="Investigate latest OFF",mcp=mcp,executor=exe,
        propose=done,verified_entity_ids=(TARGET,),
        bootstrap_device_context=True,max_rounds=1)
    assert [op for op,_ in exe.calls]==[
        "hub_get_device","hub_list_device_events","hub_list_device_events"]
    assert "attribute" not in exe.calls[2][1]
    assert "hoursBack" in exe.calls[2][1]
    assert any(r.stage=="command_issued" for r in result.case.records)


@pytest.mark.asyncio
async def test_current_factual_read_does_not_trigger_extra_causal_history():
    mcp=FakeMCP()
    exe=FakeExecutor(mcp)
    result=await run_read_only_investigation(
        question="What is the switch status?",mcp=mcp,executor=exe,
        propose=done,verified_entity_ids=(TARGET,),
        bootstrap_device_context=True,factual_objective="status",max_rounds=1)
    assert [op for op,_ in exe.calls]==["hub_get_device"]
    assert result.executed_reads==1


@pytest.mark.asyncio
async def test_optional_attribute_in_live_schema_is_required_for_unfiltered_read():
    mcp=FakeMCP()
    tool=mcp.manifest[0]
    tool.input_schema["properties"]["args"]["required"].append("attribute")
    exe=FakeExecutor(mcp)
    result=await run_read_only_investigation(
        question="Investigate latest OFF",mcp=mcp,executor=exe,
        propose=done,verified_entity_ids=(TARGET,),
        bootstrap_device_context=True,max_rounds=1)
    assert [op for op,_ in exe.calls]==["hub_get_device","hub_list_device_events"]
    assert any(d.get("stage")=="history_command_context"
               and d.get("reason")=="unfiltered_history_operation_or_schema_unavailable"
               for d in result.bootstrap_diagnostics)
    assert not any(r.stage=="command_issued" for r in result.case.records)
