"""Regression for the live 0.18.233 reasoning gap.

The newest command in the history belonged to an unrelated controller at
22:30.  The question concerned the 14:54 scheduler shutdown.  The
model read app configuration, finished, and never investigated the app's
actual decision logs.  A single host *critique* may ask the model for a
new read, but never bypasses the MCP read-only manifest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_controller_decision import controller_decision_followup
from investigation_v2.native_incident_relevance import dated_incident_evidence
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_event_reasoning_0_18_232 import (
    QUESTION, thermostat_events,
)
from test_investigation_v2_incident_relevance_0_18_229 import (
    history, READ_EVENTS,
)
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor, READ_DIAG, READ_APPS,
)
from test_investigation_v2_controller_decision_0_18_233 import raw_logs


def late_unrelated_command():
    return [
        {"name":"command-setThermostatMode",
         "date":"2026-10-29T22:30:01.589+00:00",
         "producedBy":{"appId":"2710","name":"Heating: Thermostat OFF"}},
        {"name":"thermostatMode","value":"off",
         "date":"2026-10-29T22:30:01.844+00:00",
         "producedBy":{"deviceId":"4382","name":"Thermostat"}},
    ]


def live_history():
    return sorted(thermostat_events()+late_unrelated_command(),
                  key=lambda e:e["date"],reverse=True)


def test_incident_clock_beats_a_later_command_from_another_automation():
    witness=[history(1,live_history(),device="4382")]
    coverage=dated_incident_evidence(QUESTION,witness,["4382"])
    hint=controller_decision_followup(
        witness,["4382"],coverage,app_logs_offered=True,question=QUESTION)
    assert hint["issuer_selection_basis"]=="user_incident_clock_nearest_command"
    assert hint["observed_issuer_app_id"]=="3970"
    assert hint["observed_issuer_label"]=="00 Smart Thermostat Scheduler"
    assert hint["proposed_read"]["args"]["since"].startswith("2026-10-29T14:42")
    assert hint["proposed_read"]["args"]["until"].startswith("2026-10-29T15:06")


def test_unrelated_incident_clock_does_not_select_an_arbitrary_app():
    q="Why did the thermostat stop at 17:45 on 29 October 2026?"
    witness=[history(1,live_history(),device="4382")]
    coverage=dated_incident_evidence(q,witness,["4382"])
    assert controller_decision_followup(
        witness,["4382"],coverage,app_logs_offered=True,question=q) is None
    assert controller_decision_followup(
        witness,["4382"],coverage,app_logs_offered=False,question=q) is None


@pytest.mark.asyncio
async def test_model_gets_one_extra_chance_to_inspect_upstream_app_info():
    mcp=FakeMCP([READ_EVENTS,READ_APPS,READ_DIAG])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[
        {"events":live_history()},
        {"success":True,"app":{"id":"3970","label":"00 Smart Thermostat Scheduler"},
         "page":{"name":"mainPage"},"settingsKeyCount":88},
        raw_logs(),
    ])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[native(
                "homebrain_find_device",{"name":"Thermostat"})]}
        if step==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events","args":{"deviceId":"4382"}})]}
        if step==3:
            assert "upstream_controller_decision_gap" in messages[-1]["content"]
            assert "3970" in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_apps_code",{
                "tool":"hub_get_app_config","args":{"appId":"3970"}})]}
        if step==4:
            return {"content":"The thermostat was set to 12 degrees."}
        if step==5:
            assert "configuration metadata" in messages[-1]["content"]
            assert "3970" in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_diagnostics",{
                "tool":"hub_get_logs","args":{
                    "appId":"3970","mode":"past",
                    "since":"2026-10-29T14:42:18+00:00",
                    "until":"2026-10-29T15:06:18+00:00",
                    "limit":100}})]}
        assert step==6
        assert "controller_decision_log_examples" in messages[-1]["content"]
        assert "satisfied" in messages[-1]["content"]
        return {"content":json.dumps({
            "hypothesis":"The scheduler reported the room was satisfied at 22.0°C before ending the heat call.",
            "confidence":"possible",
            "supporting_events":[
                {"read":1,"name":"thermostatOperatingState",
                 "date":"2026-10-29T14:54:36.587+00:00"},
                {"read":3,"name":"app_log",
                 "date":"2026-10-29 14:54:18.073"}],
            "alternative":"A different input may also have changed the demand.",
            "next_check":"Compare source-reported TRV history at the incident time."
        })}
    out=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=7,max_reads=4,
        enable_model_reasoned_assessment=True)
    assert step==6
    assert [x[1]["tool"] for x in executor.calls] == [
        "hub_list_device_events","hub_get_app_config","hub_get_logs"]
    d=out["native_diagnostics"]
    assert d["upstream_decision_challenge_used"] is True
    assert d["model_reasoned_assessment"]["accepted"] is True
    assert d["concise_answer_source"]=="model_cited_incident_assessment"
    assert "satisfied" in out["answer"]["text"]
    assert "4382" not in out["answer"]["text"]


@pytest.mark.asyncio
async def test_no_historical_logs_permission_means_no_extra_model_challenge():
    mcp=FakeMCP([READ_EVENTS,READ_APPS])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"events":live_history()}])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:
            return {"tool_calls":[native(
                "homebrain_find_device",{"name":"Thermostat"})]}
        if step==2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events","args":{"deviceId":"4382"}})]}
        return {"content":"The controller lowered the target and heating stopped."}
    out=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=4,max_reads=3,
        enable_model_reasoned_assessment=True)
    assert step==3
    assert out["native_diagnostics"]["upstream_decision_challenge_used"] is False
