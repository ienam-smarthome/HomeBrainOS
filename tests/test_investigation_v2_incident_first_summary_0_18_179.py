"""Read-only incident-first explanation and no-futile-plan replay.

The Oct 28 live case had an attested 4020 OFF, a matching 7790 switch
report and a configured motion sensor inactive 56.387s earlier, yet the
answer showed an unrelated 4129 historical interaction and wasted ~32s
of AI planning after all eight host reads were used.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPToolResult
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.incident_summary import latest_switch_incident
from investigation_v2.investigation_report import format_investigation_report
from investigation_v2.read_loop import run_read_only_investigation


def typed_events(device_id, events, name):
    args={"tool":"hub_list_device_events","args":{
        "deviceId":device_id,"hoursBack":24,"limit":100}}
    result=MCPToolResult("hub_read_devices",args,raw={},text="UNTRUSTED",
                         data={"deviceId":device_id,"events":events})
    return project_read_receipt("hub_read_devices",args,result,
                                source_request_id=name,
                                read_at="2026-10-28T13:50:00+00:00")


def fixture():
    history=[]
    for x in range(25):
        history.append({
            "deviceId":"7828","name":"command-setLevel","type":"command",
            "date":f"2026-10-23T{(x%24):02}:10:00+00:00",
            "producedBy":{"id":"4129" if x%2 else "1252"}})
    history += [
        {"deviceId":"7828","name":"command-off","type":"command",
         "date":"2026-10-28T00:14:56.868+00:00",
         "producedBy":{"id":"4020"}},
        {"deviceId":"7828","name":"switch","value":"off",
         "date":"2026-10-28T00:14:57.111+00:00",
         "producedBy":{"id":"7790"}},
    ]
    motion=[
        {"deviceId":"7978","name":"motion","value":"active",
         "date":"2026-10-27T23:31:57.678+00:00",
         "producedBy":{"id":"7718"}},
        {"deviceId":"7978","name":"motion","value":"inactive",
         "date":"2026-10-28T00:14:00.481+00:00",
         "producedBy":{"id":"7718"}},
    ]
    config_args={"tool":"hub_get_app_config",
                 "args":{"appId":"4020","includeSettings":True}}
    config_data={"app":{"id":"4020"},"settings":{
        "motionSensors":{"7978":"FP400 motion"},
        "keepOnSensors":{"7778":"Keep on"},
        "inactiveAction":"off",
        "backupOffEnabled":True,
        "scheduledOffEnabled":False}}
    settings=project_read_receipt("hub_read_apps_code",config_args,
        MCPToolResult("hub_read_apps_code",config_args,raw={},text="PRIVATE",
                      data=config_data),
        source_request_id="config",read_at="2026-10-28T13:50:00+00:00")
    result=[
        typed_events("7828",history,"device-history"),
        typed_events("7978",motion,"motion-history"),
        settings,
    ]
    return result, build_case_file("Investigate latest OFF",result)


def test_current_off_has_source_proven_issuer_motion_and_report_intervals():
    _,case=fixture()
    item=latest_switch_incident(case)
    assert item is not None
    assert item["issuer_app_id"]=="4020"
    assert item["target_id"]=="7828"
    assert item["interval_ms"]==243
    assert item["recent_motion_observations"]==1
    rendered="\n".join(item["lines"])
    assert "56.387 seconds" in rendered
    assert "motion=inactive" in rendered
    assert "7790" not in rendered or "state reporter" in rendered.lower()
    assert "inactiveAction=off" in rendered
    assert "Keep-on sensor coverage" in rendered
    assert "historical handler branch" in rendered
    assert item["root_cause_verified"] is False
    assert "physical light response" in rendered


def test_investigation_report_does_not_lead_with_old_competing_controllers():
    _,case=fixture()
    report=format_investigation_report(
        case,[],"source_backed_read_budget_reached")
    assert "**Latest OFF/ON incident — source evidence**" in report
    assert report.index("56.387 seconds") < report.index("**Recorded timeline**")
    assert "Possible competing controllers:" not in report
    assert "Another OFF was issued" not in report
    assert "no additional model planning" in report.lower()
    assert report.count("00:14:56")>=1
    assert report.count("00:14:57")>=1
    assert "source #4129 issued OFF" not in report


def test_unpaired_later_state_blocks_wrong_attribution():
    receipts,case=fixture()
    latest=typed_events("7828",[
        {"deviceId":"7828","name":"switch","value":"on",
         "date":"2026-10-28T00:20:00+00:00",
         "producedBy":{"id":"7790"}}
    ],"newest-report")
    unpaired=build_case_file("latest",receipts+[latest])
    assert latest_switch_incident(unpaired) is None
    assert "Most likely explanation (source-backed)" not in (
        format_investigation_report(unpaired,[],"model_finished"))


def test_historical_explicit_window_does_not_force_latest_report():
    from investigation_v2.temporal_scope import IncidentWindow
    _,case=fixture()
    window=IncidentWindow(
        start_utc="2026-10-22T00:00:00+00:00",
        end_utc="2026-10-23T00:00:00+00:00",
        zone_name="Europe/London",
        interpretation="explicit_historical_fixture",
    )
    report=format_investigation_report(case,[],"model_finished",window)
    assert "**Latest OFF/ON incident — source evidence**" not in report


class EmptyMCP:
    async def list_tools(self):
        return []


class EmptyExecutor:
    def __init__(self,mcp):
        self.mcp=mcp
    async def execute(self,*args,**kwargs):
        raise AssertionError("No new Hubitat reads or writes may execute")


@pytest.mark.asyncio
async def test_read_budget_exhausted_skips_unexecutable_model_round():
    receipts,_=fixture()
    mcp=EmptyMCP()
    calls=[]
    async def model(case,index):
        calls.append(index)
        raise AssertionError("Provider not needed when READ budget exhausted")
    r=await run_read_only_investigation(
        question="Investigate why Livingroom Light 2 turned OFF most recently.",
        mcp=mcp,executor=EmptyExecutor(mcp),propose=model,
        verified_entity_ids=("7828",),initial_receipts=receipts,
        bootstrap_source_identity=True,
        max_total_reads=0,max_rounds=1,
    )
    assert not calls
    assert r.executed_reads==0
    assert r.stopped_because=="source_backed_read_budget_reached"
    assert r.planning_rounds==0
    assert r.planning_diagnostics==[]
    assert any(row.get("stage")=="source_first_decision" and
               row.get("model_planning_skipped") is True
               for row in r.bootstrap_diagnostics)


@pytest.mark.asyncio
async def test_read_capacity_remaining_preserves_ai_planner_opportunity():
    receipts,_=fixture()
    mcp=EmptyMCP()
    calls=[]
    async def model(case,index):
        calls.append(index)
        return {"hypotheses":[],"reads":[],"finish":True}
    r=await run_read_only_investigation(
        question="Investigate why Livingroom Light 2 turned OFF most recently.",
        mcp=mcp,executor=EmptyExecutor(mcp),propose=model,
        verified_entity_ids=("7828",),initial_receipts=receipts,
        bootstrap_source_identity=True,
        max_total_reads=8,max_rounds=1,
    )
    assert calls==[0]
    assert r.stopped_because=="model_finished"
    assert r.planning_diagnostics[0]["budget_policy"]=="source_first_advisory"
    assert r.planning_diagnostics[0]["budget_ms"]<=7000
