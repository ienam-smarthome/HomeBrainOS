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
from investigation_v2.native_event_narrative import event_narrative_evidence, event_timeline_fallback
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeExecutor, FakeMCP
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_complete_interval_0_18_236 import READ as EVENT_TOOL
from test_investigation_v2_event_narrative_0_18_238 import histories, witnessed, candidate, ev


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


def test_real_30_oct_window_preserves_button_off_and_bridge_state_pairs():
    """Full-style mixed-day events should not displace the requested timeline."""
    case = [
        {"read": 2, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7818"},
         "source_data": {"events": [
             ev("switch", "2026-10-29T23:55:00.000+0000", "off", device="7790"),
             ev("switch", "2026-10-30T02:52:44.099+0000", "on", device="7790"),
             ev("command-off", "2026-10-30T03:04:16.978+0000", app="1568"),
             ev("switch", "2026-10-30T03:04:18.218+0000", "off", device="7790"),
             ev("switch", "2026-10-30T03:40:21.668+0000", "on", device="7790"),
             ev("command-off", "2026-10-30T03:46:05.251+0000", app="1569"),
             ev("switch", "2026-10-30T03:46:05.928+0000", "off", device="7790"),
             ev("switch", "2026-10-30T07:12:33.514+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T07:12:33.560+0000", app="4013"),
             ev("level", "2026-10-30T07:12:34.528+0000", "30", device="7790"),
             ev("command-setLevel", "2026-10-30T07:15:02.678+0000", app="4013"),
             ev("level", "2026-10-30T07:15:03.071+0000", "50", device="7790"),
             ev("command-off", "2026-10-30T07:44:16.182+0000", app="1569"),
         ]}},
        {"read": 3, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7821"},
         "source_data": {"events": [
             ev("switch", "2026-10-30T02:52:45.141+0000", "on", device="7790"),
             ev("command-off", "2026-10-30T03:04:16.993+0000", app="1568"),
             ev("switch", "2026-10-30T03:04:18.278+0000", "off", device="7790"),
             ev("switch", "2026-10-30T03:40:22.678+0000", "on", device="7790"),
             ev("command-off", "2026-10-30T03:46:05.313+0000", app="1569"),
             ev("switch", "2026-10-30T03:46:06.059+0000", "off", device="7790"),
             ev("switch", "2026-10-30T07:12:34.589+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T07:12:34.622+0000", app="4013"),
             ev("level", "2026-10-30T07:12:35.546+0000", "30", device="7790"),
             ev("command-off", "2026-10-30T07:44:16.196+0000", app="1569"),
         ]}},
        {"read": 4, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7807"},
         "source_data": {"events": [
             ev("switch", "2026-10-30T02:13:30.399+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T02:13:30.481+0000", app="4014"),
             ev("command-setLevel", "2026-10-30T02:13:30.699+0000", app="4014"),
             ev("level", "2026-10-30T02:13:31.416+0000", "40", device="7790"),
             ev("switch", "2026-10-30T02:15:13.073+0000", "off", device="7790"),
             ev("switch", "2026-10-30T03:03:31.727+0000", "on", device="7790"),
             ev("command-off", "2026-10-30T03:04:17.010+0000", app="1568"),
             ev("switch", "2026-10-30T03:04:17.212+0000", "off", device="7790"),
             ev("command-off", "2026-10-30T03:46:05.333+0000", app="1569"),
             ev("switch", "2026-10-30T07:27:48.079+0000", "on", device="7790"),
             ev("command-setLevel", "2026-10-30T07:27:48.148+0000", app="4014"),
             ev("level", "2026-10-30T07:27:49.070+0000", "70", device="7790"),
             ev("command-off", "2026-10-30T07:44:16.213+0000", app="1569"),
         ]}},
    ]
    packet = event_narrative_evidence(case, IDS, question=QUESTION)
    assert packet is not None
    assert packet["explicit_calendar_scope_applied"] is True
    assert packet["explicit_clock_scope_applied"] is True
    events = packet["event_examples"]
    assert set(packet["device_read_ids"]) == set(IDS)
    assert all(e["date"].startswith("2026-10-30T") for e in events)
    assert all("07:44:" not in e["date"] for e in events)
    assert len(events) <= 36
    for ident in IDS:
        assert any(e["device_id"] == ident and e["name"] == "command-off"
                   and "T03:04:" in e["date"] for e in events)
        assert any(e["device_id"] == ident and e["name"] == "switch"
                   and e.get("value") == "off"
                   and "T03:04:" in e["date"] for e in events)
    assert any(e["device_id"] == "7818" and e.get("value") == "30"
               and "T07:12:" in e["date"] for e in events)
    assert any(e["device_id"] == "7807" and e.get("value") == "40"
               and "T02:13:" in e["date"] for e in events)
    fallback = event_timeline_fallback(packet)
    assert "03:04:" in fallback
    assert "07:12:" in fallback
    assert "07:44:" not in fallback
    assert "issued 9 recorded commands" not in fallback
