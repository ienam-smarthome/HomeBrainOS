"""Regression for HTTP 503 on complex whole-home meter question.

No live network, real Hubitat devices or model service; validates semantic
stage boundaries, optional classification failure, and safe unknown-role list.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.semantic_plan import (
    inventory_profile, parse_semantic_plan, semantic_plan,
)
from investigation_v2.role_enrichment import enrich_measurement_roles
from investigation_v2.semantic_execute import execute_inventory_plan

QUESTION=(
    "Which five individual devices are currently consuming the most electricity? "
    "Exclude whole-house meters and circuit subtotals from the individual-device "
    "ranking. Show any excluded aggregate meters separately, explain which "
    "classifications are verified or inferred, and identify any devices whose "
    "measurement scope is unknown. Do not change anything."
)
ITEMS=[
    {"id":"9900","label":"House Supply Meter","room":"Energy",
     "capabilities":["PowerMeter"],"attributes":{"power":"231 W"}},
    {"id":"100","label":"Fridge","room":"Appliances",
     "capabilities":["PowerMeter"],"attributes":{"power":"84 W"}},
    {"id":"101","label":"Fan","room":"Ventilation",
     "capabilities":["PowerMeter"],"attributes":{"power":"33 W"}},
    {"id":"102","label":"Computer","room":"Office",
     "capabilities":["PowerMeter"],"attributes":{"power":"28 W"}},
    {"id":"103","label":"Socket","room":"Sockets",
     "capabilities":["PowerMeter"],"attributes":{"power":"8 W"}},
    {"id":"104","label":"Speaker","room":"Living Room",
     "capabilities":["PowerMeter"],"attributes":{"power":"7 W"}},
    {"id":"105","label":"Unclassified Submeter","room":"Energy",
     "capabilities":["PowerMeter"],"attributes":{"power":"79 W"}},
]
BASE={
    "mode":"inventory","scope":"all","device_name":None,"room":None,
    "attribute":"power","operator":"none","value":None,
    "aggregation":"top","limit":5,"measurement_target":"individual_load",
}


@pytest.mark.asyncio
async def test_original_question_uses_small_phase_one_and_then_independent_roles():
    seen=[]
    async def chat(messages,tools):
        assert tools==[]
        assert len(messages)==2
        user=json.loads(messages[1]["content"])
        seen.append(user)
        if len(seen)==1:
            assert "meter_candidates" not in user["inventory_vocabulary"]
            assert len(messages[1]["content"])<2500
            assert "House Supply Meter" not in messages[1]["content"]
            assert "measurement_roles" not in messages[0]["content"]
            return {"content":json.dumps(BASE)}
        assert user["task"]=="measurement coverage only"
        assert len(user["meter_candidates"])==7
        return {"content":json.dumps({"measurement_roles":[
            {"id":"9900","label":"House Supply Meter","role":"site_total"},
            *[{"id":str(i),"label":name,"role":"individual_load"}
              for i,name in [
                  (100,"Fridge"),(101,"Fan"),(102,"Computer"),(103,"Socket"),
                  (104,"Speaker"),
              ]],
        ]})}
    objective=await semantic_plan(QUESTION,ITEMS,chat)
    assert objective.measurement_target=="individual_load"
    assert objective.measurement_roles==()
    enriched,diagnostics=await enrich_measurement_roles(objective,ITEMS,chat)
    assert diagnostics["outcome"]=="enriched"
    assert diagnostics["accepted_hints"]==6
    answer=execute_inventory_plan(enriched,ITEMS,{"complete":True,"pages":5})
    lines=[line for line in answer["answer"]["text"].splitlines()
           if line.startswith("• ") and " — " in line]
    assert len(lines)==5
    assert "Fridge" in lines[0]
    assert "Speaker" in lines[-1]
    assert "House Supply Meter" not in "\n".join(lines)
    assert "House Supply Meter" in answer["answer"]["text"]
    assert "Unclassified Submeter" in answer["answer"]["text"]
    assert answer["inventory_query"]["matched_count"]==5
    assert answer["inventory_query"]["excluded_unknown_scope"]==1
    assert len(seen)==2


@pytest.mark.asyncio
async def test_timeout_in_optional_role_model_does_not_cancel_valid_base_plan():
    async def phase_two_hangs(messages,tools):
        await asyncio.sleep(3)
    objective=parse_semantic_plan(BASE,inventory_profile(ITEMS))
    result,diagnostics=await enrich_measurement_roles(
        objective,ITEMS,phase_two_hangs,timeout_seconds=1)
    assert result==objective
    assert diagnostics["outcome"]=="unavailable"
    assert diagnostics["reason"]=="timeout"
    output=execute_inventory_plan(result,ITEMS,{"complete":True})
    assert output["inventory_query"]["matched_count"]==0
    assert output["inventory_query"]["excluded_unknown_scope"]==7
    assert "House Supply Meter" in output["answer"]["text"]
    assert "measurement scope unknown" in output["answer"]["text"]
    assert output["answer"]["validation_issues"]


@pytest.mark.asyncio
async def test_role_model_malformed_json_returns_safe_partial_answer():
    objective=parse_semantic_plan(BASE,inventory_profile(ITEMS))
    async def malicious(messages,tools):
        return {"content":'{"measurement_roles":"wrong"}'}
    result,diag=await enrich_measurement_roles(objective,ITEMS,malicious)
    assert diag["outcome"]=="unavailable"
    assert diag["reason"]=="invalid_role_proposal"
    assert result==objective


@pytest.mark.asyncio
async def test_role_model_cannot_forge_names_or_invoke_mcp_tools():
    objective=parse_semantic_plan(BASE,inventory_profile(ITEMS))
    async def malicious(messages,tools):
        return {"tool_calls":[{"function":{"name":"hub_command"}}],
                "content":json.dumps({"measurement_roles":[
                    {"id":"9900","label":"House Supply Meter","role":"individual_load"}
                ]})}
    result,diag=await enrich_measurement_roles(objective,ITEMS,malicious)
    assert result==objective
    assert diag["outcome"]=="unavailable"


def test_singular_and_non_meter_questions_skip_second_model_phase():
    obj=parse_semantic_plan({
        **BASE,"scope":"named","device_name":"Fridge",
    },inventory_profile(ITEMS))
    async def forbidden(messages,tools):
        raise AssertionError("role inference invoked for named device")
    async def run():
        plan,diag=await enrich_measurement_roles(obj,ITEMS,forbidden)
        assert plan==obj
        assert diag["outcome"]=="not_applicable"
    asyncio.run(run())


def test_unknown_is_not_verified_individual_load_even_if_value_is_large():
    plan=parse_semantic_plan(BASE,inventory_profile(ITEMS))
    result=execute_inventory_plan(plan,ITEMS,{"complete":True})
    assert result["inventory_query"]["excluded_unknown_scope"]==len(ITEMS)
    assert result["inventory_query"]["matched_count"]==0
    assert "0 device(s)" in result["answer"]["text"] or "0 device" in result["answer"]["text"]


def test_untrusted_role_target_is_not_a_permission_to_write():
    with pytest.raises(ValueError):
        parse_semantic_plan({**BASE,"measurement_target":"control_all"},inventory_profile(ITEMS))
