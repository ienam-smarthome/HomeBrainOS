"""Energy measurement-role safety: brand-neutral, read-only, source-backed.

These examples mirror a whole-house meter and downstream loads but never
encode provider names or meter IDs as a special case in production code.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from datetime import datetime, timezone

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))

from investigation_v2.semantic_plan import inventory_profile, parse_semantic_plan
from investigation_v2.semantic_execute import execute_inventory_plan, _quantity
from investigation_v2.measurement_semantics import (
    candidates, load_operator_meter_roles, measurement_scope,
    validated_model_hints,
)

DEVICES=[
    {"id":"9900","label":"Provider Live Meter","room":"Energy",
     "capabilities":["PowerMeter"],"attributes":{"power":"231 W"}},
    {"id":"100","label":"Fridge","room":"Appliances",
     "capabilities":["PowerMeter"],"attributes":{"power":"84 W"}},
    {"id":"101","label":"Fan Switch","room":"Ventilation",
     "capabilities":["PowerMeter"],"attributes":{"power":"33.1 W"}},
    {"id":"102","label":"Mini PC","room":"Computers",
     "capabilities":["PowerMeter"],"attributes":{"power":"28 W"}},
    {"id":"103","label":"Bedroom Mesh","room":"Sockets",
     "capabilities":["PowerMeter"],"attributes":{"power":"8 W"}},
    {"id":"104","label":"Halo Plug","room":"Sockets",
     "capabilities":["PowerMeter"],"attributes":{"power":"6.9 W"}},
    {"id":"105","label":"Electrical Submeter","room":"Energy",
     "capabilities":["PowerMeter"],"attributes":{
         "power":"79 W","measurementScope":"circuit_subtotal"}},
    {"id":"106","label":"Other numeric sensor","room":"Sensors",
     "capabilities":["PowerMeter"],"attributes":{"power":None}},
]
PROVENANCE={"complete":True,"pages":5}
HINTS=[{"id":"9900","label":"Provider Live Meter","role":"site_total"},
       {"id":"100","label":"Fridge","role":"individual_load"},
       {"id":"101","label":"Fan Switch","role":"individual_load"},
       {"id":"102","label":"Mini PC","role":"individual_load"},
       {"id":"103","label":"Bedroom Mesh","role":"individual_load"},
       {"id":"104","label":"Halo Plug","role":"individual_load"}]


def raw_plan(**extra):
    result={
        "mode":"inventory","scope":"all","device_name":None,
        "room":None,"attribute":"power","operator":"none","value":None,
        "aggregation":"top","limit":5,
    }
    result.update(extra)
    return result


def plan(**extra):
    return parse_semantic_plan(raw_plan(**extra),inventory_profile(DEVICES))


def test_general_power_ranking_never_mixes_a_site_total_with_downstream_loads():
    output=execute_inventory_plan(plan(measurement_roles=HINTS),DEVICES,PROVENANCE)
    report=output["answer"]["text"]
    lines=[line for line in report.splitlines() if line.startswith("• ")]
    assert len(lines)>=5
    assert "Fridge" in lines[0]
    assert "Fan Switch" in lines[1]
    assert "Mini PC" in lines[2]
    assert "Bedroom Mesh" in lines[3]
    assert "Halo Plug" in lines[4]
    assert not any("Live Meter" in line for line in lines[:5])
    assert "Provider Live Meter" in report
    assert "classification not independently verified" in report
    assert len(output["inventory_query"]["suppressed_overlapping_meters"])==2
    assert output["inventory_query"]["matched_count"]==5
    assert output["inventory_query"]["unclassified_measurement_scopes"]==0
    assert output["inventory_query"]["inferred_individual_loads"]==5
    assert "never add them together" in report
    assert output["inventory_query"]["aggregate_safe"] is False


def test_source_metadata_precedes_conflicting_model_hypothesis():
    hints=validated_model_hints(
        [{"id":"105","label":"Electrical Submeter","role":"individual_load"}],
        candidates(DEVICES),
    )
    result=measurement_scope(DEVICES[6],hints=hints)
    assert result.role=="circuit_subtotal"
    assert result.provenance=="reported_device_metadata"
    assert result.verified is False


def test_operator_roles_precede_model_and_source_and_are_checked_against_inventory():
    mapping=load_operator_meter_roles('{"9900":"site_total","100":"individual_load"}',DEVICES)
    assert measurement_scope(DEVICES[0],operator_roles=mapping).provenance=="operator_confirmed"
    assert measurement_scope(DEVICES[0],operator_roles=mapping).verified is True
    out=execute_inventory_plan(plan(),DEVICES,PROVENANCE,operator_roles=mapping)
    assert "Provider Live Meter" in out["answer"]["text"]
    assert out["inventory_query"]["suppressed_overlapping_meters"][0]["role"]=="site_total"
    for mapping_raw in ('{"99999":"site_total"}', '{"100":"invalid"}','[]',
                        '{"100": "site_total", "other": "unknown"}','not json'):
        with pytest.raises(ValueError):
            load_operator_meter_roles(mapping_raw,DEVICES)


def test_unclassified_site_meter_is_disclosed_as_a_provisional_measurement():
    out=execute_inventory_plan(plan(),DEVICES,PROVENANCE)
    assert out["inventory_query"]["unclassified_measurement_scopes"]>=6
    assert "unknown or unconfirmed" in out["answer"]["text"]
    assert "Provider Live Meter" in out["answer"]["text"]
    assert out["inventory_query"]["suppressed_overlapping_meters"][0]["label"]=="Electrical Submeter"
    # Without confirmed or inferred metadata we must not silently claim that
    # all displayed meters are individual loads.
    assert out["answer"]["validation_issues"]


def test_mixed_power_total_is_withheld_but_known_individual_only_is_valid():
    out=execute_inventory_plan(
        plan(aggregation="sum",measurement_roles=HINTS),DEVICES,PROVENANCE)
    assert out["inventory_query"]["aggregate_value"] is None
    assert "withheld" in out["answer"]["text"]
    assert "231.00 W" not in out["answer"]["text"]

    subset=DEVICES[1:6]
    prof=inventory_profile(subset)
    guessed=validated_model_hints(HINTS[1:],prof["meter_candidates"])
    roles={x["id"]:x["role"] for x in guessed}
    calculated=execute_inventory_plan(
        parse_semantic_plan(raw_plan(aggregation="sum"),prof),
        subset,PROVENANCE,operator_roles=roles)
    assert calculated["inventory_query"]["aggregate_value"]==160.0
    assert "160.00 W" in calculated["answer"]["text"]


def test_power_and_energy_units_are_distinct_and_checked():
    assert _quantity("2 kW","power")==2000.0
    assert _quantity("231 W","power")==231.0
    assert _quantity("0.22 kWh","energy")==0.22
    assert _quantity("220 Wh","energy")==0.22
    assert _quantity("2.5 kWh","power") is None
    assert _quantity("120 W","energy") is None
    assert _quantity("garbage","power") is None
    assert _quantity(None,"power") is None


@pytest.mark.parametrize("hints", [
    [{"id":"9999","label":"Imaginary","role":"site_total"}],
    [{"id":"9900","label":"Wrong label","role":"site_total"}],
    [{"id":"9900","label":"Provider Live Meter","role":"root"}],
    [{"id":"9900","label":"Provider Live Meter","role":"site_total",
      "send_command":"off"}],
    [{"id":"9900","label":"Provider Live Meter","role":"site_total"},
     {"id":"9900","label":"Provider Live Meter","role":"site_total"}],
    {"9900":"site_total"},
])
def test_untrusted_ai_cannot_invent_devices_roles_or_commands(hints):
    with pytest.raises(ValueError):
        parse_semantic_plan(raw_plan(measurement_roles=hints),
                            inventory_profile(DEVICES))


def test_model_prompt_contains_bounded_evidence_catalogue_not_brand_rules():
    from investigation_v2.semantic_plan import _MODEL_SYSTEM
    profile=inventory_profile(DEVICES)
    assert len(profile["meter_candidates"])==7
    assert profile["meter_candidates"][0]["id"]=="9900"
    assert "Measurement role interpretation is a separate later step" in _MODEL_SYSTEM
    assert "Octopus" not in _MODEL_SYSTEM
    assert "Provider Live Meter" not in _MODEL_SYSTEM

