"""v0.18.213 cross-domain benchmark: avoid futile model-only claim pass.

Source evidence remains authoritative. Coverage and elapsed time are PROXIES,
not proof of parity or superiority over an external V1 live result.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_answer_brief import evidence_brief,evidence_readiness
from investigation_v2.native_claim_verifier import claim_catalog
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, call)
from test_investigation_v2_general_operational_evidence_0_18_212 import _receipts


@pytest.mark.parametrize("question", [
    "Which devices are stale or have unknown activity?",
    "Summarise Hubitat health and prioritise the evidence.",
    "Investigate a system error and distinguish it from device failure.",
])
@pytest.mark.asyncio
async def test_general_multisource_uses_source_brief_without_extra_model_round(
        question):
    mcp=FakeMCP([READ_DIAG])
    executor=FakeExecutor(mcp,[
        {"staleDevices":[
            {"id":"7103","name":"Mesh outlet",
             "lastActivity":"2026-10-12T01:30:00+0100"}],
         "unknownDevices":[{"id":"7687","name":"Sensor",
                            "lastActivity":"never"}],"summary":{}},
        {"entries":[{"level":"WARN","type":"app",
                     "name":"Rule Server",
                     "message":"app|4151|Rule Server|some read failure",
                     "time":"2026-10-29 11:00:00"}]},
    ])
    count=0
    async def model(messages,tools):
        nonlocal count
        count+=1
        if count==1:return {"tool_calls":[call("hub_get_device_health")]}
        if count==2:return {"tool_calls":[call(
            "hub_get_logs",mode="past",level="warn",limit=100)]}
        raise AssertionError("Final claim-only pass should be skipped")
    answer=await run_native_read_agent(
        question=question,chat=model,mcp=mcp,executor=executor,
        max_rounds=2,max_reads=4)
    d=answer["native_diagnostics"]
    assert count==2
    assert d["reads_executed"]==2 and d["successful_reads"]==2
    assert d["final_synthesis_ms"]==0
    assert d["final_synthesis_skipped_reason"]=="multi_source_factual_brief_ready"
    assert d["source_grounded_brief_published"] is True
    assert d["general_evidence_readiness"]["accuracy_or_v1_superiority_measured"] is False
    report=answer["answer"]["text"]
    assert report.index("**Evidence-based summary**") < report.index(
        "**Independent claim validation")
    assert "Mesh outlet" in report
    assert "unknown activity" in report
    assert "offline" in report
    assert "source" in report.lower()
    assert len(executor.calls)==2


def test_readiness_requires_cross_source_at_budget_not_on_first_useful_read():
    rows=_receipts()
    cat=claim_catalog(rows)
    for reason in ("model_finished","model_unavailable","deadline_reached"):
        assert evidence_readiness(rows,cat,stop_reason=reason)[
            "host_factual_brief_ready"] is False
    assert evidence_readiness(rows,cat,stop_reason="round_budget_reached")[
        "host_factual_brief_ready"] is True
    alone=[{"read":1,"operation":"hub_get_device",
            "source_data":{"id":"1","attributes":[
                {"name":"switch","value":"on"}]}}]
    assert not evidence_readiness(alone,claim_catalog(alone),
        stop_reason="round_budget_reached")["host_factual_brief_ready"]


def test_generic_brief_leads_with_source_health_and_dependencies_not_switch():
    rows=_receipts()
    text=evidence_brief(claim_catalog(rows))
    assert text.startswith("**Evidence-based summary**")
    assert "51" in text and "stale" in text
    assert "unknown activity" in text
    assert "app references" in text
    assert "offline" in text
    assert "active" not in text
    assert text.count("lastActivity=")<=2
    assert len(text.splitlines())<=10


def test_brief_cannot_publish_model_injected_text_or_invent_absence():
    rows=_receipts()
    c=claim_catalog(rows)
    assert "HUB BROKEN" not in evidence_brief(c)
    c.append({"id":"claim-999","statement":"HUB BROKEN",
              "evidence_reads":[],"root_cause_verified":False,"kind":"warning"})
    assert "HUB BROKEN" not in evidence_brief(c)
    assert evidence_brief([])==""
    assert "all devices healthy" not in evidence_brief(c).lower()


def test_general_readiness_reports_only_proxies_not_v1_parity():
    r=evidence_readiness(_receipts(),claim_catalog(_receipts()),
                         stop_reason="read_budget_reached")
    assert r["verified_catalog_facts"]>=4
    assert r["distinct_verified_read_operations"]>=3
    assert r["distinct_verified_fact_kinds"]>=3
    assert r["accuracy_or_v1_superiority_measured"] is False


@pytest.mark.asyncio
async def test_no_evidence_does_not_fake_summary_or_shortcut_source_checks():
    mcp=FakeMCP([READ_DIAG]); executor=FakeExecutor(mcp,[{}])
    count=0
    async def model(messages,tools):
        nonlocal count
        count+=1
        if count==1:return {"tool_calls":[call("hub_get_device_health")]}
        return {"content":'{"claims":[]}'}
    result=await run_native_read_agent(
        question="Is my hub healthy?",chat=model,mcp=mcp,executor=executor,
        max_rounds=2,max_reads=2)
    assert count==2
    assert result["native_diagnostics"]["final_synthesis_skipped_reason"] is None
    assert result["native_diagnostics"]["source_grounded_brief_published"] is False
