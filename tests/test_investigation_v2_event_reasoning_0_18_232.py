"""v0.18.232: replay the actual thermostat incident, not command counts.

Use the user's 29 October 14:54 control/state timeline and numerous later
temperature readings. The model must receive transition evidence from the
asked incident, with independent proof references; unstructured responses
must never become a device-ID and command-count user-facing answer.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_event_relevance import clock_candidates
from investigation_v2.native_incident_relevance import dated_incident_evidence
from investigation_v2.native_operational_sequence import operational_sequence_brief
from investigation_v2.native_reasoned_assessment import verify_natural_hypothesis
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_incident_relevance_0_18_229 import READ_EVENTS, history
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor

QUESTION = (
    "Why did my heating stop at around 2:54 pm on 29 October 2026? "
    "Was this normal thermostat behaviour or a fault? Read only."
)


def thermostat_events():
    core = [
        {"name": "heatingSetpoint", "value": "26.0",
         "date": "2026-10-29T14:48:18.301+00:00",
         "producedBy": {"appId": "3970",
                        "name": "00 Smart Thermostat Scheduler"}},
        {"name": "command-setHeatingSetpoint",
         "date": "2026-10-29T14:48:18.327+00:00",
         "producedBy": {"appId": "3970",
                        "name": "00 Smart Thermostat Scheduler"}},
        {"name": "thermostatOperatingState", "value": "heating",
         "date": "2026-10-29T14:48:36.785+00:00",
         "producedBy": {"deviceId": "4382", "name": "Thermostat"}},
        {"name": "heatingSetpoint", "value": "12.0",
         "date": "2026-10-29T14:54:18.037+00:00",
         "producedBy": {"appId": "3970",
                        "name": "00 Smart Thermostat Scheduler"}},
        {"name": "command-setHeatingSetpoint",
         "date": "2026-10-29T14:54:18.070+00:00",
         "producedBy": {"appId": "3970",
                        "name": "00 Smart Thermostat Scheduler"}},
        {"name": "thermostatOperatingState", "value": "idle",
         "date": "2026-10-29T14:54:36.587+00:00",
         "producedBy": {"deviceId": "4382", "name": "Thermostat"}},
    ]
    # Model's old first-six packet contained only these later readings.
    later = [
        {"name": "temperature", "value": "21.0" if i % 2 else "22.0",
         "date": f"2026-10-29T15:{10 + i//2:02d}:{10+i%2:02d}+00:00",
         "producedBy": {"deviceId": "4382", "name": "Thermostat"}}
        for i in range(24)
    ]
    return list(reversed(sorted(core+later, key=lambda e:e["date"])))


def coverage():
    return dated_incident_evidence(
        QUESTION, [history(3, thermostat_events(), device="4382")], ["4382"])


def test_clock_and_event_diversity_recover_the_actual_shutdown():
    result=coverage()
    assert result is not None
    assert result["material_event_count"] == 30
    assert result["material_event_selection"]["selection"] == (
        "question_clock_proximity_and_event_kind")
    events=result["material_event_examples"]
    assert any(e["name"] == "heatingSetpoint" and e["value"] == "26.0" for e in events)
    assert any(e["name"] == "heatingSetpoint" and e["value"] == "12.0" for e in events)
    assert any(e["name"] == "thermostatOperatingState"
               and e["value"] == "heating" for e in events)
    assert any(e["name"] == "thermostatOperatingState"
               and e["value"] == "idle" for e in events)
    assert any(e["name"] == "command-setHeatingSetpoint" for e in events)
    assert sum(e["name"] == "temperature" for e in events) <= 3
    assert events == sorted(events, key=lambda e:e["date"])
    assert result["incident_period"]["hub_timezone_verified"] is False
    assert clock_candidates(
        QUESTION,result["incident_period"])


def test_cited_hypothesis_uses_actual_operating_events_not_later_temperatures():
    source=coverage()
    picks=[{"read":e["read"],"name":e["name"],"date":e["date"]}
           for e in source["material_event_examples"]
           if e["name"] in ("heatingSetpoint","thermostatOperatingState")]
    assert len(picks)>=4
    proposal={
        "hypothesis":("The scheduler lowered the heating target and the "
                      "thermostat then reported idle; a controlled stop is likely."),
        "confidence":"possible",
        "supporting_events":picks[:4],
        "alternative":"The room demand may have changed for another reason.",
        "next_check":"Inspect room TRV observations and scheduler execution logs.",
    }
    result=verify_natural_hypothesis(proposal,coverage=source)
    assert result["accepted"] is True
    assert "controlled stop" in result["text"]
    assert result["root_cause_verified"] is False


def test_natural_fallback_produces_real_timeline_without_false_trv_root_cause():
    story=operational_sequence_brief(coverage(),"Thermostat")
    assert story is not None
    assert "Smart Thermostat Scheduler" in story["text"]
    assert "26.0°C to 12.0°C" in story["text"]
    assert "14:48" in story["text"] and "14:54" in story["text"]
    assert "rather than an unexplained" in story["text"]
    assert "which room thermostat or radiator" in story["text"]
    assert "4382" not in story["text"] and "3970" not in story["text"]
    assert story["cause_verified"] is False


def test_no_state_response_means_no_invented_controller_conclusion():
    rows=thermostat_events()
    rows=[e for e in rows if e["name"] != "thermostatOperatingState"]
    source=dated_incident_evidence(
        QUESTION,[history(3,rows,device="4382")],["4382"])
    assert operational_sequence_brief(source,"Thermostat") is None


def test_earlier_unrelated_day_not_promoted_to_incident():
    q="Why did heating stop at 2:54 pm on 24 October 2026?"
    src=dated_incident_evidence(
        q,[history(3,thermostat_events(),device="4382")],["4382"])
    assert src["material_event_count"] == 0
    assert operational_sequence_brief(src,"Thermostat") is None


@pytest.mark.asyncio
async def test_unstructured_model_output_still_answers_controlled_shutdown_naturally():
    mcp=FakeMCP([READ_EVENTS])
    async def identities():
        return [{"id":"4382","name":"AVATTO ME81H Thermostat",
                 "label":"Thermostat"}]
    mcp.get_device_identities=identities
    executor=FakeExecutor(mcp,[{"events":thermostat_events()}])
    step=0
    async def model(messages,tools):
        nonlocal step
        step+=1
        if step == 1:
            return {"tool_calls":[native("homebrain_find_device",{"name":"Thermostat"})]}
        if step == 2:
            return {"tool_calls":[native("hub_read_devices",{
                "tool":"hub_list_device_events","args":{"deviceId":"4382"}})]}
        assert step==3
        assert "user_incident_evidence_coverage" in messages[-1]["content"]
        assert "thermostatOperatingState" in messages[-1]["content"]
        return {"content":"The scheduler lowered the target and it stopped."}
    out=await run_native_read_agent(
        question=QUESTION,chat=model,mcp=mcp,executor=executor,
        max_rounds=4,max_reads=4,enable_model_reasoned_assessment=True)
    d=out["native_diagnostics"]
    assert d["model_reasoned_assessment"]["accepted"] is False
    assert d["concise_answer_source"]=="source_attested_operating_sequence"
    assert d["claim_publication"]["used_for_display_answer"] is False
    assert "26.0°C to 12.0°C" in out["answer"]["text"]
    assert "Evidence-based summary" not in out["answer"]["text"]
