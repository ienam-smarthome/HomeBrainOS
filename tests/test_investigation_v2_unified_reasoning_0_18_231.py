"""v0.18.231: model planning and answer reasoning are separate contracts.

The former 10k-token policy repeatedly ordered the model to produce fact IDs,
even when the experimental natural-reasoning synthesis expected evidence-linked
prose. No new model call should be needed if the loop already produced a
correct, exact-referenced hypothesis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_reasoning_policy import planning_system_prompt
from investigation_v2.native_incident_relevance import dated_incident_evidence
from investigation_v2.native_reasoned_assessment import verify_natural_hypothesis
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_incident_relevance_0_18_229 import (
    QUESTION, READ_EVENTS, history,
)
from test_investigation_v2_model_grounded_reasoning_0_18_230 import (
    model_proposal, real_overnight_events,
)
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def test_single_planning_policy_is_coherent_and_evidence_led():
    p = planning_system_prompt()
    assert 1800 <= len(p) < 4200
    assert "most likely" in p
    assert "Form at least two plausible explanations" in p
    assert "choose homebrain_request_main_ask" in p
    assert "rule action" in p
    assert "read-only" in p.lower()
    assert "claim-ID catalog" in p
    assert "return ONLY JSON" not in p
    assert "Choose IDs from source_claim_catalog" not in p
    assert "a historical OFF command" in p
    assert "underlying" not in p.lower()


def test_reasoning_evidence_includes_actual_values_and_attested_issuer():
    rows = [history(1, real_overnight_events())]
    c = dated_incident_evidence(QUESTION, rows, ["7805"])
    assert c is not None
    examples = c["material_event_examples"]
    assert examples[1]["name"] == "switch"
    assert examples[1]["value"] == "on"
    assert examples[1]["source_kind"] == "target_device"
    assert examples[1]["source_name"] == "Livingroom Light 1"
    assert examples[0]["source_kind"] == "issuing_app"
    assert examples[0]["source_name"] == "Button 1"


def test_heating_and_ventilation_evidence_use_same_reasoning_contract():
    question = "Why was heating on overnight 24–25 October 2026?"
    rows = [history(2, [
        {"name": "temperature", "value": 19.0,
         "date": "2026-10-24T20:40:00+01:00",
         "producedBy": {"deviceId": "3970", "name": "Hallway thermostat"}},
        {"name": "heatingSetpoint", "value": 22.0,
         "date": "2026-10-24T20:40:02+01:00",
         "producedBy": {"deviceId": "3970", "name": "Hallway thermostat"}},
    ], device="3970")]
    c = dated_incident_evidence(question, rows, ["3970"])
    assert c is not None and c["material_event_count"] == 2
    assert c["material_event_examples"][0]["value"] == "19"
    assert c["material_event_examples"][1]["value"] == "22"


def test_alternative_is_explicitly_possible_not_asserted_as_cause():
    p = model_proposal(alternative=(
        "A different automation may also have controlled the light."))
    r = verify_natural_hypothesis(p, coverage=dated_incident_evidence(
        QUESTION, [history(1, real_overnight_events())], ["7805"]))
    assert r["accepted"] is True
    assert "Another possibility" in r["text"]
    assert "Best next check" in r["text"]
    bad = model_proposal(alternative="It definitely proves app 999 caused it.")
    assert verify_natural_hypothesis(bad, coverage=dated_incident_evidence(
        QUESTION, [history(1, real_overnight_events())], ["7805"]))[
        "accepted"] is False


@pytest.mark.asyncio
async def test_no_extra_synthesis_after_model_already_wrote_verified_proposal():
    mcp = FakeMCP([READ_EVENTS])
    async def identities():
        return [{"id": "7805", "label": "Livingroom Light 1"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [{"events": real_overnight_events()}])
    step = 0

    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            assert "return ONLY JSON" not in messages[0]["content"]
            return {"tool_calls": [native(
                "homebrain_find_device", {"name": "Livingroom Light 1"})]}
        if step == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7805"}})]}
        if step == 3:
            assert tools
            return {"content": json.dumps(model_proposal(
                alternative="Another switch may have overridden the rule."))}
        raise AssertionError("Should reuse already source-anchored hypothesis")

    result = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=4, max_reads=3, enable_model_reasoned_assessment=True)
    assert step == 3
    d = result["native_diagnostics"]
    assert d["model_reasoned_assessment"]["accepted"] is True
    assert d["final_synthesis_ms"] == 0
    assert d["concise_answer_source"] == "model_cited_incident_assessment"
    assert "Another possibility" in result["answer"]["text"]
    assert "7805" not in result["answer"]["text"]


@pytest.mark.asyncio
async def test_plain_in_loop_text_gets_separate_cited_reasoning_contract():
    mcp = FakeMCP([READ_EVENTS])
    async def identities():
        return [{"id": "7805", "label": "Livingroom Light 1"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [{"events": real_overnight_events()}])
    step = 0

    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            return {"tool_calls": [native(
                "homebrain_find_device", {"name": "Livingroom Light 1"})]}
        if step == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7805"}})]}
        if step == 3:
            return {"content": "I think the button and motion controller interacted."}
        if step == 4:
            assert tools == []
            assert "supporting_events" in messages[0]["content"]
            assert "incident_evidence" in messages[1]["content"]
            assert "source_claim_catalog" not in messages[0]["content"]
            return {"content": json.dumps(model_proposal())}
        raise AssertionError("Unexpected extra inference")

    result = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=4, max_reads=3, enable_model_reasoned_assessment=True)
    assert step == 4
    assert result["native_diagnostics"]["model_reasoned_assessment"]["accepted"] is True
    assert result["answer"]["text"].startswith("**Possible explanation:**")
    assert "Evidence-based summary" not in result["answer"]["text"]
