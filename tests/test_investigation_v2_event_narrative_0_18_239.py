"""v0.18.239: replay live named-device Bathroom history from 30 October 2026.

The 0.18.238 regression only exercised room membership (focus_ids=[]).
Real live V2 resolved three independently named devices first, so focus_ids
contained three IDs and mistakenly disabled source-attested narrative output.
These tests reproduce both end-of-round-budget and model-finished paths.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_entity_lookup import NAME
from investigation_v2.native_event_narrative import event_narrative_evidence
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeExecutor, FakeMCP
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_complete_interval_0_18_236 import READ as EVENT_TOOL
from test_investigation_v2_event_narrative_0_18_238 import histories, witnessed, candidate


IDS = ("7818", "7821", "7807")
NAMES = ("Bathroom Light 1", "Bathroom Light 2", "Shower Light")
QUESTION = (
    "Investigate why Bathroom Light 1, Bathroom Light 2 and Shower Light "
    "turned ON and OFF between 02:00 and 07:30 on 30 October 2026. "
    "Reconstruct their chronological sequence and explain what triggered "
    "each change, what was verified, and what remains unverified. "
    "Do not change anything."
)


def test_named_device_id_focus_is_valid_attested_scope_for_two_or_more_histories():
    scoped = witnessed()[1:]
    packet = event_narrative_evidence(scoped, IDS)
    assert packet is not None
    assert set(packet["device_read_ids"]) == set(IDS)
    assert len(packet["event_examples"]) >= 3
    assert event_narrative_evidence(scoped[:1], IDS) is not None
    assert event_narrative_evidence(scoped, ("9999",)) is None
    assert event_narrative_evidence(scoped, ()) is None
    # A source-attributed command must never grant an unrelated device ID.
    assert set(packet["device_read_ids"]) == set(IDS)


@pytest.mark.asyncio
@pytest.mark.parametrize("model_ending", ["budget_valid", "budget_unstructured",
                                           "finished_valid"])
async def test_live_three_named_device_lookup_uses_narrative_not_catalog(model_ending):
    mcp = FakeMCP([EVENT_TOOL])
    async def complete_verified_identities():
        return [{"id": id_, "label": name} for id_, name in zip(IDS, NAMES)]
    mcp.get_device_identities = complete_verified_identities
    executor = FakeExecutor(mcp, histories())
    turns = 0

    async def model(messages, tools):
        nonlocal turns
        turns += 1
        if turns <= 3:
            return {"tool_calls": [native(NAME, {"name": NAMES[turns - 1]})]}
        if turns <= 6:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": IDS[turns - 4], "limit": 100},
            })]}
        if model_ending == "finished_valid" and turns == 7:
            return {"content": "The controller changed brightness, but the trigger is unknown."}
        assert tools == [], "final inference must be tools-free"
        assert messages[0]["role"] == "system"
        assert "final reasoning stage" in messages[0]["content"]
        context = json.loads(messages[-1]["content"])
        packet = context["event_evidence"]
        assert set(packet["device_read_ids"]) == set(IDS)
        assert context["source_claim_catalog"] == []
        if model_ending == "budget_unstructured":
            return {"content": "A motion sensor definitely caused the lights."}
        return {"content": json.dumps(candidate(packet))}

    result = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=7 if model_ending == "finished_valid" else 6,
        max_reads=7, enable_model_reasoned_assessment=True,
    )
    diagnostics = result["native_diagnostics"]
    assert diagnostics["event_narrative_eligible"] is True, diagnostics
    assert diagnostics["event_narrative_blockers"] == [], diagnostics
    assert diagnostics["successful_reads"] == 3, diagnostics
    assert set(diagnostics["focus_ids"]) == set(IDS), diagnostics
    assert len(diagnostics["named_identity_lookups"]) == 3, diagnostics
    assert diagnostics["claim_publication"]["used_for_display_answer"] is False
    assert diagnostics["source_grounded_brief_published"] is False
    assert len(executor.calls) == 3
    assert all(x[0] == "hub_read_devices" for x in executor.calls)
    assert all(x["status"] == "unique"
               for x in diagnostics["named_identity_lookups"])
    assert not diagnostics["final_synthesis_skipped_reason"]
    if model_ending == "budget_unstructured":
        assert diagnostics["model_event_narrative"]["accepted"] is False
        assert diagnostics["concise_answer_source"] == (
            "source_attested_event_timeline_fallback")
        assert "What the returned history shows" in result["answer"]["text"]
        assert "A motion sensor definitely caused" not in result["answer"]["text"]
    else:
        assert diagnostics["model_event_narrative"]["accepted"] is True
        assert diagnostics["concise_answer_source"] == (
            "model_scoped_event_narrative")
        assert "Evidence and timeline" in result["answer"]["text"]
    assert "issued 9 recorded commands" not in result["answer"]["text"]
    assert "Source-verified findings" not in result["answer"]["text"]


@pytest.mark.asyncio
async def test_one_named_device_history_still_uses_existing_focused_path():
    mcp = FakeMCP([EVENT_TOOL])
    async def complete_verified_identities():
        return [{"id": "7818", "label": "Bathroom Light 1"}]
    mcp.get_device_identities = complete_verified_identities
    executor = FakeExecutor(mcp, histories()[:1])
    count = 0

    async def model(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"tool_calls": [native(NAME, {"name": "Bathroom Light 1"})]}
        if count == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events", "args": {"deviceId": "7818"},
            })]}
        return {"content": "The starting sensor is not established by this event sample."}

    result = await run_native_read_agent(
        question="Inspect Bathroom Light 1 switch history.",
        chat=model, mcp=mcp, executor=executor,
        max_rounds=4, max_reads=2,
    )
    diag = result["native_diagnostics"]
    assert diag["event_narrative_eligible"] is False
    assert "fewer_than_two_device_event_reads" in diag["event_narrative_blockers"]
    assert len(executor.calls) == 1
