from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"))
from investigation_v2.temporal_scope import explicit_incident_window
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.model_adapter import V2ModelProposer
from investigation_v2.evidence import CaseFile
from mcp_client import MCPTool, MCPToolResult


def scope():
    return explicit_incident_window("Why was light ON overnight on 24–25 October 2026?",
                                    zone_name="Europe/London")


def test_overnight_dst_scope_is_absolute_and_follows_the_requested_dates():
    window=scope()
    assert window.start_utc == "2026-10-24T17:00:00+00:00"
    assert window.end_utc == "2026-10-25T12:00:00+00:00"
    assert window.contains("2026-10-25T01:09:41+0100")
    assert window.contains("2026-10-25T01:09:41+0000")
    assert not window.contains("2026-10-26T07:25:37.546+0000")
    assert window.minimum_hours_back(now=datetime(2026,10,26,9,tzinfo=timezone.utc)) >= 40


def test_explicit_day_range_without_overnight_retains_all_requested_dates():
    w=explicit_incident_window("Analyse 24-25 October 2026",zone_name="Europe/London")
    assert w.start_utc == "2026-10-23T23:00:00+00:00"
    assert w.end_utc == "2026-10-26T00:00:00+00:00"
    assert explicit_incident_window("Why did it happen last night?",zone_name="Europe/London") is None
    assert explicit_incident_window("overnight 31–33 October 2026",zone_name="Europe/London") is None


def test_projection_retains_overnight_commands_but_not_current_day():
    r=MCPToolResult("hub_read_devices",{},raw={},text="",data={
      "events":[
        {"name":"command-off","type":"command","date":"2026-10-25T00:41:40+0100","deviceId": "7805","producedBy":{"id":"4246"}},
        {"name":"command-setLevel","type":"command","date":"2026-10-25T00:49:52+0100","deviceId":"7805","producedBy":{"id":"4019"}},
        {"name":"command-on","type":"command","date":"2026-10-26T07:25:37+0000","deviceId":"7805"},
      ]
    })
    receipt=project_read_receipt("hub_read_devices",{"tool":"hub_list_device_events","args":{"deviceId":"7805","hoursBack":72}},
                                r,source_request_id="test",incident_window=scope())
    assert receipt["success"]
    assert [e["name"] for e in receipt["details"]["events"]]==["command-off","command-setLevel"]
    assert receipt["details"]["rowsOutsideRequestedWindowOrInvalid"]==1
    assert receipt["details"]["sourceEventCount"]==3


def test_temporal_contract_rejects_recent_only_event_read():
    tool=MCPTool("hub_read_devices","read only",{
      "type":"object","properties":{
        "tool":{"type":"string","enum":["hub_list_device_events"]},
        "args":{"type":"object","properties":{"deviceId":{"type":"string"},
             "hoursBack":{"type":"integer"},"since":{"type":"string"}}}},
      "required":["tool","args"]}, annotations={"readOnlyHint":True})
    def read(arg):
        return {"tool":"hub_read_devices","arguments":{"tool":"hub_list_device_events","args":arg},
                "discriminator":"Test historical event","information_gain":"Checks earlier time"}
    case=CaseFile(original_user_request="Why?")
    p=review_model_read_proposals(case,[read({"deviceId":"7805","hoursBack":1})],[tool],
      verified_entity_ids=["7805"],incident_window=scope())
    assert not p.approved
    assert "read does not cover requested incident start" in p.rejected[0].reason
    good=review_model_read_proposals(case,[read({"deviceId":"7805","since":"2026-10-24T17:00:00Z"})],[tool],
      verified_entity_ids=["7805"],incident_window=scope())
    assert len(good.approved)==1
    missing=review_model_read_proposals(case,[read({"hoursBack":72})],[tool],
      verified_entity_ids=["7805"],incident_window=scope())
    assert not missing.approved


@pytest.mark.asyncio
async def test_planner_receives_authoritative_requested_scope():
    captured=[]
    async def chat(messages,tools):
        captured.append(messages)
        return {"content":json.dumps({"hypotheses":[],"reads":[],"finish":True})}
    m=V2ModelProposer(chat,[],verified_entity_ids=["7805"],incident_window=scope())
    await m(CaseFile("Why overnight 24–25 October 2026?"),0)
    prompt=json.loads(captured[0][1]["content"])
    assert prompt["requested_incident_window"]["start_utc"] == "2026-10-24T17:00:00+00:00"
    assert prompt["verified_target_ids"]==["7805"]

