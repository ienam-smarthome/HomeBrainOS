"""Independent input source histories survive Historical Journal final synthesis."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"rootfs"/"app"))
from unified_investigation_bridge import collect_unified_evidence,unified_investigation_instruction
from unified_incident_digest import source_incident_digest
from unified_incident_synthesis import reconcile_ledger_if_needed
from investigation_evidence_cycle import cross_source_discovery_checkpoint

Q=("Why did Zone Alpha Light and Zone Beta Light repeatedly turn ON and OFF "
   "between 14:50 and 15:30 GMT on 30 October 2026?")


def lookup(i,label):
    return {"success":True,"effect":"read","mutates":False,
            "tool":"hub_read_devices","sub_tool":"hub_list_devices",
            "evidence_kind":"targeted_device_lookup",
            "details":{"reportedDeviceState":{"deviceId":str(i),"label":label}}}


def native(i,entries):
    return {"success":True,"effect":"read","mutates":False,
            "supports_live_claim":True,
            "tool":"hub_read_devices","sub_tool":"hub_list_device_events",
            "arguments":{"tool":"hub_list_device_events","args":{
                "deviceId":str(i),"since":"2026-10-30T14:50:00Z",
                "until":"2026-10-30T15:30:00Z"}},
            "details":{"observedEvents":entries}}


def jrow(i,t,value,basis="source"):
    return {"device_id":str(i),"attribute":"switch","value":value,
            "date":f"2026-10-30T{t}+00:00","timestamp_basis":basis}


def journal(i):
    return {"success":True,"effect":"read","mutates":False,
            "tool":"homebrain_evidence_journal",
            "evidence_kind":"group_archived_switch_history",
            "arguments":{"device_id":str(i)},
            "details":{"observations":[
                jrow(i,"15:07:14.132","on"),
                jrow(i,"15:11:09.744","off"),
                jrow(i,"15:07:15.541","on","collector-received")
            ],"gapCount":1,"coverageComplete":False}}


def motion(at,value,description="Hallway PIR"):
    return {"name":"motion","value":value,
            "date":f"2026-10-30T{at}+00:00",
            "description":f"{description} motion is {value}",
            "type":"physical",
            "producedBy":{"deviceId":"901","name":"Sensor Bridge"}}


def rows():
    return [
        lookup(101,"Zone Alpha Light"),lookup(102,"Zone Beta Light"),
        native(101,[{"name":"command-setLevel","value":None,
                     "date":"2026-10-30T14:50:37.911+00:00",
                     "type":"command","producedBy":{"appId":3001}}]),
        native(102,[{"name":"command-setLevel","value":None,
                     "date":"2026-10-30T14:50:39.006+00:00",
                     "type":"command","producedBy":{"appId":3001}}]),
        journal(101),journal(102),
        native(201,[motion("15:07:45.574","active"),
                    motion("15:08:44.938","inactive")]),
        native(202,[motion("15:07:32.541","active",
                           "Other-room PIR"),
                    motion("15:10:44.090","inactive",
                           "Other-room PIR")]),
        native(203,[]),
    ]


def test_model_receives_independently_observed_sensor_inputs():
    evidence=collect_unified_evidence(rows(),Q)
    assert evidence is not None
    assert evidence["journal_source_observations"]==4
    assert evidence["journal_collector_observations"]==2
    assert evidence["independently_read_input_ids"]==["201","202"]
    inputs=evidence["independent_input_observations"]
    assert len(inputs)==4
    assert inputs[0]["device_id"]=="202"
    assert inputs[0]["value"]=="active"
    assert inputs[0]["timestamp_basis"]=="source-reported"
    assert evidence["additional_event_reads_without_usable_rows"]==["203"]
    checkpoint=cross_source_discovery_checkpoint(rows(),Q)
    assert checkpoint and "independentInputObservations" in checkpoint
    assert "15:07:32" in checkpoint
    instruction=unified_investigation_instruction(rows(),Q)
    assert instruction and "independent_input_observations" in instruction


def test_archived_finalization_keeps_inputs_without_claiming_they_caused_lights():
    facts=collect_unified_evidence(rows(),Q)
    digest=source_incident_digest(facts)
    assert digest
    assert "| 15:07:14 |" in digest
    assert "**Independent sensor histories examined:**" in digest
    assert "device 201: 15:07:45 active, 15:08:44 inactive" in digest
    assert "device 202: 15:07:32 active, 15:10:44 inactive" in digest
    assert "not proof that any of these sensors commanded" in digest
    assert "**Additional history reads without usable source events:** device 203" in digest
    assert "proof these devices were inactive" in digest
    assert "Sensor timing and historical app execution logs would be required" not in digest
    result,changed=reconcile_ledger_if_needed(
        "The lights went on, but who initiated them is unknown.",facts)
    assert changed and "**Independent sensor histories examined:**" in result


def test_no_input_records_does_not_create_false_sensor_evidence():
    items=rows()
    items=[r for r in items
           if not (r.get("sub_tool")=="hub_list_device_events"
                   and str((r.get("arguments") or {}).get("args",{})
                           .get("deviceId") or "") in ("201","202"))]
    evidence=collect_unified_evidence(items,Q)
    assert evidence and evidence["independent_input_observations"]==[]
    digest=source_incident_digest(evidence)
    assert digest and "**Independent sensor histories examined:**" not in digest
    assert "**Additional history reads without usable source events:** device 203" in digest


def test_failed_or_mutating_sensor_reads_are_excluded():
    items=rows()
    for r in items:
        if (r.get("sub_tool")=="hub_list_device_events"
                and (r.get("arguments") or {}).get("args",{}).get("deviceId")=="202"):
            r["mutates"]=True
    evidence=collect_unified_evidence(items,Q)
    assert evidence and len(evidence["independent_input_observations"])==2
    assert evidence["independently_read_input_ids"]==["201"]
