"""0.18.158: investigate earlier reported lastSeen, not latest watchdog noise.

Synthetic manifests and receipts only; no actual Hubitat actions.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from mcp_client import MCPTool, MCPToolResult
from investigation_v2.evidence import CaseFile, build_case_file
from investigation_v2.last_contact_anchor import last_contact_anchor_proposals
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.source_identity import source_configuration_proposals


NOW=datetime(2026,10,27,12,0,tzinfo=timezone.utc)
LAST_SEEN="Mon Oct 12 01:30:01 BST 2026"


def _tool(*, includes_window=True, limit_max=500, readonly=True):
    props={"deviceId":{"type":"string"},
           "hoursBack":{"type":"integer","maximum":744},
           "limit":{"type":"integer","maximum":limit_max}}
    if includes_window:
        props.update({"since":{"type":"string"},"until":{"type":"string"}})
    return MCPTool("hub_read_devices","Source event history",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_list_device_events"]},
            "args":{"type":"object","properties":props,
                    "required":["deviceId"],"additionalProperties":False},
        },"required":["tool","args"],"additionalProperties":False,
    },annotations={"readOnlyHint":readonly,"mutates":not readonly})


def _case(last_seen=LAST_SEEN, events=None):
    history_args={"tool":"hub_list_device_events",
                  "args":{"deviceId":"7103","limit":50,"hoursBack":395}}
    raw=events if events is not None else [{
        "deviceId":"7103","name":"mqttStatus","value":"connected",
        "date":"2026-10-22T21:10:25+00:00",
        "producedBy":{"id":"7103"}}]
    receipt=project_read_receipt("hub_read_devices",history_args,
        MCPToolResult("hub_read_devices",history_args,raw={},text="",
                      data={"deviceId":"7103","events":raw}),
        source_request_id="verified-recent-events")
    case=build_case_file("Why did it go offline?",[receipt])
    case.device_snapshots.append({"deviceId":"7103","attributes":{
        "lastSeen":last_seen,"healthStatus":"offline","mqttStatus":"connected"}})
    return case


def test_recovery_search_uses_historical_last_seen_not_recent_watchdog_events():
    case=_case()
    proposal,reason=last_contact_anchor_proposals([_tool()],["7103"],case,now=NOW)
    assert reason=="requested_bounded_last_seen_window"
    assert len(proposal)==1
    args=proposal[0]["arguments"]["args"]
    assert args["deviceId"]=="7103"
    assert args["limit"]==200
    assert args["since"].startswith("2026-10-11T22:30:01+00:00")
    assert args["until"].startswith("2026-10-12T02:30:01+00:00")
    assert args["hoursBack"]>350
    assert "attribute" not in args
    reviewed=review_model_read_proposals(
        case,proposal,[_tool()],verified_entity_ids=["7103"],max_total_reads=8)
    assert len(reviewed.approved)==1
    assert reviewed.rejected==[]


def test_last_seen_anchor_is_not_assumed_proven_history():
    case=_case(events=[{
        "deviceId":"7103","name":"switch","value":"off",
        "date":"2026-10-12T00:30:01+00:00","producedBy":{"id":"7103"}}])
    p,reason=last_contact_anchor_proposals([_tool()],["7103"],case,now=NOW)
    assert p==[]
    assert reason=="reported_contact_window_already_observed"
    # Even an observed state report does not prove physical AP topology.
    assert case.coverage[0].source_complete is not True


@pytest.mark.parametrize("last_seen,reason",[
    ("garbled","reported_last_seen_unavailable"),
    ("Mon Oct 12 01:30:01 GMT 2026","reported_last_seen_unavailable"),
    ("2026-10-27T11:00:00+00:00","no_old_last_seen_anchor"),
    ("2026-07-01T11:00:00+00:00","no_old_last_seen_anchor"),
])
def test_untrusted_or_unsupported_last_seen_does_not_widen_scope(last_seen,reason):
    proposals,outcome=last_contact_anchor_proposals(
        [_tool()],["7103"],_case(last_seen=last_seen),now=NOW)
    assert proposals==[] and outcome==reason


def test_closed_schema_uses_larger_bounded_history_without_inventing_until():
    proposals,reason=last_contact_anchor_proposals(
        [_tool(includes_window=False)],["7103"],_case(),now=NOW)
    assert reason=="requested_deeper_last_seen_history"
    args=proposals[0]["arguments"]["args"]
    assert "since" not in args and "until" not in args
    assert args["limit"]==200
    assert args["hoursBack"]>350


def test_too_small_closed_schema_does_not_repeat_same_history_page():
    p,reason=last_contact_anchor_proposals(
        [_tool(includes_window=False,limit_max=50)],["7103"],_case(),now=NOW)
    assert p==[] and reason=="no_larger_historical_page"


def test_wrong_identity_or_write_tool_cannot_authorise_historical_read():
    case=_case()
    assert last_contact_anchor_proposals(
        [_tool()],["9999"],case,now=NOW)[0]==[]
    assert last_contact_anchor_proposals(
        [_tool(readonly=False)],["7103"],case,now=NOW)[0]==[]


def _app_tool(extra):
    return MCPTool("hub_read_apps_code","Read app",{
        "type":"object","properties":{
            "tool":{"type":"string","enum":["hub_get_app_config"]},
            "args":{"type":"object","properties":{
                "appId":{"type":"string"},**extra},
                "required":["appId"],"additionalProperties":False},
        },"required":["tool","args"],"additionalProperties":False,
    },annotations={"readOnlyHint":True,"mutates":False})


def _command_case():
    args={"tool":"hub_list_device_events","args":{"deviceId":"7103"}}
    raw={"deviceId":"7103","events":[{
        "deviceId":"7103","name":"command-on","type":"command",
        "date":"2026-10-24T20:51:12+00:00",
        "producedBy":{"id":"3103"}}]}
    receipt=project_read_receipt("hub_read_devices",args,
        MCPToolResult("hub_read_devices",args,raw={},text="",data=raw),
        source_request_id="confirmed-issuer")
    case=build_case_file("Investigate offline",[receipt])
    case.app_identities["3103"]="Ikea Rodret Dimmer: button 2 pushed"
    return case


def test_app_config_only_asks_for_settings_when_live_schema_accepts_it():
    case=_command_case()
    with_settings=source_configuration_proposals([_app_tool({
        "includeSettings":{"type":"boolean"}})],case)
    assert with_settings[0]["arguments"]["args"]=={
        "appId":"3103","includeSettings":True}
    without_settings=source_configuration_proposals([_app_tool({})],case)
    assert without_settings[0]["arguments"]["args"]=={"appId":"3103"}
    # Explicitly permitted settings are current stored fields, not proof
    # that they were effective at the time of a historical ON command.
    args=with_settings[0]["arguments"]
    projection=project_read_receipt("hub_read_apps_code",args,
        MCPToolResult("hub_read_apps_code",args,raw={},text="",data={
            "success":True,"app":{"id":"3103"},
            "settings":{"onOff.1":True}}),source_request_id="config")
    assert projection["details"]["settingsReadable"] is True
    assert projection["details"]["indexedFields"]
    assert projection["evidence_kind"]=="typed_existing_rule_partial_settings"


def test_empty_projection_does_not_become_verified_controller_settings():
    args={"tool":"hub_get_app_config","args":{
        "appId":"3103","includeSettings":True}}
    projection=project_read_receipt("hub_read_apps_code",args,
        MCPToolResult("hub_read_apps_code",args,raw={},text="",data={
            "success":True,"app":{"id":"3103"},
            "settings":{"arbitrarySecret":"sensitive"}}),source_request_id="empty")
    assert projection["details"]["settingsReadable"] is True
    assert projection["details"]["indexedFields"]==[]
    assert projection["details"]["controllerFields"]==[]

