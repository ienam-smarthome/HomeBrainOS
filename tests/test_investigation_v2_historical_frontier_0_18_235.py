"""v0.18.235: historical source frontier, not another fallback patch.

Replay a 14:54 controller command, app-specific empty incident log reads,
and a 45-row app log sample whose oldest returned row is 16:34.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool
from investigation_v2.native_historical_frontier import (
    historical_controller_frontier, reject_redundant_controller_logs)
from investigation_v2.native_incident_relevance import dated_incident_evidence
from investigation_v2.native_reasoned_assessment import verify_natural_hypothesis
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_event_reasoning_0_18_232 import QUESTION, thermostat_events
from test_investigation_v2_incident_relevance_0_18_229 import history
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def historical_receipts():
    return [
        history(4,thermostat_events(),device="4382"),
        {
            "read":6,"operation":"hub_get_logs",
            "read_filters":{"appId":"3970",
                "since":"2026-10-29T14:40:00+00:00",
                "until":"2026-10-29T15:00:00+00:00"},
            "source_data":{"log_summary":{
                "returned_rows":0,"total_reported_by_gateway":45,
                "oldest_returned":None,"newest_returned":None,
                "truncated_or_partial":True,
            }},
        },
        {
            "read":8,"operation":"hub_get_logs",
            "read_filters":{"appId":"3970",
                "since":"2026-10-29T00:00:00+00:00",
                "until":"2026-10-30T00:00:00+00:00"},
            "source_data":{
                "log_summary":{
                    "returned_rows":45,"total_reported_by_gateway":45,
                    "oldest_returned":"2026-10-29 16:34:08.971",
                    "newest_returned":"2026-10-29 23:00:03.723",
                    "truncated_or_partial":False,
                },
                "app_execution_lines":[{
                    "date":"2026-10-29 22:19:28.981",
                    "source_app_id":"3970",
                    "source_name":"00 Smart Thermostat Scheduler",
                    "message":"Demand coordination: NO HEAT REQUIRED",
                }],
            },
        },
    ]


def test_old_app_decision_is_missing_from_returned_window_not_proven_nonexistent():
    rows=historical_receipts()
    coverage=dated_incident_evidence(QUESTION,rows,["4382"])
    assert coverage["controller_decision_log_count"]==0
    result=historical_controller_frontier(QUESTION,rows,["4382"],coverage)
    assert result["app_id"]=="3970"
    assert result["status"]=="incident_not_in_returned_app_log_window"
    assert "16:34:08" in result["earliest_source_log_timestamp"]
    assert result["source_history_complete"] is False
    assert result["incident_time_zone_verified"] is False
    assert reject_redundant_controller_logs(
        "hub_get_logs",{"appId":"3970","since":"2026-10-29 14:40:00"},result)
    assert not reject_redundant_controller_logs(
        "hub_list_device_events",{"deviceId":"4382"},result)
    assert not reject_redundant_controller_logs(
        "hub_get_logs",{"appId":"2710"},result)


def test_one_empty_app_log_read_does_not_prove_all_archives_are_empty():
    rows=historical_receipts()[:2]
    coverage=dated_incident_evidence(QUESTION,rows,["4382"])
    frontier=historical_controller_frontier(QUESTION,rows,["4382"],coverage)
    assert frontier["status"]=="incident_not_observed_in_scoped_app_log_reads"
    assert not reject_redundant_controller_logs(
        "hub_get_logs",{"appId":"3970"},frontier)


def test_observed_incident_decision_disables_missing_log_conclusion():
    rows=historical_receipts()
    rows[-1]["source_data"]["app_execution_lines"].append({
        "date":"2026-10-29 14:54:18.073",
        "source_app_id":"3970",
        "source_name":"00 Smart Thermostat Scheduler",
        "message":"Actual input demand decision",
    })
    coverage=dated_incident_evidence(QUESTION,rows,["4382"])
    frontier=historical_controller_frontier(QUESTION,rows,["4382"],coverage)
    assert frontier["status"]=="incident_decision_logs_observed"
    assert not reject_redundant_controller_logs(
        "hub_get_logs",{"appId":"3970"},frontier)


def test_other_controller_latest_command_not_selected_for_missing_window():
    rows=historical_receipts()
    rows[0]["source_data"]["events"].insert(0,{
        "name":"command-setThermostatMode",
        "date":"2026-10-29T22:30:01.589+00:00",
        "producedBy":{"appId":"2710","name":"Evening thermostat off"},
    })
    coverage=dated_incident_evidence(QUESTION,rows,["4382"])
    frontier=historical_controller_frontier(QUESTION,rows,["4382"],coverage)
    assert frontier["app_id"]=="3970"


def test_unverified_numeric_in_optional_alternative_does_not_erase_valid_main_reasoning():
    events=dated_incident_evidence(QUESTION,historical_receipts(),["4382"])
    good=[
        e for e in events["material_event_examples"]
        if e["name"] in ("thermostatOperatingState","heatingSetpoint")
        and e["date"].startswith("2026-10-29T14:54")
    ]
    assert len(good)>=2
    cited=[{"read":row["read"],"name":row["name"],"date":row["date"]}
           for row in good[:2]]
    proposal={
        "hypothesis":"The controller lowered the heating target and the thermostat subsequently became idle.",
        "confidence":"possible",
        "supporting_events":cited,
        "alternative":"Perhaps 9999°C caused a different action",
        "next_check":"Review the independently stored room sensor history.",
    }
    answer=verify_natural_hypothesis(proposal,coverage=events)
    assert answer["accepted"] is True
    assert answer["optional_alternative_withheld"] is True
    assert "9999" not in answer["text"]
    assert "subsequently became idle" in answer["text"]
    proposal["hypothesis"]="The controller lowered the target at 9999°C"
    assert verify_natural_hypothesis(proposal,coverage=events)["accepted"] is False


READ_WITH_INVENTORY=MCPTool(
    "hub_read_devices","Read-only devices and history",
    {"type":"object","properties":{
        "tool":{"type":"string","enum":[
            "hub_list_devices","hub_get_device","hub_list_device_events"]},
        "args":{"type":"object","additionalProperties":True}},
     "required":["tool","args"]},
    annotations={"readOnlyHint":True},
)


@pytest.mark.asyncio
async def test_named_dated_incident_does_not_execute_20_second_whole_hub_device_list():
    mcp=FakeMCP([READ_WITH_INVENTORY])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"events":thermostat_events()}])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[native(
                "homebrain_find_device",{"name":"Thermostat"})]}
        if step==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_devices","args":{}})]}
        if step==3:
            assert "bounded_identity_candidates_available" in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events",
                "args":{"deviceId":"4382"}})]}
        return {"content":"A source-verified controller lowered the target."}
    result=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=4,max_reads=3)
    assert [call[1]["tool"] for call in executor.calls]==["hub_list_device_events"]
    assert any(f.get("code")=="bounded_identity_candidates_available"
               for f in result["native_diagnostics"]["failures"])
