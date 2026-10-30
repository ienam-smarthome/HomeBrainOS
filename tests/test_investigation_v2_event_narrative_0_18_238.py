"""v0.18.238: AI-authored room/device event history, not command-count fallback.

The fixture replays the source-reported 30 Oct Bathroom sequence with the
same room and event READ tools as the live failure. It checks exact event
anchors, natural language, source limits and adversarial rejection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_event_narrative import (
    event_narrative_evidence, verify_event_narrative,
    event_timeline_fallback, narrative_system_prompt,
)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import DEVICE, native
from test_investigation_v2_room_source_frontier_0_18_223 import ROOM_TOOL


def ev(name, time, value=None, app=None, device=None):
    row = {"name": name, "date": time}
    if value is not None:
        row["value"] = value
    if app:
        row["producedBy"] = {"appId": app, "name": "Bathroom (Lights On)"}
    elif device:
        row["producedBy"] = {"deviceId": device, "name": "Matter Hue Bridge Pro"}
    return row


def room():
    return {"id": 98, "name": "Bathroom", "deviceCount": 3,
            "devices": [
                {"id": "7818", "label": "Bathroom Light 1"},
                {"id": "7821", "label": "Bathroom Light 2"},
                {"id": "7807", "label": "Shower Light"},
            ]}


def histories():
    return [
        {"events": [
            ev("switch", "2026-10-30T07:12:33.514+0000", "on", device="7790"),
            ev("command-setLevel", "2026-10-30T07:12:33.560+0000", app="4013"),
            ev("level", "2026-10-30T07:12:34.528+0000", "30", device="7790"),
            ev("command-setLevel", "2026-10-30T07:15:02.678+0000", app="4013"),
            ev("level", "2026-10-30T07:15:03.071+0000", "50", device="7790"),
        ]},
        {"events": [
            ev("switch", "2026-10-30T07:12:34.589+0000", "on", device="7790"),
            ev("command-setLevel", "2026-10-30T07:12:34.622+0000", app="4013"),
            ev("level", "2026-10-30T07:12:35.546+0000", "30", device="7790"),
        ]},
        {"events": [
            ev("command-setLevel", "2026-10-30T02:13:30.481+0000", app="4014"),
            ev("level", "2026-10-30T02:13:31.416+0000", "40", device="7790"),
        ]},
    ]


def witnessed():
    return [{"read": 2, "operation": "hub_get_room",
             "source_data": room()}] + [
        {"read": i + 3, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": device_id},
         "source_data": data}
        for i, (device_id, data) in enumerate(
            zip(("7818", "7821", "7807"), histories()))
    ]


def event_ref(packet, device_id, name, clock):
    e = next(e for e in packet["event_examples"]
             if e["device_id"] == device_id and e["name"] == name
             and f"T{clock}" in e["date"])
    return {key: e[key] for key in ("read", "device_id", "name", "date")}


def candidate(packet):
    return {
        "answer": ("Bathroom Lights 1 and 2 reported ON around 07:12, "
                   "followed by brightness commands from Bathroom (Lights On)."),
        "breakdown": [
            {"text": "Bathroom Light 1 reported ON at 07:12.",
             "supporting_events": [
                 event_ref(packet, "7818", "switch", "07:12")]},
            {"text": "Bathroom Light 2 reported ON at 07:12.",
             "supporting_events": [
                 event_ref(packet, "7821", "switch", "07:12")]},
            {"text": "Bathroom Light 1 subsequently reported brightness 50 at 07:15.",
             "supporting_events": [
                 event_ref(packet, "7818", "level", "07:15")]},
        ],
        "uncertainty": ("The room's input sensor histories and controller "
                        "decision logs were not read, so the initiating "
                        "trigger remains unverified."),
    }


def test_multi_device_event_packet_respects_source_room_membership():
    case = witnessed()
    packet = event_narrative_evidence(case, [])
    assert packet
    assert set(packet["device_read_ids"]) == {"7818", "7821", "7807"}
    assert "Bathroom Light 1" in {e["device_name"] for e in packet["event_examples"]}
    assert len(packet["event_examples"]) >= 7
    assert event_narrative_evidence(case[1:], []) is None
    assert packet["physical_state_independently_verified"] is False
    assert "source" in narrative_system_prompt().lower()


def test_multi_device_narrative_is_model_authored_and_cites_exact_events():
    packet = event_narrative_evidence(witnessed(), [])
    result = verify_event_narrative(candidate(packet), packet=packet,
                                    question="Investigate Bathroom lights")
    assert result["accepted"] is True
    assert result["model_prose_published"] is True
    assert result["supporting_event_count"] == 3
    assert "Bathroom Lights 1 and 2 reported ON" in result["text"]
    assert "Read #3" in result["text"]
    assert "Read #4" in result["text"]
    assert "trigger remains unverified" in result["text"]
    assert "recorded commands" not in result["text"]


@pytest.mark.parametrize("mutator,reason", [
    (lambda x: x["breakdown"][0]["supporting_events"][0].update(
        {"device_id": "9999"}), "event_not_in_attested_scoped_history"),
    (lambda x: x["breakdown"][0].update(
        {"text": "Bathroom Light 1 reported brightness 9999 at 07:12."}),
     "unsupported_breakdown_detail"),
    (lambda x: x.update({"answer": "The motion sensor caused the bathroom lights to turn on."}),
     "invalid_narrative_parts"),
    (lambda x: x["breakdown"][0].update({"supporting_events": []}),
     "invalid_breakdown_sources"),
    (lambda x: x["breakdown"][0].update(
        {"text": "Bathroom Light 1 reported OFF at 07:12."}),
     "contradicted_reported_switch_state"),
])
def test_fabricated_refs_values_and_certain_causation_never_publish(mutator, reason):
    packet = event_narrative_evidence(witnessed(), [])
    proposal = candidate(packet)
    mutator(proposal)
    result = verify_event_narrative(proposal, packet=packet,
                                    question="Investigate Bathroom lights")
    assert result["accepted"] is False
    assert result["reason"] == reason
    assert result["model_prose_published"] is False


def test_malformed_source_arrays_are_treated_as_unusable_not_truth():
    case = witnessed()
    case[0]["source_data"]["devices"] = None
    assert event_narrative_evidence(case, []) is None
    case = witnessed()
    case[1]["source_data"]["events"] = None
    packet = event_narrative_evidence(case, [])
    assert packet is not None
    assert set(packet["device_read_ids"]) == {"7818", "7821", "7807"}


def test_when_ai_invalid_fallback_is_chronology_not_command_counts():
    packet = event_narrative_evidence(witnessed(), [])
    text = event_timeline_fallback(packet)
    assert "Bathroom Light" in text
    assert "reported switch=on" in text
    assert "Read #" in text
    assert "issued setLevel" in text
    assert "issued 2 recorded commands" not in text
    assert "remains uncertain" in text


@pytest.mark.asyncio
async def test_native_room_history_invokes_model_final_reasons_not_claim_catalog():
    mcp = FakeMCP([ROOM_TOOL, DEVICE])
    executor = FakeExecutor(mcp, [
        {"count": 1, "rooms": [{"name": "Bathroom"}]},
        room(), *histories()])
    turns = 0

    async def model(messages, tools):
        nonlocal turns
        turns += 1
        if turns == 1:
            return {"tool_calls": [native("hub_read_rooms", {
                "tool": "hub_list_rooms", "args": {}})]}
        if turns == 2:
            return {"tool_calls": [native("hub_read_rooms", {
                "tool": "hub_get_room", "args": {"room": "Bathroom"}})]}
        if 3 <= turns <= 5:
            ident = ("7818", "7821", "7807")[turns - 3]
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events", "args": {"deviceId": ident}})]}
        if turns == 6:
            return {"content": "The controller issued brightness commands but the trigger is not known."}
        if turns == 7:
            assert tools == []
            assert "final reasoning stage" in messages[0]["content"]
            context = json.loads(messages[-1]["content"])
            assert "event_examples" in context["event_evidence"]
            assert context["source_claim_catalog"] == []
            return {"content": json.dumps(candidate(context["event_evidence"]))}
        raise AssertionError("Unexpected unnecessary model call")

    result = await run_native_read_agent(
        question="Investigate the Bathroom lighting behaviour this morning.",
        chat=model, mcp=mcp, executor=executor,
        max_rounds=7, max_reads=6,
        enable_model_reasoned_assessment=True)
    d = result["native_diagnostics"]
    assert turns == 7
    assert d["successful_reads"] == 5
    assert d["event_narrative_eligible"] is True
    assert d["model_event_narrative"]["accepted"] is True
    assert d["claim_publication"]["used_for_display_answer"] is False
    assert d["claim_publication"]["model_prose_published"] is True
    assert d["concise_answer_source"] == "model_scoped_event_narrative"
    assert "Evidence and timeline" in result["answer"]["text"]
    assert "Source-verified findings" not in result["answer"]["text"]
    assert len(executor.calls) == 5
