"""v0.18.157 — event-attested app settings through generic MCP read args.

Never infer historical execution from current config. All input manifests
and tool responses are synthetic; no physical Hubitat or writes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from mcp_client import MCPTool, MCPToolResult
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.planning import review_model_read_proposals
from investigation_v2.source_identity import source_configuration_proposals


def evidence():
    args={"tool":"hub_list_device_events","args":{"deviceId":"7103"}}
    result=MCPToolResult("hub_read_devices",args,raw={},text="",
        data={"deviceId":"7103","events":[{
            "name":"command-on","type":"command","deviceId":"7103",
            "date":"2026-10-24T20:51:12+00:00",
            "producedBy":{"id":"3103"}}]},is_error=False)
    row=project_read_receipt("hub_read_devices",args,result,source_request_id="real-attested-issuer")
    case=build_case_file("Why is Bedroom 3 Mesh offline?",[row])
    case.app_identities["3103"]="Ikea Rodret Dimmer: button 2"
    return case


def manifest(args_schema, *, read_only=True, operation="hub_get_app_config"):
    return MCPTool("hub_read_apps_code","Read installed apps",{
        "type":"object",
        "properties":{
            "tool":{"type":"string","enum":[operation]},
            "args":args_schema,
        },
        "required":["tool","args"],
        "additionalProperties":False,
    },annotations={"readOnlyHint":read_only,"mutates":not read_only})


@pytest.mark.parametrize("schema,basis",[
    ({"type":"object"}, "open_args_schema"),
    ({"type":"object","properties":{}}, "open_args_schema"),
    ({"type":"object","properties":{},"additionalProperties":True}, "open_args_schema"),
    ({"type":"object","properties":{"appId":{"type":"string"}},
      "required":["appId"],"additionalProperties":False}, "declared_app_id"),
])
def test_generic_schema_allows_exact_proven_issuer_under_host_gate(schema,basis):
    case=evidence()
    tool=manifest(schema)
    diagnostics=[]
    proposals=source_configuration_proposals([tool],case,diagnostics=diagnostics)
    assert len(proposals)==1
    expected_args={"appId":"3103"}
    if basis=="open_args_schema":
        expected_args["includeSettings"]=True
    assert proposals[0]["arguments"]=={"tool":"hub_get_app_config","args":expected_args}
    assert diagnostics == [{"stage":"controller_config","status":"verified_issuer_proposal",
                            "issuer_id":"3103","argument_basis":basis,
                            "settings_requested":"true" if basis=="open_args_schema" else "false"}]
    reviewed=review_model_read_proposals(
        case,proposals,[tool],verified_entity_ids=["7103"],
        max_total_reads=8,max_reads_this_round=1)
    assert len(reviewed.approved)==1
    assert reviewed.rejected == []


@pytest.mark.parametrize("schema,reason",[
    ({"type":"object","properties":{},"additionalProperties":False},
     "app_id_missing_from_live_schema"),
    ({"type":"string"}, "unsupported_args_schema"),
    ({"type":"object","required":["appId","token"]},
     "unsupported_required_args"),
    ({"type":"object","properties":{},
      "additionalProperties":{"type":"integer"}}, "open_args_value_rejected"),
])
def test_closed_or_incompatible_generic_args_fail_closed(schema,reason):
    diagnostics=[]
    assert source_configuration_proposals(
        [manifest(schema)],evidence(),diagnostics=diagnostics)==[]
    assert diagnostics[-1]["reason"]==reason


def test_event_attested_issuer_scope_never_authorises_unrelated_app():
    case=evidence()
    tool=manifest({"type":"object"})
    proposed=source_configuration_proposals([tool],case)
    assert proposed
    proposed[0]["arguments"]["args"]["appId"]="9999"
    outcome=review_model_read_proposals(case,proposed,[tool],
        verified_entity_ids=["7103"],max_total_reads=8)
    assert outcome.approved==[]
    assert any("verified scope" in x.reason for x in outcome.rejected)


def test_open_args_do_not_authorise_write_gateways_or_unadvertised_operations():
    case=evidence()
    assert source_configuration_proposals(
        [manifest({"type":"object"},read_only=False)],case)==[]
    assert source_configuration_proposals(
        [manifest({"type":"object"},operation="hub_list_apps")],case)==[]
    bare=build_case_file("Why offline?",[])
    assert source_configuration_proposals([manifest({"type":"object"})],bare)==[]


def test_v2_endpoint_exposes_identity_page_timings():
    s=(ROOT/"app.py").read_text()
    route=s.split("async def v2_test(",1)[1].split('@app.post("/api/chat")',1)[0]
    assert '"inventory_page_diagnostics": inventory_page_diagnostics' in route
    assert '"page_timings_ms"' in route
    assert '"first_page_ms"' in route
    assert '"slowest_page_ms"' in route
    assert '"identity_only"' in route


def test_incident_adverse_transition_prioritises_off_issuer_over_later_on():
    """The first relevant read must follow the incident, not numeric ID."""
    args={"tool":"hub_list_device_events","args":{"deviceId":"7103"}}
    events=[
        {"deviceId":"7103","name":"command-off","type":"command",
         "date":"2026-10-12T00:30:01+00:00","producedBy":{"id":"3950"}},
        {"deviceId":"7103","name":"switch","value":"off",
         "date":"2026-10-12T00:30:02+00:00","producedBy":{"id":"7103"}},
        {"deviceId":"7103","name":"healthStatus","value":"offline",
         "date":"2026-10-12T00:33:46+00:00","producedBy":{"id":"7103"}},
        {"deviceId":"7103","name":"command-on","type":"command",
         "date":"2026-10-24T20:51:12+00:00","producedBy":{"id":"3103"}},
    ]
    result=MCPToolResult("hub_read_devices",args,raw={},text="",
        data={"deviceId":"7103","events":events},is_error=False)
    receipt=project_read_receipt("hub_read_devices",args,result,
        source_request_id="incident")
    case=build_case_file("Why offline?",[receipt])
    proposed=source_configuration_proposals([manifest({"type":"object"})],case)
    assert proposed[0]["arguments"]["args"]["appId"]=="3950"
    approved=review_model_read_proposals(case,proposed,
        [manifest({"type":"object"})],verified_entity_ids=["7103"],
        max_total_reads=8)
    assert len(approved.approved)==1


def test_unrelated_device_failure_does_not_bias_issuer_ranking():
    case=evidence()
    from investigation_v2.evidence import EvidenceItem
    case.records.append(EvidenceItem(
        "other","observed","hub_read_devices","hub_list_device_events",
        "device_events","9999","9999",None,
        "2026-10-24T20:51:13+00:00","2026-10-24T20:51:13+00:00",
        "state_reported","healthStatus","offline",("other",)))
    proposed=source_configuration_proposals([manifest({"type":"object"})],case)
    assert proposed[0]["arguments"]["args"]["appId"]=="3103"


def test_off_state_and_offline_sequence_survives_planner_timeout_report():
    from investigation_v2.investigation_report import format_investigation_report
    args={"tool":"hub_list_device_events","args":{"deviceId":"7103"}}
    events=[
        {"deviceId":"7103","name":"command-off","type":"command",
         "date":"2026-10-12T00:30:01+00:00","producedBy":{"id":"3950"}},
        {"deviceId":"7103","name":"switch","value":"off",
         "date":"2026-10-12T00:30:02+00:00","producedBy":{"id":"7103"}},
        {"deviceId":"7103","name":"healthStatus","value":"offline",
         "date":"2026-10-12T00:33:46+00:00","producedBy":{"id":"7103"}},
    ]
    raw=MCPToolResult("hub_read_devices",args,raw={},text="",
        data={"deviceId":"7103","events":events},is_error=False)
    case=build_case_file("Investigate offline",[project_read_receipt(
        "hub_read_devices",args,raw,source_request_id="historical")])
    report=format_investigation_report(case,[],"planning_timeout")
    assert "**Incident-linked sequence:**" in report
    assert "switch=off state was reported" in report
    assert "healthStatus=offline was reported" in report
    assert "not independently prove" in report
    assert "Without a subsequent independently reported switch state" not in report
