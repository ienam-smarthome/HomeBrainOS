"""v0.18.216: reuse existing model responses and avoid futile slow-model pass."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.native_read_agent import run_native_read_agent
from investigation_v2.native_verified_prose import (
    narrative_followup_eligible,verify_model_explanation)
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP,FakeExecutor,READ_DIAG,call)
from test_investigation_v2_verified_focus_0_18_204 import _read,_call


def _tools():
    return FakeMCP([READ_DIAG,_read("hub_read_devices",["hub_get_device"])])


def _results():
    return [
        {"entries":[
            {"type":"dev","name":"Sample outlet","level":"WARN",
             "time":"2026-10-29 11:00:00",
             "message":"dev|9001|Sample outlet|Watchdog fired"},
            {"type":"dev","name":"Sample outlet","level":"WARN",
             "time":"2026-10-29 11:05:00",
             "message":"dev|9001|Sample outlet|Watchdog fired"},
        ]},
        {"id":"9001","name":"Sample outlet","attributes":[
            {"name":"healthStatus","value":"offline"}]},
    ]


def _draft():
    return {"findings":[{
        "source_id":"9001",
        "explanation":"Sample outlet has 2 WARN rows and "
                      "healthStatus=offline in the reported readings; "
                      "this is worth checking.",
        "next_check":"Verify the device power and network "
                     "connectivity without changing settings.",
    }]}


@pytest.mark.asyncio
async def test_existing_final_reply_draft_needs_no_additional_model_call():
    mcp=_tools()
    executor=FakeExecutor(mcp,_results())
    requests=0
    async def model(messages,tools):
        nonlocal requests
        requests+=1
        if requests==1:
            return {"tool_calls":[call(
                "hub_get_logs",mode="past",level="warn",limit=100)]}
        if requests==2:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",deviceId="9001")]}
        assert requests==3
        return {"content":json.dumps({
            "claims":[{"fact_id":"claim-1"}],
            **_draft(),
        })}
    result=await run_native_read_agent(
        question="Review unusual devices and explain what to check.",
        chat=model,mcp=mcp,executor=executor,
        max_rounds=3,max_reads=4,enable_verified_narrative=True)
    d=result["native_diagnostics"]
    assert requests==3
    assert d["narrative_draft_in_read_loop"] is True
    assert d["verified_narrative_accepted"] is True
    assert d["verified_narrative_result"]=="verified_from_read_loop"
    assert d["verified_narrative_ms"]==0
    assert d["planning_model_calls"]==3
    assert d["concise_answer_source"]=="model_authored_independently_checked"
    assert "Sample outlet has 2 WARN rows" in result["answer"]["text"]
    assert "Source-verified findings" in result["report"]["text"]
    assert d["claim_publication"]["status"]=="validated"
    assert len(executor.calls)==2


@pytest.mark.asyncio
async def test_model_can_propose_draft_together_with_a_read_tool_call():
    mcp=_tools()
    executor=FakeExecutor(mcp,_results())
    count=0
    async def model(messages,tools):
        nonlocal count
        count+=1
        if count==1:
            return {"tool_calls":[call(
                "hub_get_logs",mode="past",level="warn",limit=100)]}
        if count==2:
            return {
                "content":json.dumps({"findings":[{
                    "source_id":"9001",
                    "explanation":"Sample outlet has 2 WARN rows in "
                                  "the returned sample; this is worth checking.",
                    "next_check":"Review the device logs and inspect "
                                 "recent activity."}]}),
                "tool_calls":[_call(
                    "hub_read_devices","hub_get_device",deviceId="9001")],
            }
        raise AssertionError("The model loop reached its budget, no extra call")
    result=await run_native_read_agent(
        question="Assess significant device warnings.",chat=model,
        mcp=mcp,executor=executor,max_rounds=2,max_reads=4,
        enable_verified_narrative=True)
    d=result["native_diagnostics"]
    assert count==2
    assert d["verified_narrative_accepted"] is True
    assert d["verified_narrative_result"]=="verified_from_read_loop"
    assert d["verified_narrative_ms"]==0
    assert "Sample outlet has 2 WARN rows" in result["answer"]["text"]
    assert len(executor.calls)==2


@pytest.mark.parametrize("duration,calls,remaining,expected",[
    (6000,6,50.0,True),
    (18000,6,50.0,True),
    (18001,6,50.0,False),
    (57000,6,50.0,False), # 29 October live run: slow model
    (5000,2,7.9,False),
    (5000,2,8.0,True),
    (0,0,60.0,False),
    (0,1,60.0,True),
    (5000,2,-1.0,False),
])
def test_extra_call_gate_uses_actual_provider_latency_not_question_terms(
        duration,calls,remaining,expected):
    assert narrative_followup_eligible(duration,calls,remaining) is expected


def test_unsupported_model_draft_does_not_gain_automatic_permissions():
    from investigation_v2.native_cross_source_brief import verified_source_cases
    from test_investigation_v2_cross_source_brief_0_18_214 import _case_rows
    proposal={"findings":[{
        "source_id":"9001",
        "explanation":"Mesh outlet has 28 WARN rows because power is cut.",
        "next_check":"Restart the hub and disable device monitoring.",
    }]}
    result=verify_model_explanation(proposal,verified_source_cases(_case_rows()))
    assert result["accepted"] is False
    assert "text" not in result
