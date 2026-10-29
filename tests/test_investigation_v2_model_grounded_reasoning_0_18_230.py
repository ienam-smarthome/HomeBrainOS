"""v0.18.230: model reasons in prose, citations remain host-attested.

This is not a claim to full semantic entailment. Accept only a *possible*
model interpretation anchored to exact device-scoped events in the user's
historical window. Invented reads, times, numbers and confident physical
causation remain unpublishable. Existing READ-only permission gate is kept.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_incident_relevance import dated_incident_evidence
from investigation_v2.native_reasoned_assessment import (
    candidate_prompt, verify_natural_hypothesis,
)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_incident_relevance_0_18_229 import (
    QUESTION, READ_EVENTS, history,
)
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor


def real_overnight_events():
    return [
        {"name": "command-on", "date": "2026-10-24T19:00:00+01:00",
         "producedBy": {"appId": "1251", "name": "Button 1"}},
        {"name": "switch", "value": "on",
         "date": "2026-10-24T19:00:01+01:00",
         "producedBy": {"deviceId": "7805", "name": "Livingroom Light 1"}},
        {"name": "command-setLevel", "date": "2026-10-24T23:00:00+01:00",
         "producedBy": {"appId": "4019", "name": "Light Mode Controller"}},
    ]


def source_coverage():
    return dated_incident_evidence(
        QUESTION, [history(1, real_overnight_events())], ["7805"])


def model_proposal(events=None, **changes):
    rows = events or source_coverage()["material_event_examples"]
    return {
        "hypothesis": (
            "The light might have stayed on because a button activated "
            "it and the automation later adjusted brightness."),
        "confidence": "possible",
        "supporting_events": rows[:2],
        "next_check": (
            "Review the controller's actual inactive-timer decisions."),
        **changes,
    }


def test_two_exact_historical_source_events_admit_tentative_natural_answer():
    receipt = verify_natural_hypothesis(
        model_proposal(), coverage=source_coverage(),
        observed_source_names=[QUESTION])
    assert receipt["accepted"] is True
    assert receipt["text"].startswith("**Possible explanation:**")
    assert "Livingroom" not in receipt["text"] or "7805" not in receipt["text"]
    assert receipt["model_prose_published"] is True
    assert receipt["semantic_entailment_verified"] is False
    assert receipt["root_cause_verified"] is False
    assert receipt["supporting_events"][0]["read"] == 1
    assert "technical" not in receipt["text"].lower()
    assert "Source-verified findings" not in receipt["text"]


@pytest.mark.parametrize("change,reason", [
    ({"confidence": "confirmed"}, "unsupported_confidence"),
    ({"hypothesis": "It definitely broke when the timer failed."},
     "overconfident_or_unbounded_explanation"),
    ({"hypothesis": "The light used 9999W because the rule triggered."},
     "unsupported_numeric_detail"),
    ({"supporting_events": [
        {"read": 99, "name": "switch", "date": "2026-10-24T19:00:01+01:00"},
        {"read": 1, "name": "command-on", "date": "2026-10-24T19:00:00+01:00"},
    ]}, "event_not_in_verified_incident_window"),
    ({"supporting_events": [
        {"read": 1, "name": "command-on", "date": "2026-10-24T19:00:00+01:00"},
        {"read": 1, "name": "command-on", "date": "2026-10-24T19:00:00+01:00"},
    ]}, "duplicate_event_anchor"),
])
def test_reject_model_overreach_invalid_source_and_fabricated_numbers(change, reason):
    result = verify_natural_hypothesis(
        model_proposal(**change), coverage=source_coverage(),
        observed_source_names=[QUESTION])
    assert result["accepted"] is False
    assert result["reason"] == reason


def test_wrong_date_or_no_verified_events_never_publishes_model_story():
    empty = dated_incident_evidence(
        QUESTION, [history(2, [{
            "name": "command-on", "date": "2026-10-29T20:00:00+00:00",
            "producedBy": {"appId": "1251", "name": "Button"},
        }])], ["7805"])
    result = verify_natural_hypothesis(model_proposal(), coverage=empty)
    assert result["accepted"] is False
    assert result["reason"] == "no_relevant_dated_incident_events"
    assert verify_natural_hypothesis(model_proposal(), coverage=None)[
        "model_prose_published"] is False


@pytest.mark.asyncio
async def test_native_v2_uses_one_final_model_pass_for_source_anchored_reasoning():
    mcp = FakeMCP([READ_EVENTS])
    async def identities():
        return [{"id": "7805", "name": "Hue Matter Light",
                 "label": "Livingroom Light 1"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [{"events": real_overnight_events()}])
    count = 0
    async def model(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"tool_calls": [native(
                "homebrain_find_device", {"name": "Livingroom Light 1"})]}
        if count == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7805"}})]}
        assert tools == []
        assert "incident_evidence" in messages[1]["content"]
        assert "supporting_events" in messages[0]["content"]
        return {"content": json.dumps(model_proposal())}
    answer = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=2, max_reads=3, enable_model_reasoned_assessment=True)
    d = answer["native_diagnostics"]
    assert len(executor.calls) == 1
    assert count == 3
    assert d["model_reasoned_assessment"]["accepted"] is True
    assert d["claim_publication"]["model_prose_published"] is True
    assert d["concise_answer_source"] == "model_cited_incident_assessment"
    assert answer["answer"]["text"].startswith("**Possible explanation:**")
    assert "7805" not in answer["answer"]["text"]
    assert answer["answer"]["root_cause_verified"] is False


@pytest.mark.asyncio
async def test_unanchored_model_story_falls_back_to_source_not_hallucination():
    mcp = FakeMCP([READ_EVENTS])
    async def identities():
        return [{"id": "7805", "label": "Livingroom Light 1"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [{"events": real_overnight_events()}])
    count = 0
    async def model(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"tool_calls": [native(
                "homebrain_find_device", {"name": "Livingroom Light 1"})]}
        if count == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7805"}})]}
        return {"content": json.dumps(model_proposal(
            supporting_events=[
                {"read": 9, "name": "switch",
                 "date": "2026-10-24T19:00:01+01:00"},
                {"read": 10, "name": "command-on",
                 "date": "2026-10-24T19:00:00+01:00"},
            ]))}
    result = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=2, max_reads=3, enable_model_reasoned_assessment=True)
    assert result["native_diagnostics"]["model_reasoned_assessment"][
        "accepted"] is False
    assert result["native_diagnostics"]["claim_publication"][
        "model_prose_published"] is False
    assert "button activated it" not in result["answer"]["text"]
