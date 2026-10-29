"""v0.18.208: exact replay of focus loss and unscoped app stats, 29 Oct.

No silent ID inference from a model or broad hub data. A verified targeted
device read must echo the subject ID and the user must mention that subject.
Runtime stats in a global page only count for independently attested callers.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_focus_anchor import verified_device_focus
from investigation_v2.native_source_adapters import compact_logs
from investigation_v2.native_runtime_stats import (
    project_log_runtime_stats, focused_runtime_stat_receipts)
from investigation_v2.native_causal_claim_audit import (
    incident_attribution_packet, evidence_safe_incident_explanation)
from investigation_v2.native_fact_ledger import factual_evidence_ledger
from investigation_v2.native_claim_verifier import claim_catalog
from investigation_v2.native_evidence_focus import (
    focused_highlights, focused_model_view)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_verified_focus_0_18_204 import _read, _call
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def _logs(device_id="7934"):
    return compact_logs({"entries":[{
        "level":"WARN","type":"dev","name":"Google Nest Hub",
        "time":stamp,
        "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
    } for stamp in (
        "2026-10-29 08:59:59.642",
        "2026-10-29 09:00:04.669",
        "2026-10-29 09:00:07.793",
        "2026-10-29 09:00:09.478"
    )]})


def _events():
    return {"events":[
        {"name":"command-setVolume","date":"2026-10-29T08:59:59.657+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-speak","date":"2026-10-29T09:00:01.109+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"command-setVolume","date":"2026-10-29T09:00:07.808+0000",
         "producedBy":{"appId":"4080","name":"00 Google Calendar Notifier"}},
        {"name":"status","value":"idle","date":"2026-10-29T09:00:09.478+0000",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
    ]}


def _stats(mode):
    rows=([
        {"id":7934,"name":"Google Nest Hub - [Google Nest Hub]",
         "pct":89.48085758694425,"count":20253,"total":47727579},
    ] if mode=="devices" else [
        {"id":4129,"name":"SenseCap D1 Settings",
         "pct":24.7,"count":28480,"total":6907283},
        {"id":4080,"name":"00 Google Calendar Notifier",
         "pct":7.073027573076396,"count":829,"total":1977482},
        {"id":1679,"name":"Adhan Player",
         "pct":4.2,"count":120,"total":85000},
    ])
    return project_log_runtime_stats({"mode":mode,"entries":rows,"total":370})


def _receipts():
    return [
        {"read":1,"operation":"hub_get_logs","read_filters":{},
         "source_data":{"log_summary":compact_logs({"entries":[{
             "level":"WARN","type":"app","name":"SenseCap D1 Settings",
             "time":"2026-10-29 09:56:39.490",
             "message":"app|4129|SenseCap D1 Settings|live push failed"
         }]})}},
        {"read":2,"operation":"hub_get_logs",
         "read_filters":{"deviceId":"7934","mode":"past","level":"warn"},
         "source_data":{"log_summary":_logs()}},
        {"read":3,"operation":"hub_get_logs",
         "read_filters":{"mode":"devices","deviceId":"7934"},
         "source_data":{"runtime_stats":_stats("devices")}},
        {"read":4,"operation":"hub_list_device_events",
         "read_filters":{"deviceId":"7934"},
         "source_data":{"issuer_apps":[{
             "appId":"4080","name":"00 Google Calendar Notifier",
             "count":3,"commands":{"setVolume":2,"speak":1}}],
             **_events()}},
        {"read":5,"operation":"hub_get_logs",
         "read_filters":{"mode":"apps"},
         "source_data":{"runtime_stats":_stats("apps")}},
    ]


def test_target_warning_and_runtime_receipts_can_anchor_no_device_config_read():
    question="Investigate Google Nest Hub (device 7934) excessive load"
    logs=_logs()
    anchored=verified_device_focus(question,"hub_get_logs",
        {"mode":"past","deviceId":"7934"},
        {"log_summary":logs},{"7934"})
    assert anchored=={
        "device_id":"7934","identity_basis":"explicit_verified_device_id",
        "source_kind":"target_log"}
    anchored=verified_device_focus(question,"hub_get_logs",
        {"mode":"devices","deviceId":"7934"},
        {"runtime_stats":_stats("devices")},{"7934"})
    assert anchored["source_kind"]=="device_runtime"
    anchored=verified_device_focus(question,"hub_list_device_events",
        {"deviceId":"7934"},_events(),{"7934"})
    assert anchored["source_kind"]=="device_event"


@pytest.mark.parametrize("operation,args,source,verified",[
    ("hub_get_logs",{},{"log_summary":_logs()},{"7934"}),
    ("hub_get_logs",{"deviceId":"7103","mode":"past"},
        {"log_summary":_logs()},{"7934","7103"}),
    ("hub_get_logs",{"deviceId":"7934","mode":"past"},
        {"log_summary":_logs()},set()),
    ("hub_get_logs",{"deviceId":"7934","mode":"devices"},
        {"runtime_stats":_stats("apps")},{"7934"}),
    ("hub_list_device_events",{"deviceId":"7934"},
        {"events":[{"name":"command-speak","producedBy":{"appId":"4080"}}]},
        {"7934"}),
])
def test_no_focus_from_unscoped_mismatch_unverified_or_only_app_command(
        operation,args,source,verified):
    assert verified_device_focus(
        "Investigate device 7934",operation,args,source,verified) is None


def test_no_focus_on_generic_hub_audit_even_with_matching_source():
    assert verified_device_focus(
        "Review general hub performance","hub_get_logs",
        {"deviceId":"7934","mode":"past"},
        {"log_summary":_logs()},{"7934"}) is None


def test_verified_name_without_numeric_id_can_anchor_target_log():
    assert verified_device_focus(
        "Why is Google Nest Hub generating warnings?",
        "hub_get_logs",{"deviceId":"7934","mode":"past"},
        {"log_summary":_logs()},{"7934"})["device_id"]=="7934"


def test_global_app_stats_filtered_by_attested_caller_but_not_unrelated_app():
    rows=_receipts()
    stats=focused_runtime_stat_receipts(rows,["7934"])
    assert [(x["kind"],x["id"]) for x in stats]==[
        ("devices","7934"),("apps","4080")]
    assert all(x["incident_time_aligned"] is False for x in stats)
    facts=factual_evidence_ledger(rows,["7934"])
    assert [(x["source_kind"],x["source_id"]) for x in facts
            if x["kind"]=="cumulative_runtime_stats"]==[
                ("devices","7934"),("apps","4080")]
    catalog=claim_catalog(rows,["7934"])
    metrics=[x for x in catalog if x["kind"]=="runtime_stat"
             and x["metric"]=="pct"]
    assert {x["scope"]:round(x["numeric"],3) for x in metrics}=={
        "7934":89.481,"4080":7.073}
    assert all(x["root_cause_verified"] is False for x in metrics)
    assert all(x["scope"]!="4129" for x in catalog)
    highlights=" ".join(focused_highlights(rows,["7934"]))
    assert "pct=89.480" in highlights
    assert "pct=7.073" in highlights
    assert "SenseCap D1 Settings" not in highlights
    model_view=focused_model_view(
        "hub_get_logs",{"runtime_stats":_stats("apps")},["7934"],
        caller_app_ids=["4080"])
    assert [x["id"] for x in model_view["runtime_stats"]["rows"]]==["4080"]
    packet=incident_attribution_packet(rows,["7934"])
    assert len(packet["runtime_performance_snapshots"])==2
    report=evidence_safe_incident_explanation(packet)
    assert "pct=89.480" in report and "pct=7.073" in report
    assert "SenseCap D1 Settings" not in report


def test_unscoped_app_snapshot_without_verified_issuer_cannot_contribute():
    rows=_receipts()
    rows[3]["source_data"]["issuer_apps"]=[]
    assert [(x["kind"],x["id"]) for x in
            focused_runtime_stat_receipts(rows,["7934"])]==[
                ("devices","7934")]
    rows=_receipts()
    rows[4]["read_filters"]={"mode":"apps","appId":"4129"}
    assert [(x["kind"],x["id"]) for x in
            focused_runtime_stat_receipts(rows,["7934"])]==[
                ("devices","7934")]


@pytest.mark.asyncio
async def test_full_read_agent_replay_anchors_from_warn_and_skips_failed_synthesis():
    mcp=FakeMCP([
        _read("hub_read_diagnostics",["hub_get_logs"]),
        _read("hub_read_devices",["hub_list_device_events"]),
    ])
    async def identities():
        return [{"id":"7934","name":"Google Nest Hub",
                 "label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"entries":[{"level":"WARN","type":"app","name":"SenseCap D1 Settings",
            "time":"2026-10-29 09:56:39.490",
            "message":"app|4129|SenseCap D1 Settings|live push failed"}]},
        {"entries":[{
            "level":"WARN","type":"dev","name":"Google Nest Hub",
            "time":stamp,
            "message":"dev|7934|Google Nest Hub|Device 7934 generates excessive hub load",
        } for stamp in ["2026-10-29 08:59:59.642",
                        "2026-10-29 09:00:04.669",
                        "2026-10-29 09:00:07.793",
                        "2026-10-29 09:00:09.478"]]},
        {"mode":"devices","entries":[{
            "id":7934,"name":"Google Nest Hub","pct":89.48085758694425,
            "count":20253,"total":47727579}]},
        _events(),
        {"mode":"apps","entries":[{
            "id":4129,"name":"SenseCap D1 Settings","pct":24.7},
            {"id":4080,"name":"00 Google Calendar Notifier",
             "pct":7.073027573076396,"count":829,"total":1977482}]},
    ])
    # Four rounds, no final model-only pass. Every operation is model-selected.
    calls=0
    async def model(messages,tools):
        nonlocal calls
        calls+=1
        assert tools, "A source-authoritative incident needs no model synthesis"
        if calls==1:return {"tool_calls":[
            _call("hub_read_diagnostics","hub_get_logs",limit=100)]}
        if calls==2:return {"tool_calls":[
            _call("hub_read_diagnostics","hub_get_logs",mode="past",
                  deviceId="7934",level="warn",limit=100)]}
        if calls==3:return {"tool_calls":[
            _call("hub_read_diagnostics","hub_get_logs",mode="devices",
                  deviceId="7934"),
            _call("hub_read_devices","hub_list_device_events",
                  deviceId="7934",limit=50)]}
        if calls==4:return {"tool_calls":[
            _call("hub_read_diagnostics","hub_get_logs",mode="apps")]}
        raise AssertionError("Unexpected fifth model call")
    result=await run_native_read_agent(
        question="Investigate Google Nest Hub device 7934 hub load warnings",
        mcp=mcp,executor=executor,chat=model,max_rounds=4,max_reads=5)
    d=result["native_diagnostics"]
    assert d["focus_ids"]==["7934"]
    assert d["verified_focus_receipts"][0]["source_kind"]=="target_log"
    assert d["verified_focus_receipts"][0]["read"]==2
    assert d["final_synthesis_ms"]==0
    assert d["claim_publication"]["authority"]=="host_incident_receipts"
    assert d["claim_publication"]["rejected_reasons"]==[]
    assert d["incident_attribution_evidence"]["warning_command_temporal_leads"][
        "warning_clusters"][-1]["commands_in_window_with_edges"]==3
    assert len(d["incident_attribution_evidence"]["runtime_performance_snapshots"])==2
    report=result["answer"]["text"]
    assert "00 Google Calendar Notifier" in report
    assert "pct=89.480" in report and "pct=7.073" in report
    assert "SenseCap D1 Settings reported warning" not in report
    assert result["resolved_devices"]==["7934"]
    assert calls==4
    assert len(executor.calls)==5
