"""Regression gates for V2 planner cold/slow starts and safe early evidence.

This suite uses a fake MCP manifest, fake ToolExecutor and fake model, never
the real Hubitat hub, provider, tokens or home automation controls.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"hubitat-mcp-ai"/"rootfs"/"app"))

from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect
from investigation_v2.evidence import build_case_file
from investigation_v2.planning_evidence import planning_evidence
from investigation_v2.source_identity import source_identity_proposals
from investigation_v2.model_adapter import V2ModelProposer
from investigation_v2.read_loop import run_read_only_investigation

FIXTURE=ROOT/"tests/fixtures/investigation_v2_overnight.json"


def case():
    obj=json.loads(FIXTURE.read_text())
    return build_case_file(obj["question"],obj["receipts"])


def app_gateway(*, mutation=False, arg_required=False):
    return MCPTool("hub_read_apps_code","CURRENT APP LIST",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_apps"]},
            "args":{"type":"object","properties":{"appId":{"type":"string"}},
                    "required":["appId"] if arg_required else [],
                    "additionalProperties":False},
        },"required":["tool","args"],"additionalProperties":False,
    },annotations={"readOnlyHint":not mutation})


def test_planning_evidence_retains_all_command_source_ids_and_exact_utc_local_clocks():
    from investigation_v2.temporal_scope import explicit_incident_window
    c=case()
    window=explicit_incident_window("overnight 24–25 October 2026",zone_name="Europe/London")
    compact=planning_evidence(c,window)
    payload=json.loads(compact)
    assert len(payload["records"])==len(c.records)
    assert {r["id"] for r in payload["records"]}=={r.record_id for r in c.records}
    assert len(compact)<len(c.evidence_brief())
    assert all(r["local"] for r in payload["records"])
    off=next(r for r in payload["records"] if r["action"]=="command-off"
             and "00:41:40" in r["local"])
    assert off["local"].endswith("+01:00")
    assert "23:41:40" in off["utc"]
    assert off["issuer_id"]=="4246"
    assert "secret" not in compact.lower()


def test_provenance_seed_uses_only_live_nonmutating_app_manifest():
    c=case()
    proposal=source_identity_proposals([app_gateway()],c)
    assert len(proposal)==1
    assert proposal[0]["arguments"]=={"tool":"hub_list_apps","args":{}}
    assert source_identity_proposals([app_gateway(mutation=True)],c)==[]
    assert source_identity_proposals([app_gateway(arg_required=True)],c)==[]
    assert source_identity_proposals([],c)==[]


class FakeMCP:
    def __init__(self,mutation=False):
        self.mutation=mutation
    async def list_tools(self):
        return [app_gateway(mutation=self.mutation)]


class FakeExecutor:
    def __init__(self,mcp):
        self.mcp=mcp
        self.calls=[]
    async def execute(self,name,args,*,tool,record_evidence):
        assert record_evidence is False
        self.calls.append((name,args,tool))
        result=MCPToolResult(name,args,raw={},text="DO NOT PRINT TOKEN",
                             data={"apps":[
                                 {"id":4246,"name":"Night Idle OFF TEST"},
                                 {"id":4019,"name":"Light Mode Controller"},
                                 {"id":1251,"name":"Button Rule"}
                             ]},is_error=False)
        return ToolExecution(name=name,arguments=args,effect=ToolEffect.READ,
                             success=True,elapsed_ms=1,content="DO NOT PRINT TOKEN",result=result)


@pytest.mark.asyncio
async def test_read_only_app_identity_succeeds_before_planner_timeout_without_model_permission():
    obj=json.loads(FIXTURE.read_text())
    mcp=FakeMCP()
    executor=FakeExecutor(mcp)
    calls=[]
    async def stalled(case,round_index):
        calls.append((len(case.records),dict(case.app_identities)))
        await asyncio.sleep(2.0)
        raise AssertionError("AI did not return in time")
    result=await run_read_only_investigation(
        question=obj["question"],mcp=mcp,executor=executor,
        propose=stalled,verified_entity_ids=["7805"],
        initial_receipts=obj["receipts"],max_total_reads=2,max_rounds=1,
        planning_timeout_seconds=1.0,bootstrap_source_identity=True,
    )
    assert result.stopped_because=="planning_timeout"
    assert result.executed_reads==1
    assert len(executor.calls)==1
    assert executor.calls[0][0]=="hub_read_apps_code"
    assert executor.calls[0][1]=={"tool":"hub_list_apps","args":{}}
    assert calls[0][1]["4246"]=="Night Idle OFF TEST"
    assert result.case.app_identities["4019"]=="Light Mode Controller"
    assert result.planning_diagnostics[0]["outcome"]=="timeout"
    assert result.planning_diagnostics[0]["case_records"]==len(result.case.records)
    assert result.planning_diagnostics[0]["input_chars"] is None
    assert "DO NOT PRINT TOKEN" not in json.dumps(result.to_dict())


@pytest.mark.asyncio
async def test_preflight_cannot_invoke_advertised_write_tool():
    obj=json.loads(FIXTURE.read_text())
    mcp=FakeMCP(mutation=True)
    executor=FakeExecutor(mcp)
    async def fast(case,round_index):
        return {"hypotheses":[],"reads":[],"finish":True}
    result=await run_read_only_investigation(
        question=obj["question"],mcp=mcp,executor=executor,
        propose=fast,verified_entity_ids=["7805"],initial_receipts=obj["receipts"],
        max_rounds=1,bootstrap_source_identity=True,
    )
    assert executor.calls==[]
    assert result.executed_reads==0
    assert result.stopped_because=="model_finished"


@pytest.mark.asyncio
async def test_prompt_metrics_capture_input_size_without_raw_data_or_model_text():
    messages=[]
    async def chat(msgs,tools):
        messages.append(msgs)
        return {"content":json.dumps({"hypotheses":[],"reads":[],"finish":True})}
    model=V2ModelProposer(chat,[app_gateway()],verified_entity_ids=["7805"])
    c=case()
    plan=await model(c,0)
    assert plan["finish"] is True
    assert model.last_prompt_chars>0
    assert model.advertised_tool_count==1
    prompt=json.loads(messages[0][1]["content"])
    compact=json.loads(prompt["case_file"])
    assert len(compact["records"])==len(c.records)
    assert {r["id"] for r in compact["records"]}=={r.record_id for r in c.records}
    assert "native" not in json.dumps(prompt).lower()


@pytest.mark.asyncio
async def test_planner_success_and_error_are_logged_only_as_bounded_metadata():
    mcp=FakeMCP()
    executor=FakeExecutor(mcp)
    async def fast(case,round_index):
        return {"hypotheses":[],"reads":[],"finish":True}
    result=await run_read_only_investigation(
        question="Can I safely investigate?",mcp=mcp,executor=executor,
        propose=fast,verified_entity_ids=[],max_rounds=1,
    )
    assert result.stopped_because=="model_finished"
    assert result.planning_diagnostics[0]["outcome"]=="returned"
    assert result.planning_diagnostics[0]["elapsed_ms"]>=0
    assert result.planning_diagnostics[0]["input_chars"] is None

    async def fail(case,round_index):
        raise RuntimeError("credential_do_not_log_secret")
    result2=await run_read_only_investigation(
        question="Why?",mcp=mcp,executor=executor,
        propose=fail,verified_entity_ids=[],max_rounds=1,
    )
    assert result2.stopped_because=="planning_unavailable"
    assert result2.planning_diagnostics[0]["outcome"]=="error"
    assert "credential_do_not_log_secret" not in json.dumps(result2.to_dict())

