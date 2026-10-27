"""v0.18.166: safe multi-named current reads from verified Hubitat inventory."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.semantic_plan import (SemanticPlan, parse_semantic_plan, inventory_profile)
from investigation_v2.semantic_execute import (ground_named_inventory_plan, execute_inventory_plan)
from investigation_v2.test_service import resolve_verified_device_subjects

DEVICES=[
 {"id":"7829","label":"Hallway Light 1","name":"Hallway Light",
  "roomName":"Hallway","attributes":[{"name":"switch","value":"on"}]},
 {"id":"7828","label":"Livingroom Light 2","name":"Livingroom Light",
  "roomName":"Living Room","attributes":[{"name":"switch","value":"off"}]},
 {"id":"9911","label":"Other Light","roomName":"Other",
  "attributes":[{"name":"switch","value":"on"}]},
 # Two unrelated sockets expose generic driver name 'switch'.
 # The word 'switch' in 'switch state of Hallway Light' is an attribute,
 # NOT a third target. This reproduces the live 422 on 27 October.
 {"id":"7786","label":"LivCAM socket","name":"switch","roomName":"Sockets",
  "attributes":[{"name":"switch","value":"on"}]},
 {"id":"7787","label":"FP2 Livingroom socket","name":"switch","roomName":"Sockets",
  "attributes":[{"name":"switch","value":"off"}]},
]
QUESTION="What is the current switch state of Hallway Light 1 and Livingroom Light 2? Read both devices directly from Hubitat. Do not change anything."

def make_plan(**overrides):
    fields=dict(mode="inventory",scope="named",device_name=None,
       room=None,attribute="switch",operator="none",value=None,
       aggregation="list",limit=1,
       device_names=["Hallway Light 1","Livingroom Light 2"])
    fields.update(overrides)
    return parse_semantic_plan(fields,inventory_profile(DEVICES))

def test_two_named_devices_can_be_read_with_independent_values():
    plan=ground_named_inventory_plan(make_plan(),QUESTION,DEVICES)
    assert plan.device_names==("Hallway Light 1","Livingroom Light 2")
    assert plan.limit>=2
    result=execute_inventory_plan(plan,DEVICES,{"complete":True,"pages":5})
    answer=result["answer"]["text"]
    assert "Hallway Light 1 — on" in answer
    assert "Livingroom Light 2 — off" in answer
    assert "Other Light" not in answer
    assert result["inventory_query"]["matched_count"]==2
    assert result["inventory_query"]["missing_readings"]==0

def test_host_recovers_from_ai_joining_two_names_into_one():
    plan=make_plan(device_name="Hallway Light 1 and Livingroom Light 2",device_names=[])
    grounded=ground_named_inventory_plan(plan,QUESTION,DEVICES)
    assert grounded.device_name is None
    assert grounded.device_names==("Hallway Light 1","Livingroom Light 2")
    assert len(resolve_verified_device_subjects(QUESTION,DEVICES)[0])==2

def test_model_room_guess_cannot_drop_named_device():
    plan=make_plan(room="Hallway")
    grounded=ground_named_inventory_plan(plan,QUESTION,DEVICES)
    assert grounded.room is None
    assert execute_inventory_plan(grounded,DEVICES,{"complete":True})["inventory_query"]["matched_count"]==2

def test_model_cannot_add_device_not_present_in_question():
    plan=make_plan(device_names=["Hallway Light 1","Other Light"])
    with pytest.raises(ValueError,match="differ from verified question targets"):
        ground_named_inventory_plan(plan,QUESTION,DEVICES)

def test_missing_or_duplicate_device_names_fail_closed():
    plan=make_plan(device_names=["Hallway Light 1","not a device"])
    with pytest.raises(ValueError,match="does not uniquely match"):
        ground_named_inventory_plan(plan,QUESTION,DEVICES)
    with pytest.raises(ValueError,match="duplicate named device"):
        make_plan(device_names=["Hallway Light 1","hallway light 1"])
    dupe=[*DEVICES,{"id":"9900","label":"Livingroom Light 2","attributes":[{"name":"switch","value":"on"}]}]
    with pytest.raises(ValueError,match="Ambiguous device name"):
        ground_named_inventory_plan(make_plan(),QUESTION,dupe)

def test_legacy_single_named_device_remains_supported():
    plan=make_plan(device_name="Hallway Light 1",device_names=[])
    scoped=ground_named_inventory_plan(plan,"What is the switch state of Hallway Light 1?",DEVICES)
    result=execute_inventory_plan(scoped,DEVICES,{"complete":True})
    assert result["inventory_query"]["matched_count"]==1

def test_non_inventory_and_non_named_objectives_unaffected():
    plan=SemanticPlan(mode="investigation",scope="named",device_name="Hallway Light 1")
    assert ground_named_inventory_plan(plan,QUESTION,DEVICES) is plan


def test_attribute_word_switch_is_not_a_third_device_subject():
    ids, resolved, method = resolve_verified_device_subjects(QUESTION,DEVICES)
    assert ids==("7829","7828")
    assert [item["label"] for item in resolved]==[
        "Hallway Light 1","Livingroom Light 2"]
    assert method=="question"
    result=execute_inventory_plan(
        ground_named_inventory_plan(make_plan(),QUESTION,DEVICES),
        DEVICES,{"complete":True,"pages":5})
    assert result["inventory_query"]["matched_count"]==2
    assert "LivCAM socket" not in result["answer"]["text"]
    assert "FP2 Livingroom socket" not in result["answer"]["text"]


@pytest.mark.parametrize("question",[
    "Check the switch and Hallway Light 1.",
    "Please read the switch, then Hallway Light 1.",
    "Is switch on?",
    "What is the state of the switch and Hallway Light 1?",
])
def test_genuine_generic_switch_device_ambiguity_still_fails_closed(question):
    with pytest.raises(ValueError,match="Ambiguous device name"):
        resolve_verified_device_subjects(question,DEVICES)


def test_other_property_qualifier_before_strong_named_target():
    sensors=[*DEVICES,
        {"id":"8123","label":"Temp Meter A","name":"temperature"},
        {"id":"8124","label":"Temp Meter B","name":"temperature"}]
    ids,_,_=resolve_verified_device_subjects(
        "What is the temperature reading of Hallway Light 1?",sensors)
    assert ids==("7829",)


def test_not_an_attribute_qualifier_without_an_exact_subject():
    with pytest.raises(ValueError,match="Ambiguous device name"):
        resolve_verified_device_subjects("What is the switch state?",DEVICES)
