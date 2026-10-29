"""v0.18.209: live-operation contract feedback and bounded evidence frontier.

The model still chooses every read. Tool descriptions may document required
nested fields for *live enumerated operations only*. Rejected calls are never
repaired or executed by the host. An event read is a bounded observation,
not a declaration that historical coverage is complete.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.native_read_contracts import (
    advertised_operation_contracts, read_contract_feedback)
from investigation_v2.native_read_agent import _model_tools, run_native_read_agent
from test_investigation_v2_verified_focus_0_18_204 import _read, _call
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def test_only_live_gateway_enum_operations_are_described():
    manifest = {
        "hub_read_devices": _read(
            "hub_read_devices", ["hub_get_device", "hub_list_device_events"]),
        "hub_read_apps_code": _read(
            "hub_read_apps_code", ["hub_get_app_config"]),
    }
    offered=_model_tools(manifest)
    descriptions={item["function"]["name"]:item["function"]["description"]
                  for item in offered}
    assert "hub_get_device: args.deviceId REQUIRED" in descriptions["hub_read_devices"]
    assert "hub_list_device_events: args.deviceId" in descriptions["hub_read_devices"]
    assert "hub_get_app_config" not in descriptions["hub_read_devices"]
    assert "hub_get_app_config: args.appId REQUIRED" in descriptions["hub_read_apps_code"]
    assert "hub_get_device" not in descriptions["hub_read_apps_code"]
    assert offered[0]["function"]["parameters"] == manifest["hub_read_devices"].input_schema
    assert advertised_operation_contracts(["hub_delete_device", "hub_reboot"]) == ""


def test_failed_device_read_receives_exact_verified_target_example():
    feedback=read_contract_feedback(
        "hub_read_devices",
        {"tool":"hub_get_device","args":{"mode":"configuration"}},
        {"device":{"3951","7934","7103","1089","7776","7935",
                   "7790","7810","7853","7104"},
         "app":{"4080"}, "driver":set()},
        focus_ids=["7934"])
    assert feedback is not None
    assert feedback["required_shape"] == {
        "tool":"hub_get_device", "args":{"deviceId":"7934"}}
    assert feedback["verified_focus_device_id"]=="7934"
    assert feedback["verified_id_choices"]["device"][0]=="7934"
    assert feedback["read_only"] is True
    assert feedback["host_execution_attempted"] is False
    assert feedback["schema_examples_are_not_authorisation"] is True


def test_unverified_or_ambiguous_focus_can_never_supply_concrete_id():
    typed={"device":{"7934","7103"},"app":set(),"driver":set()}
    args={"tool":"hub_get_device","args":{}}
    no_focus=read_contract_feedback(
        "hub_read_devices",args,typed,focus_ids=["9999"])
    assert no_focus["required_shape"]["args"]["deviceId"]=="verified device ID"
    assert "verified_focus_device_id" not in no_focus
    multi=read_contract_feedback(
        "hub_read_devices",args,typed,focus_ids=["7934","7103"])
    assert multi["required_shape"]["args"]["deviceId"]=="verified device ID"
    assert "verified_focus_device_id" not in multi


def test_app_and_source_contracts_remain_separate_namespaces():
    typed={"device":{"7934"},"app":{"4080"},"driver":set()}
    config=read_contract_feedback("hub_read_apps_code",
        {"tool":"hub_get_app_config","args":{}},
        typed,focus_ids=["7934"])
    assert config["required_shape"]["args"]["appId"]=="source-attested app ID"
    src=read_contract_feedback("hub_read_apps_code",
        {"tool":"hub_get_source","args":{"type":"driver"}},
        typed,focus_ids=["7934"])
    assert src["verified_id_choices"]["driver"] == []
    assert src["verified_id_choices"]["app"] == ["4080"]
    assert src["host_execution_attempted"] is False


@pytest.mark.asyncio
async def test_first_scoped_event_read_returns_frontier_without_auto_repeat():
    mcp=FakeMCP([_read("hub_read_devices",["hub_list_device_events"])])
    async def identities():
        return [{"id":"7934","name":"Google Nest Hub",
                 "label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    events={"events":[
        {"name":"status","date":"2026-10-29T09:00:09.478+0000",
         "value":"idle",
         "producedBy":{"deviceId":"7934","name":"Google Nest Hub"}},
        {"name":"command-speak","date":"2026-10-29T09:00:01.109+0000",
         "producedBy":{"appId":"4080",
                       "name":"00 Google Calendar Notifier"}},
    ]}
    executor=FakeExecutor(mcp,[events])
    turns=0
    async def model(messages,tools):
        nonlocal turns
        turns+=1
        if turns==1:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_list_device_events",
                deviceId="7934")]}
        assert turns==2
        result=json.loads(messages[-1]["content"])
        frontier=result["event_read_frontier"]
        assert frontier["deviceId"]=="7934"
        assert frontier["source_returned_rows"]==2
        assert frontier["history_complete"] is False
        assert frontier["oldest_returned"] == "2026-10-29T09:00:01.109+0000"
        assert "narrower interval" in frontier["advice"]
        assert result["source_data"]["issuer_apps"][0]["appId"]=="4080"
        return {"content":'{"claims":[]}'}
    answer=await run_native_read_agent(
        question="Investigate Google Nest Hub (device 7934)",
        mcp=mcp,executor=executor,chat=model,max_rounds=2,max_reads=2)
    assert turns==2
    assert len(executor.calls)==1
    assert answer["native_diagnostics"]["focus_ids"]==["7934"]
    assert answer["native_diagnostics"]["failures"]==[]


@pytest.mark.asyncio
async def test_first_malformed_device_call_is_rejected_then_model_repairs_it():
    mcp=FakeMCP([_read("hub_read_devices",["hub_get_device"])])
    async def identities():
        return [{"id":"7934","name":"Google Nest Hub",
                 "label":"Google Nest Hub"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"id":"7934","name":"Google Nest Hub",
         "label":"Google Nest Hub","attributes":[
             {"name":"status","value":"idle"}]}])
    turns=0
    async def model(messages,tools):
        nonlocal turns
        turns+=1
        if turns==1:
            return {"tool_calls":[{"function":{
                "name":"homebrain_find_device",
                "arguments":{"name":"Google Nest Hub"}}}]}
        if turns==2:
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",mode="configuration")]}
        if turns==3:
            error=json.loads(messages[-1]["content"])
            assert error["error"]=="missing_required_operation_fields"
            contract=error["required_read_contract"]
            assert contract["required_shape"]["args"]["deviceId"]=="7934"
            return {"tool_calls":[_call(
                "hub_read_devices","hub_get_device",deviceId="7934")]}
        return {"content":'{"claims":[]}'}
    answer=await run_native_read_agent(
        question="Investigate Google Nest Hub (device 7934)",
        mcp=mcp,executor=executor,chat=model,max_rounds=4,max_reads=1)
    assert len(executor.calls)==1
    assert answer["native_diagnostics"]["focus_ids"]==["7934"]
    assert answer["native_diagnostics"]["invalid_contract_attempts"]=={
        "hub_get_device":1}
    assert turns==4
