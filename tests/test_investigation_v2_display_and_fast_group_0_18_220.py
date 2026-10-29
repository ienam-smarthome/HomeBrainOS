"""0.18.220: user answer vs technical report boundary; no wasted model pass.

Live 29 Oct test returned correct six-device answer in answer.text but the
V2 browser displayed report.text first, i.e. an old truncated 9-claim list.
The same complete group suffered an unnecessary 8.008s extra claim pass.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.test_webui import render_v2_test_page
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP,FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import DEVICE,NAME,native
from test_investigation_v2_entity_comparison_0_18_219 import _reads


def test_v2_page_prioritises_verified_answer_over_long_technical_report():
    page=render_v2_test_page()
    assert "data.answer?.text||data.report?.text||'No answer returned'" in page
    assert "data.report?.text||data.answer?.text" not in page
    assert "technical_source_report:data.report?.text" in page
    assert "full_source_backed_answer:data.answer?.text" in page
    assert "el('answer').textContent" in page
    assert "el('copyAnswer').onclick" in page
    assert "el('copyReport').onclick" in page


@pytest.mark.asyncio
async def test_complete_six_device_group_skips_eight_second_claim_pass():
    rows=_reads()
    mcp=FakeMCP([DEVICE])
    async def identities():
        return [{"id":r["source_data"]["id"],
                 "label":r["source_data"]["label"]} for r in rows]
    mcp.get_device_identities=identities
    # FakeExecutor returns source data in call order. Match each actual
    # model-selected scoped device ID; mismatched responses must *not*
    # establish complete group evidence.
    by_id={r["source_data"]["id"]:r["source_data"] for r in rows}
    order=["7818","7821","1079","7746","7754","7851"]
    executor=FakeExecutor(mcp,[by_id[ident] for ident in order])
    model_calls=0
    async def model(messages,tools):
        nonlocal model_calls
        model_calls+=1
        if model_calls==1:
            return {"tool_calls":[native(NAME,{"name":"Bathroom"})]}
        ids=(["7818","7821"] if model_calls==2 else
             ["1079","7746"] if model_calls==3 else
             ["7754","7851"] if model_calls==4 else None)
        if ids is None:
            raise AssertionError("Complete group must not trigger final model synthesis")
        return {"tool_calls":[native("hub_read_devices",{
            "tool":"hub_get_device",
            "args":{"deviceId":ident,"mode":"summary"}}) for ident in ids]}
    result=await run_native_read_agent(
        question="Verify each name-matched Bathroom device and all its "
                 "lights, with state and stored level; read-only.",
        mcp=mcp,executor=executor,chat=model,max_rounds=4,max_reads=8)
    d=result["native_diagnostics"]
    assert model_calls==4
    assert d["successful_reads"]==6
    assert d["final_synthesis_skipped_reason"]=="complete_verified_entity_group"
    assert d["final_synthesis_ms"]==0
    assert d["concise_answer_source"]=="verified_entity_group_comparison"
    assert d["entity_group_summary"]["matched_light_count"]==2
    displayed=result["answer"]["text"]
    assert displayed.count("switch=off")==2
    assert "Bathroom Light 1" in displayed
    assert "Bathroom Light 2" in displayed
    assert "last reported level=60%" in displayed
    assert len(executor.calls)==6


@pytest.mark.asyncio
async def test_partial_group_does_not_falsely_skip_final_claim_validation():
    rows=_reads()
    mcp=FakeMCP([DEVICE])
    async def identities():
        return [{"id":r["source_data"]["id"],
                 "label":r["source_data"]["label"]} for r in rows]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[rows[0]["source_data"]])
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        if calls==1:
            return {"tool_calls":[native(NAME,{"name":"Bathroom"})]}
        if calls==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_get_device",
                "args":{"deviceId":"7818","mode":"summary"}})]}
        assert tools==[]
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="Check all named Bathroom devices, read-only.",
        mcp=mcp,executor=executor,chat=model,max_rounds=2)
    d=result["native_diagnostics"]
    assert calls==3
    assert d["successful_reads"]==1
    assert d["final_synthesis_skipped_reason"] is None
    assert d["subject_relevance"]["reason"]=="candidate_group_incomplete"
    assert d["concise_answer_source"]=="unresolved_named_subject_evidence"
    assert "not fully verified" in result["answer"]["text"]
