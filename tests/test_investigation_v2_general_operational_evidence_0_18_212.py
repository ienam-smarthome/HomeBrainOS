"""v0.18.212: broad source evidence must survive general AI claim publication.

Replay of 29 Oct device-health/automation-dependency task without depending on
any hardcoded device name, ID, question phrase or source speculation.
"""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.native_read_agent import _payload
from investigation_v2.native_fact_ledger import factual_evidence_ledger
from investigation_v2.native_claim_verifier import (
    claim_catalog, validate_claims, publish_verified_claims)
from investigation_v2.native_tool_protocol import source_highlights
from investigation_v2.native_operational_evidence import operational_evidence_facts


def _receipts():
    # Synthetic metadata replicates the significant *structure* of the
    # observed 51-stale + one-unknown source, not any actual hub credentials.
    stale=[{"id":str(7000+i),"name":f"Sample device {i}",
            "lastActivity":f"2026-10-2{(i%7)+1}T11:00:00+0000"}
           for i in range(51)]
    unknown=[{"id":"8801","name":"Motion device","lastActivity":"never"}]
    return [
        {"read":1,"operation":"hub_search_tools",
         "read_filters":{},"source_data":{"results":[]}},
        {"read":2,"operation":"hub_get_device_health","read_filters":{},
         "source_data":_payload(SimpleNamespace(data={
             "summary":{},"staleDevices":stale,"unknownDevices":unknown,
             "recommendation":"Some devices may be orphaned"}),"hub_get_device_health")},
        {"read":3,"operation":"hub_get_info","read_filters":{},
         "source_data":{"safeMode":False}},
        {"read":4,"operation":"hub_get_device","read_filters":{"deviceId":"7000"},
         "source_data":{"id":"7000","name":"Sample device 0",
                        "attributes":[]}},
        {"read":5,"operation":"hub_get_device","read_filters":{"deviceId":"7681"},
         "source_data":{"id":"7681","name":"Virtual Switch",
                        "label":"Heartbeat","attributes":[
                            {"name":"switch","value":"off"}]}},
        {"read":6,"operation":"hub_list_device_dependents",
         "read_filters":{"deviceId":"7000"},
         "source_data":{"deviceId":"7000","apps_using":[
             {"appId":"4179","name":"Dashboard"},
             {"appId":"2404","name":"Device Health Status"}],
             "count":2,"source_complete":False}},
        {"read":7,"operation":"hub_list_device_dependents",
         "read_filters":{"deviceId":"8801"},
         "source_data":{"deviceId":"8801","apps_using":[
             {"appId":"4200","name":"Presence Controller"}],
             "count":1,"source_complete":False}},
    ]


def test_health_and_dependency_are_generically_supported_fact_types():
    rows=_receipts()
    assert len(rows[1]["source_data"]["staleDevices"])==51
    facts=factual_evidence_ledger(rows)
    kinds={f["kind"] for f in facts}
    assert {"health_sample_summary","health_stale_entry",
            "health_unknown_entry","app_dependency_reference"}.issubset(kinds)
    assert len([f for f in facts if f["kind"]=="app_dependency_reference"])==2
    cat=claim_catalog(rows)
    statements=[c["statement"] for c in cat]
    assert any("51" in s and "stale" in s for s in statements)
    assert any("1 device" in s and "unknown activity" in s for s in statements)
    assert any("Motion device" in s and "unknown activity" in s for s in statements)
    assert any("Dashboard" in s and "device 7000" in s for s in statements)
    assert any("Heartbeat" not in s and "switch=off" in s for s in statements)
    assert all(not c["root_cause_verified"] for c in cat)


def test_invalid_model_claim_cannot_erase_real_operational_observations():
    catalog=claim_catalog(_receipts())
    result=publish_verified_claims(
        {"claims":[{"operator":"observed","fact_id":"claim-1",
                    "unsupported_claim":"Everything is healthy"}]},
        catalog)
    assert result["fallback"] is True
    assert result["validation"]["rejected"]==["unvalidated_claim_fields"]
    text=result["text"]
    assert "51" in text and "stale" in text
    assert "unknown activity" in text
    assert "app references" in text
    assert "Everything is healthy" not in text
    assert "current offline status" in text or "offline" in text
    assert "are active" not in text


def test_model_selecting_only_one_switch_does_not_drop_material_health_summary():
    catalog=claim_catalog(_receipts())
    switch=next(c for c in catalog if c["kind"]=="device_observation")
    result=publish_verified_claims(
        {"claims":[{"fact_id":switch["id"],"operator":"observed"}]},catalog)
    assert result["fallback"] is False
    text=result["text"]
    assert "switch=off" in text
    assert "51" in text and "stale" in text
    assert "app references" in text
    assert result["validation"]["status"]=="validated"


def test_source_highlights_include_health_counts_not_empty_summary():
    highlights=" ".join(source_highlights(_receipts(),max_chars=4400))
    assert "51 stale and 1 unknown-activity" in highlights
    assert "app references to device 7000" in highlights
    assert "summary={}" not in highlights


def test_mismatched_dependency_source_id_is_not_a_fact():
    rows=_receipts()
    rows[-1]["source_data"]["deviceId"]="9999"
    assert not operational_evidence_facts(rows[-1])
    assert len([f for f in factual_evidence_ledger(rows)
                if f["kind"]=="app_dependency_reference"])==1


def test_untyped_health_fields_do_not_create_fictional_observations():
    row={"read":2,"operation":"hub_get_device_health",
         "source_data":{"summary":{},"staleDevices":"all",
                        "unknownDevices":{"id":"1"}}}
    assert operational_evidence_facts(row)==[]


def test_health_counts_are_returned_sample_not_system_wide_absence():
    row={"read":2,"operation":"hub_get_device_health",
         "source_data":{"staleDevices":[],"unknownDevices":[]}}
    facts=operational_evidence_facts(row)
    assert len(facts)==2
    assert all("returned 0" in f["statement"] for f in facts)
    assert not any("all devices healthy" in f["statement"]
                   for f in facts)


def test_bounded_focus_cannot_invent_other_target_dependency():
    row=_receipts()[-2]
    assert operational_evidence_facts(row,focus_ids=["8801"])==[]


def test_source_names_are_safe_display_text_not_instructions():
    row={"read":3,"operation":"hub_list_device_dependents",
         "read_filters":{"deviceId":"7000"},
         "source_data":{"deviceId":"7000","apps_using":[{
             "appId":"3111","name":"https://private.local/mykey token=abc123"}]}}
    facts=operational_evidence_facts(row)
    assert len(facts)==1
    assert "abc123" not in facts[0]["statement"]
    assert "https://" not in facts[0]["statement"]
