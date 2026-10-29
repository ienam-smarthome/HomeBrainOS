"""Replay source-verified room-first answer from the 29 October live test.

The test does not infer sensors from labels or grant missing device states.
It verifies that the displayed conclusion and the independent claim-selection
diagnostic are correctly distinguished without modifying V2 READ execution.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.native_room_evidence import (
    natural_entity_answer, verified_room_inventory,
)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_entity_lookup_0_18_184 import (
    DEVICE, native,
)
from test_investigation_v2_room_source_frontier_0_18_223 import ROOM_TOOL
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor,
)
from test_investigation_v2_entity_comparison_0_18_219 import _source


MEMBERS = [
    ("7746", "Bathroom Hi-P sensor"),
    ("7818", "Bathroom Light 1"),
    ("7821", "Bathroom Light 2"),
    ("7754", "Bathroom Soft Sensor"),
    ("7896", "Matter LWR01 Bathroom Illuminance"),
    ("7895", "Matter LWR01 Bathroom Occupancy"),
    ("7807", "Shower Light"),
    ("7908", "Shower MS605"),
]


def room():
    return {"id": 98, "name": "Bathroom",
            "deviceCount": len(MEMBERS),
            "devices": [{"id": ident, "label": label}
                        for ident, label in MEMBERS]}


def light(ident, label, level, read):
    return _source(ident, label, ["Light", "Switch", "SwitchLevel"],
                   {"switch": "off", "level": level}, read)


def evidence():
    return [
        light("7818", "Bathroom Light 1", 60, 3),
        light("7821", "Bathroom Light 2", 60, 4),
        light("7807", "Shower Light", 70, 5),
    ]


def test_room_first_answer_lists_each_checked_light_once():
    result = natural_entity_answer(
        [], evidence(), [verified_room_inventory(room(), "Bathroom", read=2)])
    assert result is not None
    assert result["room_only_count"] == 0
    assert result["room_unread_count"] == 5
    assert result["verified_device_read_count"] == 3
    text = result["text"]
    for label in ("Bathroom Light 1", "Bathroom Light 2", "Shower Light"):
        assert text.count(f"**{label}:**") == 1
    assert "Other devices in this room" not in text
    assert "Additional room members" not in text
    assert "**Coverage:** 5 other room member(s)" in text
    assert "capabilities and current states have not been verified" in text
    assert "off" in text
    assert "Bathroom Hi-P sensor" not in text


def test_name_first_group_still_includes_separately_verified_room_only_light():
    from test_investigation_v2_entity_comparison_0_18_219 import _lookup, _reads
    from test_investigation_v2_room_evidence_0_18_221 import _room
    result = natural_entity_answer(
        _lookup(), _reads() + [
            light("8888", "Shower Light", 70, 8)],
        [verified_room_inventory(_room(), "Bathroom", read=7)],
    )
    assert result is not None
    assert result["room_only_count"] > 0
    assert "Additional room members not matched by name" in result["text"]
    assert result["text"].count("**Shower Light:**") == 1


@pytest.mark.asyncio
async def test_live_shaped_room_answer_has_separate_authority_and_no_extra_reads():
    mcp = FakeMCP([ROOM_TOOL, DEVICE])
    responses = [
        {"count": 25, "rooms": [{"name": "Bathroom"}] +
         [{"name": f"Other {n}"} for n in range(24)]},
        room(),
        *[row["source_data"] for row in evidence()],
    ]
    executor = FakeExecutor(mcp, responses)
    count = 0
    async def model(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return {"tool_calls": [native("hub_read_rooms", {
                "tool": "hub_list_rooms", "args": {}})]}
        if count == 2:
            return {"tool_calls": [native("hub_read_rooms", {
                "tool": "hub_get_room", "args": {"room": "Bathroom"}})]}
        if count in (3, 4, 5):
            id_ = ("7818", "7821", "7807")[count-3]
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_get_device",
                "args": {"deviceId": id_, "mode": "summary"}})]}
        return {"content": '{"claims":[]}'}

    result = await run_native_read_agent(
        question="Which Bathroom lights are off? Include actual Bathroom "
                 "room lights without Bathroom in their names. Read only.",
        chat=model, mcp=mcp, executor=executor, max_rounds=6)
    assert count == 6
    d = result["native_diagnostics"]
    assert d["successful_reads"] == 5
    assert d["verified_room_name_catalogs"][0]["question_matched_rooms"] == ["Bathroom"]
    assert d["concise_answer_source"] == "verified_entity_group_comparison"
    assert d["entity_group_summary"]["room_unread_count"] == 5
    assert d["entity_group_summary"]["room_only_count"] == 0
    assert d["claim_publication"]["used_for_display_answer"] is False
    assert result["answer"]["validation_issues"] == [
        "source_verified_room_and_device_readings",
        "some_room_member_states_unread",
    ]
    assert result["answer"]["text"].count("**Shower Light:**") == 1
    assert "Source-verified findings" in result["report"]["text"]
    assert len(executor.calls) == 5
    assert all(args.get("tool") != "hub_list_devices"
               for _, args in executor.calls)
