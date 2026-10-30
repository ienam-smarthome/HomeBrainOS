"""V2 semantic objective architecture — no keyword classifier or model-privileged IO."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.semantic_plan import (
    SemanticPlan, inventory_profile, parse_semantic_plan, semantic_plan,
)
from investigation_v2.semantic_execute import execute_inventory_plan

DEVICES=[
    {"id":"7805","label":"Livingroom Light 1","room":"Living Room",
     "capabilities":["Switch","SwitchLevel","ColorControl"],
     "attributes":{"switch":"on","power":"6 W","level":60}},
    {"id":"7840","label":"Bedroom 1 Light","room":"Bedroom 1",
     "capabilities":["Switch","ColorTemperature"],
     "attributes":{"switch":"off","power":0}},
    {"id":"4221","label":"TV","room":"Multimedia",
     "capabilities":["Switch","PowerMeter"],
     "attributes":{"switch":"on","power":85,"energy":2.4}},
    {"id":"7103","label":"Bedroom 3 Mesh","room":"Bedroom 3",
     "capabilities":["Switch","PowerMeter"],
     "attributes":{"switch":"off","power":"8 W","healthStatus":"offline"}},
    {"id":"3456","label":"Kitchen Motion Sensor","room":"Kitchen",
     "capabilities":["MotionSensor","Battery"],
     "attributes":{"motion":"active","battery":17}},
    {"id":"3457","label":"Bedroom 2 Motion Sensor","room":"Bedroom 2",
     "capabilities":["MotionSensor","Battery"],
     "attributes":{"motion":"inactive","battery":92}},
    {"id":"4000","label":"Livingroom Light Injection <script>","room":"Living Room",
     "capabilities":["Switch","ColorControl"],
     "attributes":{"switch":"off","power":None}},
]
PROVENANCE={"complete":True,"pages":5,"source":"fresh_projected_gateway"}
KEYS={"mode","scope","device_name","room","attribute","operator",
      "value","aggregation","limit"}


def plan(**overrides):
    default={
        "mode":"inventory","scope":"all","device_name":None,
        "room":None,"attribute":None,"operator":"none","value":None,
        "aggregation":"list","limit":10,
    }
    default.update(overrides)
    return default


def verified(**overrides):
    return parse_semantic_plan(plan(**overrides),inventory_profile(DEVICES))


@pytest.mark.parametrize(("description","options","expected_count"),[
    ("what lights are currently on",{
        "scope":"lights","attribute":"switch","operator":"eq","value":"on"},1),
    ("how many switches are off",{
        "scope":"switches","attribute":"switch","operator":"eq","value":"off",
        "aggregation":"count"},3),
    ("which devices report offline",{
        "scope":"all","attribute":"healthStatus","operator":"eq","value":"offline"},1),
    ("motion sensors with batteries below 20",{
        "scope":"sensors","attribute":"battery","operator":"lt","value":20},1),
    ("largest power draw",{
        "scope":"all","attribute":"power","aggregation":"top","limit":3},4),
])
def test_one_generic_executor_covers_unrelated_question_types(description,options,expected_count):
    query=verified(**options)
    result=execute_inventory_plan(query,DEVICES,PROVENANCE)
    assert result["answer_mode"]=="semantic_inventory"
    assert result["inventory_query"]["matched_count"]==expected_count
    assert result["inventory_query"]["inventory_complete"] is True
    assert result["answer"]["root_cause_verified"] is False
    assert "command" not in result["test_mode"]
    assert "read-only" in result["answer"]["text"].lower()


def test_rank_top_power_and_host_computes_exact_sum_not_model_arithmetic():
    rank=execute_inventory_plan(verified(attribute="power",aggregation="top",limit=3),
                                DEVICES,PROVENANCE)
    lines=rank["answer"]["text"]
    assert lines.index("TV")<lines.index("Bedroom 3 Mesh")<lines.index("Livingroom Light 1")
    assert "85" in lines and "8" in lines and "6" in lines
    total=execute_inventory_plan(verified(attribute="power",aggregation="sum"),
                                 DEVICES,PROVENANCE)
    # Without scope identities these meter values may overlap, so total
    # power cannot be added safely even when all numeric readings exist.
    assert total["inventory_query"]["aggregate_value"] is None
    assert "withheld" in total["answer"]["text"]
    assert total["inventory_query"]["aggregate_safe"] is False
    assert total["inventory_query"]["missing_readings"]>=1


def test_room_filter_and_name_require_real_verified_entity():
    result=execute_inventory_plan(
        verified(room="Living Room",scope="lights",attribute="switch",
                 operator="eq",value="on"),
        DEVICES,PROVENANCE)
    assert result["inventory_query"]["matched_count"]==1
    result2=execute_inventory_plan(
        verified(scope="named",device_name="TV",attribute="switch"),
        DEVICES,PROVENANCE)
    assert result2["inventory_query"]["matched_count"]==1
    with pytest.raises(ValueError):
        execute_inventory_plan(verified(scope="named",device_name="Ghost TV"),DEVICES,PROVENANCE)
    with pytest.raises(ValueError):
        verified(room="Kitchenette")
    with pytest.raises(ValueError):
        verified(attribute="credential")
    with pytest.raises(ValueError):
        verified(attribute="somethingInvented")


@pytest.mark.parametrize("overrides",[
    {"scope":"named","device_name":None},
    {"scope":"lights","device_name":"TV"},
    {"limit":10000},
    {"limit":True},
    {"attribute":"hubshellcommand"},
    {"attribute":"switch","operator":"gt","value":"on"},
    {"attribute":None,"operator":"eq","value":"off"},
    {"aggregation":"top","attribute":None},
    {"operator":"none","value":"secret"},
    {"value":{"tool":"delete"}},
    {"mode":"device_control"},
])
def test_host_rejects_untrusted_model_plan_fields(overrides):
    with pytest.raises(ValueError):
        verified(**overrides)


def test_opaque_bogus_field_and_prompt_injection_cannot_change_permissions():
    unsafe=plan(attribute="switch")
    unsafe["send_command"]={"deviceId":"7805","command":"off"}
    with pytest.raises(ValueError):
        parse_semantic_plan(unsafe,inventory_profile(DEVICES))
    malformed=plan(attribute="switch",scope="lights")
    malformed["limit"]="9999"
    with pytest.raises(ValueError):
        parse_semantic_plan(malformed,inventory_profile(DEVICES))


@pytest.mark.asyncio
async def test_configured_ai_interprets_semantics_but_never_calls_a_tool_itself():
    received=[]
    data=plan(scope="lights",attribute="switch",operator="eq",value="on")
    async def fake_model(messages,tools):
        received.extend(messages)
        assert tools==[]
        return {"content":json.dumps(data)}
    parsed=await semantic_plan(
        "Tell me which bulbs are glowing right now, please",DEVICES,fake_model)
    assert parsed.scope=="lights"
    assert parsed.attribute=="switch"
    assert parsed.value=="on"
    assert "tool" not in parsed.to_dict()
    assert "available_attributes" in received[1]["content"]
    assert "inventoried_device_count" in received[1]["content"]
    assert "password" not in received[1]["content"]


@pytest.mark.asyncio
async def test_model_asking_for_native_action_is_never_allowed():
    async def fake_model(messages,tools):
        return {"content":json.dumps(plan()),
                "tool_calls":[{"function":{"name":"turnOffEverything"}}]}
    with pytest.raises(ValueError,match="native tool"):
        await semantic_plan("Which devices have power?",DEVICES,fake_model)


@pytest.mark.asyncio
async def test_bound_semantic_planning_time_and_never_fabricate_on_failure():
    async def fake_model(messages,tools):
        await asyncio.sleep(2)
        return {"content":json.dumps(plan())}
    with pytest.raises(asyncio.TimeoutError):
        await semantic_plan("Show all high power devices",DEVICES,fake_model,
                            timeout_seconds=1)


def test_missing_readings_and_incomplete_source_are_disclosed():
    result=execute_inventory_plan(
        verified(scope="all",attribute="power",operator="gt",value=5),
        DEVICES,{"complete":False,"pages":3})
    assert result["inventory_query"]["missing_readings"]>=3
    assert "not verified complete" in result["answer"]["text"]
    assert "excluded, not assumed zero" in result["answer"]["text"]
    assert result["answer"]["validation_issues"]


def test_untrusted_labels_are_plain_text_not_executable_markup():
    result=execute_inventory_plan(verified(scope="lights"),DEVICES,PROVENANCE)
    assert "<script>" not in result["answer"]["text"]
    assert "Injection script" in result["answer"]["text"]

