"""0.18.215: source-checked model-authored explanation is not a free pass.

The actual V2 path may ask one bounded extra model question after the
model-selected READ sequence, but only subject/quantity/status-validated
language may replace the existing source-authoritative answer.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_verified_prose import verify_model_explanation
from investigation_v2.native_cross_source_brief import verified_source_cases
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, call)
from test_investigation_v2_verified_focus_0_18_204 import _read, _call
from test_investigation_v2_cross_source_brief_0_18_214 import _case_rows


def _proposal():
    return {"findings":[
        {"source_id":"9001",
         "explanation":"Mesh outlet has 28 WARN rows and healthStatus=offline "
                       "in the reported readings; this is worth checking.",
         "next_check":"Verify the physical power and network connectivity "
                      "without changing settings."},
        {"source_id":"9002",
         "explanation":"Matter bridge has 10 WARN rows and healthStatus=online "
                       "while networkStatus=offline in the reported readings.",
         "next_check":"Check independent network reachability and review "
                      "the device readings."},
        {"source_id":"9003",
         "explanation":"MQTT app has 37 WARN rows in the returned sample; "
                       "this is worth checking.",
         "next_check":"Review the app logs and inspect recent activity."},
    ]}


def test_natural_sentences_are_model_authored_but_source_checked():
    cases=verified_source_cases(_case_rows())
    result=verify_model_explanation(_proposal(),cases)
    assert result["accepted"] is True
    text=result["text"]
    assert text.startswith("**Evidence-checked explanation**")
    assert "Mesh outlet has 28 WARN rows" in text
    assert "healthStatus=online while networkStatus=offline" in text
    assert "Review the app logs" in text
    assert "(Read #1, #3)" in text
    assert "not verification of physical connectivity" in text
    assert result["verified_subject_ids"]==["9001","9002","9003"]


@pytest.mark.parametrize("field,value",[
    ("source_id","9999"),
    ("source_id","9002"),
    ("explanation","Mesh outlet is broken and must be replaced."),
    ("explanation","Mesh outlet has 99 WARN rows and healthStatus=offline."),
    ("explanation","Mesh outlet has 28 WARN rows and healthStatus=online."),
    ("explanation","Mesh outlet has 28 ERROR rows and healthStatus=offline."),
    ("explanation","Mesh outlet has 28 WARN rows and the driver crashed."),
    ("explanation","Mesh outlet has 28 WARN rows and is offline."),
    ("explanation","Mesh outlet has 28 WARN rows and causes hub overload."),
    ("explanation","Mesh outlet has 28 WARN rows; http://example.net"),
    ("next_check","Restart the router and reset the device."),
    ("next_check","Check why it is definitely offline."),
    ("next_check","Check logs then turn off the device."),
])
def test_unsupported_assertions_and_action_recommendations_are_withheld(field,value):
    proposal=_proposal()
    proposal["findings"][0][field]=value
    result=verify_model_explanation(proposal,verified_source_cases(_case_rows()))
    assert result["accepted"] is False
    assert "text" not in result


def test_empty_unstructured_and_extra_fields_denied():
    cases=verified_source_cases(_case_rows())
    for item in (None, "The Mesh is broken!",'{"findings":[]}',
                 {"findings":[{"source_id":"9001"}]},
                 {"findings":_proposal()["findings"],
                  "wrote_commands":True}):
        result=verify_model_explanation(item,cases)
        assert result["accepted"] is False


@pytest.mark.asyncio
async def test_real_native_agent_one_model_authored_pass_verified_and_published():
    mcp=FakeMCP([READ_DIAG,_read("hub_read_devices",["hub_get_device"])])
    executor=FakeExecutor(mcp,[
        {"entries":[
            {"type":"dev","name":"Sample outlet","level":"WARN",
             "time":"2026-10-29 11:00:00",
             "message":"dev|9001|Sample outlet|Watchdog fired"},
            {"type":"dev","name":"Sample outlet","level":"WARN",
             "time":"2026-10-29 11:05:00",
             "message":"dev|9001|Sample outlet|Watchdog fired"},
        ]},
        {"id":"9001","name":"Sample outlet","label":"Sample outlet",
         "attributes":[{"name":"healthStatus","value":"offline"}]},
    ])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[call(
                "hub_get_logs",mode="past",level="warn",limit=100)]}
        if calls==2:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",deviceId="9001")]}
        if calls==3:
            return {"content":'{"claims":[{"fact_id":"claim-1"}]}'}
        assert calls==4 and tools==[]
        assert '"source_id": "9001"' in messages[-1]["content"]
        return {"content":'{"findings":[{"source_id":"9001",'
            '"explanation":"Sample outlet has 2 WARN rows and '
            'healthStatus=offline in the reported readings; this is worth '
            'checking.","next_check":"Verify the device power and network '
            'connectivity without changing settings."}]}'}
    result=await run_native_read_agent(
        question="Find significant issues and recommended checks.",
        chat=model,mcp=mcp,executor=executor,
        max_rounds=3,max_reads=4,max_seconds=90,
        enable_verified_narrative=True)
    d=result["native_diagnostics"]
    assert d["verified_narrative_accepted"] is True
    assert d["concise_answer_source"]=="model_authored_independently_checked"
    assert d["verified_narrative_result"]=="source_scoped_factual_validation"
    assert result["answer"]["text"].startswith("**Evidence-checked explanation**")
    assert "Sample outlet has 2 WARN rows" in result["answer"]["text"]
    assert "Verified read coverage" in result["report"]["text"]
    assert "Source-verified findings" in result["report"]["text"]
    assert calls==4
    assert len(executor.calls)==2


@pytest.mark.asyncio
async def test_unsupported_model_narrative_returns_unchanged_trusted_brief():
    mcp=FakeMCP([READ_DIAG,_read("hub_read_devices",["hub_get_device"])])
    executor=FakeExecutor(mcp,[
        {"entries":[{"type":"dev","name":"Mesh plug","level":"WARN",
                     "time":"2026-10-29 11:00:00",
                     "message":"dev|9001|Mesh plug|Watchdog fired"}]},
        {"id":"9001","name":"Mesh plug",
         "attributes":[{"name":"healthStatus","value":"offline"}]},
    ])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[call(
                "hub_get_logs",mode="past",level="warn",limit=100)]}
        if calls==2:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",deviceId="9001")]}
        if calls==3:
            return {"content":'{"claims":[]}'}
        return {"content":'{"findings":[{"source_id":"9001",'
                '"explanation":"Mesh plug is broken because the battery is flat.",'
                '"next_check":"Restart the hub and reset the device."}]}'}
    result=await run_native_read_agent(
        question="Review my hub health.",chat=model,mcp=mcp,executor=executor,
        max_rounds=3,max_seconds=90,enable_verified_narrative=True)
    d=result["native_diagnostics"]
    assert d["verified_narrative_accepted"] is False
    assert d["verified_narrative_result"]=="unsupported_language"
    assert d["concise_answer_source"]=="cross_source_verified_case_graph"
    assert "broken" not in result["answer"]["text"]
    assert "Source-reported" in result["answer"]["text"] or \
        "source-reported" in result["answer"]["text"]
    assert len(executor.calls)==2


@pytest.mark.asyncio
async def test_opt_out_keeps_old_behavior_and_no_extra_model_call():
    mcp=FakeMCP([READ_DIAG,_read("hub_read_devices",["hub_get_device"])])
    executor=FakeExecutor(mcp,[
        {"entries":[{"type":"dev","name":"Sample outlet","level":"WARN",
                     "time":"2026-10-29 11:00:00",
                     "message":"dev|9001|Sample outlet|Watchdog fired"}]},
        {"id":"9001","name":"Sample outlet",
         "attributes":[{"name":"healthStatus","value":"offline"}]},
    ])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[call(
                "hub_get_logs",mode="past",level="warn",limit=100)]}
        if calls==2:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",deviceId="9001")]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="Review my hub health.",chat=model,mcp=mcp,executor=executor,
        max_rounds=3,enable_verified_narrative=False)
    assert calls==3
    assert result["native_diagnostics"]["verified_narrative_result"]=="not_attempted"
