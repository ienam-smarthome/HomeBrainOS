"""Regression: independently attested controller decision follow-up, not a device-specific route."""
import json
import sys
from pathlib import Path
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from mcp_client import MCPToolResult
from investigation_v2.native_controller_decision import controller_decision_followup,scoped_app_execution_lines
from investigation_v2.native_incident_relevance import dated_incident_evidence
from investigation_v2.native_reasoned_assessment import verify_natural_hypothesis
from investigation_v2.native_read_agent import _payload,run_native_read_agent
from investigation_v2.native_evidence_focus import focused_model_view
from test_investigation_v2_event_reasoning_0_18_232 import QUESTION,thermostat_events
from test_investigation_v2_incident_relevance_0_18_229 import history,READ_EVENTS
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP,FakeExecutor,READ_DIAG

def raw_logs():
    return {"entries":[
        {"date":"2026-10-29 14:54:18.073","level":"info","type":"app",
         "name":"00 Smart Thermostat Scheduler",
         "message":"app|3970|00 Smart Thermostat Scheduler|Demand OFF: Smart Rad TRV reports 22.0°C / 22.0°C, satisfied"},
        {"date":"2026-10-29 14:54:18.074","level":"info","type":"app",
         "name":"Other App",
         "message":"app|8888|Other App|an unrelated decision"},
    ],"total":2}

def receipts():
    return [history(1,thermostat_events(),device="4382")]

def test_source_attested_controller_inspection_recommended_without_execution():
    w=receipts()
    cov=dated_incident_evidence(QUESTION,w,["4382"])
    hint=controller_decision_followup(w,["4382"],cov,app_logs_offered=True)
    assert hint["observed_issuer_app_id"]=="3970"
    assert hint["proposed_read"]["operation"]=="hub_get_logs"
    assert "2026-10-29T14:42" in hint["proposed_read"]["args"]["since"]
    assert controller_decision_followup(w,["4382"],cov,app_logs_offered=False) is None
    assert controller_decision_followup(w,["4383"],cov,app_logs_offered=True) is None

def test_scoped_info_messages_preserved_other_apps_discarded():
    data=raw_logs()
    entries=scoped_app_execution_lines(data,"3970")
    assert len(entries)==1 and "satisfied" in entries[0]["message"]
    assert "Other App" not in json.dumps(entries)
    result=MCPToolResult("hub_read_diagnostics",{},{},"",data)
    packet=_payload(result,"hub_get_logs",read_filters={"appId":"3970"})
    assert packet["app_execution_lines"]==entries
    assert "satisfied" in json.dumps(focused_model_view("hub_get_logs",packet,["4382"]))
    assert "app_execution_lines" not in _payload(result,"hub_get_logs")

def test_source_event_and_info_log_are_separately_citable():
    w=receipts()
    projected=_payload(MCPToolResult("hub_read_diagnostics",{},{},"",raw_logs()),
                       "hub_get_logs",read_filters={"appId":"3970"})
    w.append({"read":2,"operation":"hub_get_logs",
              "read_filters":{"appId":"3970"},"source_data":projected})
    cov=dated_incident_evidence(QUESTION,w,["4382"])
    info=cov["controller_decision_log_examples"][0]
    assert info["name"]=="app_log"
    assert info["source_clock_verified"] is False
    assert "22.0°C" in info["value"]
    assert controller_decision_followup(w,["4382"],cov,app_logs_offered=True) is None
    state=next(e for e in cov["material_event_examples"]
               if e["name"]=="thermostatOperatingState" and e["value"]=="idle")
    model={"hypothesis":"The scheduler logged that radiator demand was satisfied at 22.0°C before heating stopped.",
           "confidence":"possible",
           "supporting_events":[{"read":state["read"],"name":state["name"],"date":state["date"]},
                                {"read":info["read"],"name":info["name"],"date":info["date"]}],
           "next_check":"Inspect radiator history at the reported time.",
           "alternative":"A different controller could also have influenced demand."}
    assert verify_natural_hypothesis(model,coverage=cov)["accepted"] is True
    model["hypothesis"]=model["hypothesis"].replace("22.0°C","9999°C")
    assert verify_natural_hypothesis(model,coverage=cov)["accepted"] is False

@pytest.mark.asyncio
async def test_model_selects_verified_app_logs_after_device_history():
    mcp=FakeMCP([READ_EVENTS,READ_DIAG])
    async def identities():
        return [{"id":"4382","label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"events":thermostat_events()},raw_logs()])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step==1:return {"tool_calls":[native("homebrain_find_device",{"name":"Thermostat"})]}
        if step==2:return {"tool_calls":[native("hub_read_devices",{"tool":"hub_list_device_events","args":{"deviceId":"4382"}})]}
        if step==3:
            assert "upstream_controller_decision_gap" in messages[-1]["content"]
            return {"tool_calls":[native("hub_read_diagnostics",{"tool":"hub_get_logs","args":{"appId":"3970","mode":"past","since":"2026-10-29T14:42:00+00:00","until":"2026-10-29T15:06:00+00:00"}})]}
        assert step==4
        assert "controller_decision_log_examples" in messages[-1]["content"]
        return {"content":"The scheduler recorded that radiator demand was satisfied."}
    out=await run_native_read_agent(question=QUESTION,chat=model,mcp=mcp,
                 executor=executor,max_rounds=4,max_reads=3,enable_model_reasoned_assessment=True)
    assert step==4 and len(executor.calls)==2
    assert out["native_diagnostics"]["requested_incident_evidence_coverage"]["controller_decision_log_count"]==1
