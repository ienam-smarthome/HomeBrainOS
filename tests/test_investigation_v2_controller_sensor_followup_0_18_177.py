"""Phase 1 read-first controller sensor evidence contract (no live Hubitat).

An event-attested command issuer's ID-matched current config can scope a
bounded secondary sensor-history read. Current selections NEVER prove
historical effective rule settings, and log gaps NEVER prove a restart.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from existing_rule_settings_evidence import project_installed_app_settings
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.controller_dependencies import (
    controller_sensor_history_proposals, controller_log_coverage_proposals,
)
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.planning_evidence import planning_evidence
from investigation_v2.read_loop import run_read_only_investigation
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecution
from tool_registry import ToolEffect


def tool(name, operations, props, *, writable=False):
    return MCPTool(name, "Read-only gateway fixture", {
        "type":"object", "properties":{
            "tool":{"type":"string","enum":operations},
            "args":{"type":"object","properties":props,
                    "additionalProperties":False},
        }, "required":["tool","args"], "additionalProperties":False,
    }, annotations={"readOnlyHint":not writable,"mutates":writable})


def manifest(*, include_sensor=True, allow_logs=True, write_sensor=False):
    device_ops=["hub_get_device","hub_list_device_events"]
    p={"deviceId":{"type":"string"},
       "attribute":{"type":"string"},
       "hoursBack":{"type":"integer"},
       "limit":{"type":"integer"},
       "since":{"type":"string"},
       "until":{"type":"string"}}
    dev=tool("hub_read_devices",device_ops,p,writable=write_sensor)
    app=tool("hub_read_apps_code",["hub_get_app_config"],
             {"appId":{"type":"string"},"includeSettings":{"type":"boolean"}})
    logs=tool("hub_manage_logs",["hub_get_logs"],
              {"appId":{"type":"string"},"hoursBack":{"type":"integer"},
               "limit":{"type":"integer"}})
    return [dev, app]+([logs] if allow_logs else [])


def command_fixture():
    return {"tool":"hub_read_devices","sub_tool":"hub_list_device_events",
        "source_request_id":"typed-verified-command",
        "success":True,"mutates":False,"effect":"read",
        "arguments":{"tool":"hub_list_device_events",
                     "args":{"deviceId":"7828","hoursBack":48}},
        "details":{"deviceId":"7828","events":[{
            "deviceId":"7828","name":"command-off","type":"command",
            "date":"2026-10-28T00:14:56.868+00:00",
            "producedBy":{"id":"4020"},
        },{
            "deviceId":"7828","name":"switch","value":"off",
            "date":"2026-10-28T00:14:57.111+00:00",
            "producedBy":{"id":"7790"},
        }]}}


def raw_settings(*, app_id="4020", malicious=False):
    return {"app":{"id":app_id},"settings":{
        "motionSensors":{"7300":"FP400 motion"},
        "keepOnSensors":{"7301":"Kitchen","7302":"LWR01"},
        "inactiveAction":"off","inactiveOffSeconds":30,
        "unrelatedSensorNumbers":"9999",
        "apiSecret":"DONT_EXPOSE",
        **({"motionSensors":{"malicious":"9999","7300":"FP400"}} if malicious else {}),
    }}


def settings_receipt(*, app_id="4020"):
    args={"tool":"hub_get_app_config",
          "args":{"appId":"4020","includeSettings":True}}
    result=MCPToolResult("hub_read_apps_code",args,raw={},text="secret",
                         data=raw_settings(app_id=app_id))
    return project_read_receipt("hub_read_apps_code",args,result,
                                source_request_id="verified-config",
                                read_at="2026-10-28T10:45:00+00:00")


def test_typed_projection_only_extracts_explicit_sensor_selection_ids():
    p=project_installed_app_settings(raw_settings(),"4020")
    assert p["settingsReadable"] is True
    assert p["deviceReferences"] == [
        {"key":"motionSensors","deviceIds":["7300"]},
        {"key":"keepOnSensors","deviceIds":["7301","7302"]},
    ]
    serialized=json.dumps(p)
    assert "DONT_EXPOSE" not in serialized
    assert "9999" not in serialized
    assert project_installed_app_settings(raw_settings(app_id="9999"),"4020")[
        "settingsReadable"] is False


def test_case_only_whitelists_current_sensor_references_for_attested_issuer():
    case=build_case_file("Why off?",[command_fixture(),settings_receipt()])
    assert set(case.app_sensor_references)=={"4020"}
    assert case.app_sensor_references["4020"][0]["source_request_id"]=="verified-config"
    assert case.app_sensor_references["4020"][0]["source_basis"]==(
        "read_time_stored_controller_config")
    assert "DONT_EXPOSE" not in json.dumps(case.to_dict())
    wrong=build_case_file("Why off?",[command_fixture(),settings_receipt(app_id="9999")])
    assert wrong.app_sensor_references=={}
    no_actor=build_case_file("Why off?",[settings_receipt()])
    assert no_actor.app_sensor_references=={}


def test_host_scope_accepts_only_selected_sensor_ids():
    case=build_case_file("Why off?",[command_fixture(),settings_receipt()])
    reads=controller_sensor_history_proposals(manifest(),case,limit=3)
    assert [x["arguments"]["args"]["deviceId"] for x in reads]==[
        "7300","7301","7302"]
    approved=review_model_read_proposals(
        case,reads,manifest(),verified_entity_ids=("7828",),
        max_total_reads=8,max_reads_this_round=3,budget_used_reads=0)
    assert len(approved.approved)==3 and not approved.rejected
    bad=dict(reads[0])
    bad["arguments"]={"tool":"hub_list_device_events",
                      "args":{"deviceId":"9999","hoursBack":24,"limit":50}}
    result=review_model_read_proposals(
        case,[bad],manifest(),verified_entity_ids=("7828",),
        max_total_reads=8,budget_used_reads=0)
    assert not result.approved
    assert result.rejected[0].reason=="target ID has no independent verified scope"
    assert not controller_sensor_history_proposals(
        manifest(write_sensor=True),case)


def test_log_read_proposal_is_source_scoped_and_never_grants_mutations():
    case=build_case_file("Why off?",[command_fixture(),settings_receipt()])
    p=controller_log_coverage_proposals(manifest(),case)
    assert len(p)==1
    assert p[0]["arguments"]["tool"]=="hub_get_logs"
    assert p[0]["arguments"]["args"]["appId"]=="4020"
    assert not controller_log_coverage_proposals(manifest(allow_logs=False),case)
    assert not controller_log_coverage_proposals([tool(
        "hub_manage_logs",["hub_get_logs"],{"appId":{"type":"string"}},
        writable=True)],case)


def test_source_planning_labels_current_sensor_selection_not_historic_trigger():
    case=build_case_file("Why off?",[command_fixture(),settings_receipt()])
    view=json.loads(planning_evidence(case,None))
    ref=view["current_controller_sensor_selections"][0]
    assert ref["sensor_ids"]==["7300"]
    assert ref["historical_selection_verified"] is False
    assert any("not prove event-time" in x for x in view["constraints"])


class FakeMCP:
    async def list_tools(self):
        return manifest()


class FakeExecutor:
    def __init__(self,mcp):
        self.mcp=mcp
        self.calls=[]

    async def execute(self,name,arguments,**kwargs):
        assert kwargs["record_evidence"] is False
        op=arguments["tool"];args=arguments["args"]
        self.calls.append((name,op,dict(args)))
        if op=="hub_get_device":
            data={"device":{"id":"7828","attributes":{"switch":"off"}}}
        elif op=="hub_list_device_events":
            identity=args["deviceId"]
            if identity=="7828":
                data={"deviceId":identity,"events":[
                    {"deviceId":identity,"name":"switch","value":"off",
                     "date":"2026-10-28T00:14:57.111+00:00",
                     "producedBy":{"id":"7790"}}] if args.get("attribute")=="switch" else
                    command_fixture()["details"]["events"]}
            elif identity=="7300":
                data={"deviceId":identity,"events":[{
                    "deviceId":identity,"name":"motion","value":"inactive",
                    "date":"2026-10-28T00:14:00.481+00:00"}]}
            elif identity=="7301":
                data={"deviceId":identity,"events":[]}
            else:
                raise AssertionError("unknown sensor source")
        elif op=="hub_get_app_config":
            assert args["appId"]=="4020"
            data=raw_settings()
        elif op=="hub_get_logs":
            assert args["appId"]=="4020"
            data={"logs":[{"date":"2026-10-28T07:23:00+00:00",
                           "message":"UNTRUSTED PRIVATE PASSWORD"},
                          {"date":"2026-10-28T07:24:00+00:00"}]}
        else:
            raise AssertionError(op)
        return ToolExecution(name=name,arguments=arguments,effect=ToolEffect.READ,
            success=True,elapsed_ms=5,content="",
            result=MCPToolResult(name,arguments,raw={},text="UNTRUSTED",data=data))


@pytest.mark.asyncio
async def test_full_read_first_incident_reaches_sensor_and_log_before_model():
    mcp=FakeMCP()
    exe=FakeExecutor(mcp)
    rounds=[]
    async def done(case,index):
        rounds.append(index)
        assert any(r.target_id=="7300" and r.action=="motion"
                   and r.value=="inactive" for r in case.records)
        return {"reads":[],"hypotheses":[],"finish":True}
    result=await run_read_only_investigation(
        question="Investigate why the named device switched off.",
        mcp=mcp,executor=exe,propose=done,
        verified_entity_ids=("7828",),
        bootstrap_device_context=True,bootstrap_source_identity=True,
        max_rounds=1,max_total_reads=9)
    operations=[call[1] for call in exe.calls]
    assert operations==[
        "hub_get_device","hub_list_device_events","hub_list_device_events",
        "hub_get_app_config","hub_list_device_events","hub_list_device_events",
        "hub_get_logs"]
    assert [c[2]["deviceId"] for c in exe.calls if c[1]=="hub_list_device_events"][-2:]==[
        "7300","7301"]
    assert result.executed_reads==7
    assert rounds==[0]
    assert any(r.target_id=="7300" and r.action=="motion"
               and r.value=="inactive" for r in result.case.records)
    assert "4020" in result.case.app_sensor_references
    logs=[d for d in result.bootstrap_diagnostics if d.get("stage")=="controller_logs"]
    assert logs and logs[-1]["restart_verified"] is False
    assert logs[-1]["oldest_available_utc"]=="2026-10-28T07:23:00+00:00"
    out=json.dumps(result.to_dict())
    assert "UNTRUSTED" not in out and "PASSWORD" not in out
    assert result.to_dict()["root_cause_verified"] is False
