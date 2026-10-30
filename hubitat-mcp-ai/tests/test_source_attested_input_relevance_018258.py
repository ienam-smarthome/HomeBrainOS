"""Event-notified app links are associations, not proof of causal initiation."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"rootfs"/"app"))
from unified_investigation_bridge import collect_unified_evidence,unified_investigation_instruction
from unified_incident_digest import source_incident_digest
from investigation_evidence_cycle import cross_source_discovery_checkpoint

Q=("Why did Zone Alpha Light and Zone Beta Light switch between "
   "14:50 and 15:30 GMT on 30 October 2026?")


def lookup(i,name):
    return {"success":True,"mutates":False,"tool":"hub_read_devices",
            "evidence_kind":"targeted_device_lookup",
            "details":{"reportedDeviceState":{"deviceId":str(i),"label":name}}}


def read(i,events,mutates=False):
    return {"success":True,"effect":"read","mutates":mutates,
            "supports_live_claim":True,"tool":"hub_read_devices",
            "sub_tool":"hub_list_device_events",
            "arguments":{"tool":"hub_list_device_events","args":{"deviceId":str(i)}},
            "details":{"observedEvents":events}}


def journal(i):
    return {"tool":"homebrain_evidence_journal","success":True,
            "effect":"read","mutates":False,
            "evidence_kind":"group_archived_switch_history",
            "arguments":{"device_id":str(i)},
            "details":{"observations":[
                {"device_id":str(i),"attribute":"switch","value":"on",
                 "date":"2026-10-30T15:07:14.132+00:00","timestamp_basis":"source"},
                {"device_id":str(i),"attribute":"switch","value":"off",
                 "date":"2026-10-30T15:11:09.744+00:00","timestamp_basis":"source"},
            ]}}


def event(i,app,when="15:07:45.574"):
    return {"name":"motion","value":"active",
            "date":"2026-10-30T"+when+"+00:00",
            "type":"physical","producedBy":{"deviceId":str(i)},
            "triggered":[{"appId":app,"handler":"motionHandler"}]}


def receipts(sensor_app="4002",sensor_mutates=False):
    return [
        lookup(101,"Zone Alpha Light"),lookup(102,"Zone Beta Light"),
        read(101,[{"name":"command-setLevel",
                    "date":"2026-10-30T14:50:37.911+00:00",
                    "producedBy":{"appId":"4001"}}]),
        read(102,[{"name":"level","value":"60",
                    "date":"2026-10-30T14:50:39.100+00:00",
                    "producedBy":{"deviceId":"900"},
                    "triggered":[{"appId":"4001"}]}]),
        journal(101),journal(102),
        read(201,[event(201,sensor_app)],mutates=sensor_mutates),
    ]


def test_unrelated_observed_app_is_not_promoted_to_target_cause():
    facts=collect_unified_evidence(receipts(),Q)
    assert facts and facts["target_observed_command_app_ids"]==["4001"]
    links=facts["input_app_relationships"]
    assert len(links)==1
    link=links[0]
    assert link["input_device_id"]=="201"
    assert link["input_notified_app_ids"]==["4002"]
    assert link["shared_target_command_app_ids"]==[]
    assert link["relationship"]=="different-observed-app-associations"
    assert link["historical_causation_verified"] is False
    text=source_incident_digest(facts)
    assert "device 201 notified app(s) 4002" in text
    assert "none appears among the observed target command/listener apps" in text
    assert "Unobserved or alternative control paths cannot be excluded" in text
    assert "device 201: 15:07:45 active" in text
    prompt=unified_investigation_instruction(receipts(),Q)
    assert prompt and '"input_app_relationships"' in prompt
    checkpoint=cross_source_discovery_checkpoint(receipts(),Q)
    assert checkpoint and '"inputAppRelationships"' in checkpoint


def test_shared_command_app_is_only_a_relationship_lead():
    facts=collect_unified_evidence(receipts(sensor_app="4001"),Q)
    link=facts["input_app_relationships"][0]
    assert link["relationship"]=="shared-observed-target-command-app"
    assert link["shared_target_command_app_ids"]==["4001"]
    assert link["historical_causation_verified"] is False
    msg=source_incident_digest(facts)
    assert "device 201 shares app(s) 4001" in msg
    assert "not proof of cause" in msg


def test_unverified_source_cannot_supply_relationship():
    facts=collect_unified_evidence(receipts(sensor_mutates=True),Q)
    assert facts["input_app_relationships"]==[]
    assert facts["independent_input_observations"]==[]


def test_late_or_out_of_window_input_notification_does_not_create_link():
    rows=receipts()
    rows[-1]["details"]["observedEvents"]=[event(201,"4001",when="19:07:45.574")]
    facts=collect_unified_evidence(rows,Q)
    assert facts["input_app_relationships"]==[]
    assert facts["target_observed_command_app_ids"]==["4001"]
