"""V2 source-grounded compact planning: no mutating operations advertised."""
from __future__ import annotations
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPTool
from investigation_v2.evidence import CaseFile, Coverage, EvidenceItem
from investigation_v2.model_adapter import _advertised_reads, V2ModelProposer
from investigation_v2.planning_evidence import planning_evidence
from investigation_v2.investigation_report import format_investigation_report

def event(i, action, stage="state_reported", value=None, target="7103", issuer="7103", seconds=None):
    t=datetime(2026,10,12,tzinfo=timezone.utc)+timedelta(seconds=i*60 if seconds is None else seconds)
    return EvidenceItem(record_id=f"rec{i}",source_request_id="source",
        tool="hub_read_devices",operation="hub_list_device_events",
        source_category="device_events",target_id=target,producer_id=issuer,
        producer_label=None,timestamp_utc=t.isoformat(),timestamp_original=t.isoformat(),
        stage=stage,action=action,value=value,raw_references=(f"source.details.events[{i}]",))

def manifest():
    return MCPTool("hub_read_devices","Read only",{"type":"object",
        "properties":{"tool":{"type":"string","enum":["hub_list_device_events",
            "hub_call_device_command","hub_get_device"]},
            "args":{"type":"object","properties":{"deviceId":{"type":"string"},
                "limit":{"type":"integer"},"command":{"type":"string"}},
                "required":["deviceId"],"additionalProperties":False}},
        "required":["tool","args"],"additionalProperties":False},
        annotations={"readOnlyHint":True,"mutates":False})

def test_planner_manifest_does_not_leak_unsafe_operation_via_tool_enum():
    schemas=_advertised_reads([manifest()])
    assert len(schemas)==1
    assert schemas[0]["operations"]==["hub_list_device_events","hub_get_device"]
    assert schemas[0]["properties"]["tool"]["enum"]==schemas[0]["operations"]
    assert "hub_call_device_command" not in json.dumps(schemas)

def test_dense_polling_near_failure_is_not_repeated_to_model():
    rows=[event(i,"voltage",value=str(240+i%3),seconds=i*90) for i in range(36)]
    rows.extend([event(41,"command-off","command_issued",target="7103",issuer="3950",seconds=1800),
                 event(42,"switch",value="off",seconds=1801),
                 event(43,"healthStatus",value="offline",seconds=2030),
                 event(44,"stored-setting:onOffSwitch.3","config_stored",
                       value="device IDs: 7103",target="3950",issuer=None,seconds=18000)])
    case=CaseFile("Why did the plug become offline?",records=rows)
    before=case.to_dict()
    projected=json.loads(planning_evidence(case,None))
    ids={r["id"] for r in projected["records"]}
    assert {"rec41","rec42","rec43","rec44"}<=ids
    assert len(projected["records"])<=12
    assert sum(x["rows"] for x in projected["coalesced_context"])>=25
    assert case.to_dict()==before

@pytest.mark.asyncio
async def test_model_receives_compact_read_only_contract_and_all_material_ids():
    rows=[event(i,"voltage",value="245",seconds=i*90) for i in range(36)]
    rows.extend([event(41,"command-off","command_issued",issuer="3950",seconds=1800),
                 event(42,"switch",value="off",seconds=1801),
                 event(43,"healthStatus",value="offline",seconds=2030)])
    case=CaseFile("Investigate",records=rows)
    seen=[]
    async def chat(messages, tools):
        seen.extend(messages)
        assert tools==[]
        return {"content":'{"hypotheses":[],"reads":[],"finish":true}'}
    proposer=V2ModelProposer(chat,[manifest()],verified_entity_ids=["7103"])
    result=await proposer(case,0)
    assert result["finish"] is True
    prompt=json.loads(seen[1]["content"])
    assert prompt["required_result"]=={"hypotheses":[],"reads":[],"finish":True}
    inner=json.loads(prompt["case_file"])
    ids={r["id"] for r in inner["records"]}
    assert {"rec41","rec42","rec43"}<=ids
    assert proposer.last_prompt_chars<6500
    assert "hub_call_device_command" not in seen[1]["content"]

def test_report_never_invents_a_second_off_and_explains_unresolved_catalogue():
    case=CaseFile("Why offline?",records=[
       event(41,"command-off","command_issued",issuer="3950",seconds=1800),
       event(42,"switch",value="off",seconds=1801),
       event(43,"healthStatus",value="offline",seconds=2030),
       event(44,"stored-setting:onOffSwitch.3","config_stored",
             value="device IDs: 7103",target="3950",issuer=None,seconds=18000),
    ])
    case.coverage.append(Coverage(source_request_id="catalog",tool="hub_read_apps_code",
        operation="hub_list_apps",query_target_id=None,requested_filters={},
        returned_rows=0,oldest_utc=None,newest_utc=None,page_reaches_start=None,
        source_complete=None,truncated=None,source_integrity_verified=None,
        pagination_cursor=None,succeeded=True))
    report=format_investigation_report(case,[],"planning_timeout")
    assert report.count("issued OFF at")==1
    assert "Another OFF was issued" not in report
    assert "source #3950 did not match a name" in report
    assert "Controller app #3950" in report
    assert "physical failure mechanism" in report
