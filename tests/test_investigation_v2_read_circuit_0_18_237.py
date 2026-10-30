"""v0.18.237 regression: failure to retrieve event history is NOT a negative event result.

The recorded live case spent ~110.8s. Five MCP operations each timed out
at 20s, and only a non-causal app listing succeeded. A circuit breaker
must stop the timeout cascade and the answer must identify the source
access failure, without inventing a missing historical event interval.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_read_health import ReadHealth, read_timeout_cap
from investigation_v2.native_interval_coverage import (
    complete_interval_coverage, incomplete_interval_answer)
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP,FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import native


QUESTION="Investigate the most recent complete heating ON/OFF cycle and explain why it started and stopped."

APPS=MCPTool(
    "hub_read_apps_code","Read-only applications",
    {"type":"object","properties":{
        "tool":{"type":"string","enum":["hub_list_apps"]},
        "args":{"type":"object","additionalProperties":True}},
     "required":["tool","args"]},annotations={"readOnlyHint":True},
)

DEVICES=MCPTool(
    "hub_read_devices","Read-only devices",
    {"type":"object","properties":{
        "tool":{"type":"string","enum":["hub_get_device","hub_list_device_events"]},
        "args":{"type":"object","additionalProperties":True}},
     "required":["tool","args"]},annotations={"readOnlyHint":True},
)


def test_read_time_budget_prioritizes_not_exhausting_entire_user_investigation():
    assert read_timeout_cap("hub_list_apps",20,120)==5
    assert read_timeout_cap("hub_search_tools",20,120)==5
    assert read_timeout_cap("hub_list_devices",20,120)==5
    assert read_timeout_cap("hub_get_device",20,120)==10
    assert read_timeout_cap("hub_list_device_events",20,120)==10
    assert read_timeout_cap("hub_get_device",3,120)==3
    assert read_timeout_cap("hub_get_device",20,2.5)==2.5


def test_circuit_resets_only_on_success_and_not_on_rejected_or_failed_reads():
    h=ReadHealth()
    h.completed("hub_list_devices","read_timeout")
    assert h.snapshot()["state"]=="degraded"
    h.completed("hub_list_apps","mcp_tool_reported_error")
    assert not h.stopped
    h.completed("hub_get_device",None)
    assert h.consecutive_timeouts==0
    h.completed("hub_get_device","read_timeout")
    assert not h.stopped
    h.completed("hub_get_logs","read_timeout")
    assert h.stopped
    assert h.total_timeouts==3
    assert h.snapshot()["state"]=="open"


def test_no_device_event_read_means_history_not_read_not_no_complete_interval():
    evidence=complete_interval_coverage(QUESTION,[],["4382"])
    assert evidence["status"]=="target_history_not_read"
    assert evidence["source_reads"]==[]
    text=incomplete_interval_answer(evidence,read_failures=[
        {"operation":"hub_get_device","code":"read_timeout"}])
    assert "MCP reads timed out" in text
    assert "not evidence that no complete cycle occurred" in text
    assert "source events retrieved do not contain" not in text


class FirstSuccessThenTimeoutExecutor(FakeExecutor):
    async def execute(self,name,arguments,*,tool=None,record_evidence=True):
        if self.calls:
            self.calls.append((name,arguments))
            raise asyncio.TimeoutError("controlled upstream MCP timeout")
        return await super().execute(
            name,arguments,tool=tool,record_evidence=record_evidence)


@pytest.mark.asyncio
async def test_two_cross_gateway_timeouts_stop_investigation_without_inventing_missing_history():
    mcp=FakeMCP([APPS,DEVICES])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FirstSuccessThenTimeoutExecutor(mcp,[{
        "apps":[{"id":3970,"name":"00 Smart Thermostat Scheduler",
                 "type":"Smart Thermostat Scheduler"}]}])
    turn=0
    async def model(messages,tools):
        nonlocal turn
        turn+=1
        if turn==1:
            return {"tool_calls":[native("hub_read_apps_code",{
                "tool":"hub_list_apps","args":{}})]}
        if turn==2:
            return {"tool_calls":[native("homebrain_find_device",{
                "name":"Thermostat"})]}
        if turn==3:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device","args":{"deviceId":"4382"}})]}
        if turn==4:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events",
                "args":{"deviceId":"4382"}})]}
        raise AssertionError("Source circuit must stop before requesting another model turn")
    result=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=7,max_reads=8,per_read_timeout=20,
        enable_model_reasoned_assessment=True)
    d=result["native_diagnostics"]
    assert d["reads_executed"]==3
    assert d["successful_reads"]==1
    assert d["stop_reason"]=="mcp_read_transport_degraded"
    assert d["read_transport_health"]["state"]=="open"
    assert d["read_transport_health"]["timeout_count"]==2
    assert d["requested_complete_interval_coverage"]["status"]=="target_history_not_read"
    assert d["final_synthesis_skipped_reason"]=="explicit_complete_cycle_source_unavailable"
    assert d["concise_answer_source"]=="requested_complete_interval_source_unavailable"
    assert d["claim_publication"]["used_for_display_answer"] is False
    assert "MCP reads timed out" in result["answer"]["text"]
    assert "No source-reported start/stop history was successfully" in result["answer"]["text"]
    assert "source events retrieved do not contain" not in result["answer"]["text"]
    assert len(executor.calls)==3
