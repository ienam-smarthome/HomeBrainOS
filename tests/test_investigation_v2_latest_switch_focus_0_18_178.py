"""Regression for Oct 28 v0.18.177: latest OFF issuer is not the
oldest/most frequent unrelated app or issuer of an earlier network outage.

No model, hub access, writes, or inferred configuration; all source IDs are
part of a synthetic transcript shaped like the recorded V2 live report.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool
from investigation_v2.evidence import build_case_file
from investigation_v2.causal_evidence import (
    command_state_pairs, focused_switch_command,
)
from investigation_v2.source_identity import source_configuration_proposals
from investigation_v2.controller_dependencies import controller_log_coverage_proposals
from investigation_v2.planning_evidence import planning_evidence
from investigation_v2.model_adapter import V2ModelProposer


def gateway(name, operations, props=None):
    return MCPTool(name, "READ ONLY", {
        "type":"object",
        "properties":{
            "tool":{"type":"string","enum":operations},
            "args":{"type":"object","properties":props or {},
                    "additionalProperties":True},
        },
        "required":["tool","args"],
        "additionalProperties":False,
    },annotations={"readOnlyHint":True,"mutates":False})


def manifest():
    return [
        gateway("hub_read_apps_code",["hub_list_apps","hub_get_app_config"]),
        gateway("hub_read_diagnostics",["hub_get_logs"]),
        gateway("hub_read_devices",["hub_list_device_events"]),
    ]


def receipt(events, request_id="historic-transcript", target="7828"):
    return {
        "tool":"hub_read_devices",
        "sub_tool":"hub_list_device_events",
        "source_request_id":request_id,
        "success":True,"mutates":False,"effect":"read",
        "arguments":{"tool":"hub_list_device_events",
                     "args":{"deviceId":target,"hoursBack":168,"limit":150}},
        "details":{"deviceId":target,"events":events,
                   "sourceComplete":False},
    }


def events():
    old=datetime(2026,10,23,18,0,tzinfo=timezone.utc)
    rows=[]
    # An unrelated app generated a command followed by network-offline,
    # which the earlier adverse-network rank incorrectly prioritised.
    rows.extend([
        {"name":"command-on","type":"command",
         "date":"2026-10-23T18:37:18.015+00:00",
         "producedBy":{"id":"4129"}},
        {"name":"networkStatus","value":"offline",
         "date":"2026-10-23T18:45:18.704+00:00",
         "producedBy":{"id":"7790"}},
    ])
    for i in range(58):
        timestamp=(old+timedelta(hours=1,minutes=8*i)).isoformat()
        # Many unrelated historical commands inflate the model prompt,
        # but must not affect the latest-source command selection.
        rows.append({"name":"command-on" if i%2==0 else "command-setLevel",
                     "type":"command","date":timestamp,
                     "producedBy":{"id":"1252" if i%3 else "4129"}})
    rows.extend([
        {"name":"command-off","type":"command",
         "date":"2026-10-28T00:14:56.868+00:00",
         "producedBy":{"id":"4020"}},
        {"name":"switch","value":"off",
         "date":"2026-10-28T00:14:57.111+00:00",
         "producedBy":{"id":"7790"}},
        {"name":"networkStatus","value":"online",
         "date":"2026-10-28T07:18:53.552+00:00",
         "producedBy":{"id":"7790"}},
    ])
    return rows


def current_case():
    return build_case_file(
        "Investigate why the device turned OFF most recently.",
        [receipt(events())])


def test_latest_attested_off_outweighs_unrelated_network_event_issuer():
    case=current_case()
    focus,reason=focused_switch_command(case,verified_target_ids=("7828",))
    assert reason=="paired_latest_switch_transition"
    assert focus is not None and focus.producer_id=="4020"
    assert focus.action=="command-off"
    assert focus.timestamp_utc=="2026-10-28T00:14:56.868000+00:00"
    pairs=[x for x in command_state_pairs(case) if x.issuer_app_id=="4020"]
    assert len(pairs)==1 and pairs[0].interval_ms==243
    app=source_configuration_proposals(
        manifest(),case,verified_target_ids=("7828",))
    assert len(app)==1 and app[0]["arguments"]["args"]["appId"]=="4020"
    logs=controller_log_coverage_proposals(
        manifest(),case,verified_target_ids=("7828",))
    assert len(logs)==1 and logs[0]["arguments"]["args"]["appId"]=="4020"


def test_wrong_target_or_unpaired_last_state_must_not_select_old_issuer():
    case=current_case()
    assert source_configuration_proposals(
        manifest(),case,verified_target_ids=("9999",))==[]
    assert controller_log_coverage_proposals(
        manifest(),case,verified_target_ids=("9999",))==[]
    add={"name":"switch","value":"on",
         "date":"2026-10-28T00:15:05+00:00",
         "producedBy":{"id":"7790"}}
    unmatched=build_case_file(
        "Most recent change", [receipt(events()+[add])])
    focused,basis=focused_switch_command(unmatched,verified_target_ids=("7828",))
    assert focused is None and basis=="latest_switch_transition_unpaired"
    assert source_configuration_proposals(
        manifest(),unmatched,verified_target_ids=("7828",))==[]
    assert controller_log_coverage_proposals(
        manifest(),unmatched,verified_target_ids=("7828",))==[]


def test_model_planning_view_shrinks_history_but_keeps_decisive_pair():
    case=current_case()
    original_ids={r.record_id for r in case.records}
    full=json.loads(planning_evidence(case,None))
    focused=json.loads(planning_evidence(case,None,focus_latest=True))
    assert len(full["records"])==len(case.records)
    assert focused["planning_view"]=="latest_attested_switch_incident"
    assert focused["full_case_retained_for_audit"] is True
    assert len(focused["records"])<len(full["records"])
    assert len(json.dumps(focused)) < len(json.dumps(full))*0.80
    assert focused["total_case_records"]==len(case.records)
    assert set(original_ids)=={r.record_id for r in case.records}
    assert any(p["issuer_app_id"]=="4020" and p["interval_ms"]==243
               for p in focused["command_state_pairs"])
    assert any(r["issuer_id"]=="4020" and r["action"]=="command-off"
               for r in focused["records"])


@pytest.mark.asyncio
async def test_planner_uses_compact_view_with_correct_app_and_no_changes():
    case=current_case()
    observed=[]
    async def fake_chat(messages, tools):
        assert tools==[]
        request=json.loads(messages[1]["content"])
        view=json.loads(request["case_file"])
        observed.append(view)
        return {"content":json.dumps({"hypotheses":[],"reads":[],"finish":True})}
    planner=V2ModelProposer(fake_chat,manifest(),
                           verified_entity_ids=("7828",))
    result=await planner(case,0)
    assert result["finish"] is True
    assert observed[0]["planning_view"]=="latest_attested_switch_incident"
    assert any(p["issuer_app_id"]=="4020"
               for p in observed[0]["command_state_pairs"])
    assert planner.last_prompt_chars < 18000


def test_latest_command_fallback_only_when_no_switch_reports_exist():
    case=build_case_file("Inspect command",[
        receipt([{"name":"command-off","type":"command",
                  "date":"2026-10-28T00:14:56.868+00:00",
                  "producedBy":{"id":"4020"}}])
    ])
    selected,basis=focused_switch_command(case,verified_target_ids=("7828",))
    assert basis=="latest_command_without_switch_report"
    assert selected is not None and selected.producer_id=="4020"
