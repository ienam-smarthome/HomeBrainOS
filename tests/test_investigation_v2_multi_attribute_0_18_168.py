"""v0.18.168: light status must use separately sourced switch and level evidence."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from current_state_claim_contract import ground_current_device_status
from investigation_v2.semantic_plan import parse_semantic_plan, inventory_profile
from investigation_v2.semantic_execute import (
    ground_current_attribute_request, ground_named_inventory_plan,
    execute_inventory_plan,
)

DEVICES=[{"id":"7828","label":"Livingroom Light 2","name":"Generic Dimmer",
          "roomName":"Living Room","attributes":[
             {"name":"switch","value":"on"},{"name":"level","value":30}]},
         {"id":"7829","label":"Hallway Light 1","name":"Generic Dimmer",
          "roomName":"Hallway","attributes":[{"name":"switch","value":"off"}]}]
QUESTION="Read the current switch state and brightness level of Livingroom Light 2 directly from Hubitat. Do not change anything."

def plan(*,attribute=None):
    raw=dict(mode="inventory",scope="named",device_name="Livingroom Light 2",
        room=None,attribute=attribute,operator="none",value=None,
        aggregation="list",limit=1)
    return parse_semantic_plan(raw,inventory_profile(DEVICES))

def test_both_attributes_are_independently_reported_in_same_current_snapshot():
    p=ground_named_inventory_plan(plan(),QUESTION,DEVICES)
    p=ground_current_attribute_request(p,QUESTION)
    assert p.attributes==("switch","level")
    result=execute_inventory_plan(p,DEVICES,{"complete":True,"pages":5})
    assert "switch=on, level=30%" in result["answer"]["text"]
    assert result["inventory_query"]["reported_device_values"]==[
        {"id":"7828","label":"Livingroom Light 2",
         "reported_attributes":{"switch":"on","level":30}}]
    assert result["inventory_query"]["missing_readings"]==0
    assert result["semantic_plan"]["attributes"]==["switch","level"]

def test_model_only_selects_switch_host_recovers_explicit_second_attribute():
    p=ground_current_attribute_request(plan(attribute="switch"),QUESTION)
    assert p.attribute is None and p.attributes==("switch","level")

def test_absent_level_is_explicitly_unavailable_and_not_inferred_from_write():
    devices=[{**DEVICES[0],"attributes":[{"name":"switch","value":"on"}]}]
    p=ground_current_attribute_request(plan(),QUESTION)
    result=execute_inventory_plan(p,devices,{"complete":True,"pages":1})
    assert "switch=on, level=unavailable" in result["answer"]["text"]
    assert "30%" not in result["answer"]["text"]
    assert result["inventory_query"]["missing_readings"]==1
    assert result["inventory_query"]["reported_device_values"][0]["reported_attributes"]["level"] is None

def test_unrelated_or_non_current_question_never_infers_an_attribute_projection():
    p=plan()
    assert ground_current_attribute_request(p,"Why did Livingroom Light 2 go off?") is p
    assert ground_current_attribute_request(p,"What is Livingroom Light 2?") is p

def test_status_claim_from_switch_only_snapshot_cannot_invent_brightness():
    evidence=[{"success":True,"evidence_kind":"targeted_device_lookup",
               "details":{"reportedDeviceState":{"deviceId":"7828",
                   "label":"Livingroom Light 2",
                   "reportedAttributes":{"switch":"on"}}}},
              {"success":True,"evidence_kind":"deterministic_targeted_device_resolution"}]
    text="Livingroom Light 2 is currently **on** with a brightness level of **30%**."
    fixed,unknown=ground_current_device_status(text,evidence,"live-read")
    assert "level" in unknown
    assert "brightness level of **30%**" not in fixed
    assert "**Switch:** on" in fixed
    assert "Measurements not present" in fixed

def test_status_claim_accepts_fresh_reported_level_if_matched():
    evidence=[{"success":True,"evidence_kind":"targeted_device_lookup",
               "details":{"reportedDeviceState":{"deviceId":"7828",
                   "label":"Livingroom Light 2",
                   "reportedAttributes":{"switch":"on","level":30}}}},
              {"success":True,"evidence_kind":"deterministic_targeted_device_resolution"}]
    text="Livingroom Light 2 is currently **on** with a brightness level of **30%**."
    fixed,unknown=ground_current_device_status(text,evidence,"live-read")
    assert fixed==text and unknown==[]

def test_status_claim_detects_contradicting_fresh_level():
    evidence=[{"success":True,"evidence_kind":"targeted_device_lookup",
               "details":{"reportedDeviceState":{"deviceId":"7828",
                   "label":"Livingroom Light 2",
                   "reportedAttributes":{"switch":"on","level":60}}}}]
    text="Livingroom Light 2 is currently on with a brightness level of 30%."
    fixed,unknown=ground_current_device_status(text,evidence,"live-read")
    assert "level" in unknown and "30%" not in fixed
    assert "**Brightness:** 60" in fixed
