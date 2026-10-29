"""Replay the 29 October room-list projection and full-inventory dead end.

The model chooses all operations. The host provides attested room names and
refuses unnecessary whole-hub inventory only after real room-source evidence.
No Hubitat or network access is required for the fake MCP experiment.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool
from investigation_v2.native_room_catalog import (
    source_room_catalog, question_room_matches,
)
from investigation_v2.native_read_agent import _payload, run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import (
    NAME, DEVICE, native,
)
from test_investigation_v2_room_evidence_0_18_221 import _room
from test_investigation_v2_entity_comparison_0_18_219 import _reads, _source


ROOM_TOOL = MCPTool(
    "hub_read_rooms", "Read source-verified rooms",
    {"type": "object", "properties": {
        "tool": {"type": "string",
                 "enum": ["hub_list_rooms", "hub_get_room"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]},
    annotations={"readOnlyHint": True},
)


def catalog():
    return {"count": 25,
            "rooms": [{"name": "Bathroom", "id": 3, "devices": [
                {"id": "999999", "label": "Unverified arbitrary member"}]}]
                     + [{"name": "Room " + str(n)} for n in range(24)]}


def test_real_rooms_field_is_preserved_but_member_ids_are_never_trusted():
    parsed = source_room_catalog(catalog())
    assert parsed["reported_room_count"] == 25
    assert parsed["returned_room_count"] == 25
    assert parsed["name_catalog_complete"] is True
    assert len(parsed["rooms"]) == 25
    assert parsed["room_membership_verified"] is False
    assert "999999" not in str(parsed)
    assert question_room_matches(
        "Which Bathroom lights are off?", parsed) == ["Bathroom"]
    assert question_room_matches("Check boiler controls", parsed) == []


def test_room_name_list_does_not_make_partial_or_malformed_data_complete():
    parsed = source_room_catalog({"count": 3, "rooms": [
        {"name": "Kitchen"}, {"name": "Kitchen"}, {"name": "Bathroom"},
    ]})
    assert parsed["name_catalog_complete"] is False
    assert parsed["rejected_room_rows"] == 1
    assert source_room_catalog({"count": 25}) is None
    assert source_room_catalog({"rooms": {"Bathroom": 1}}) is None
    assert source_room_catalog({"rooms": [{"id": "9000"}]})["rooms"] == []


def test_read_projection_no_longer_discards_room_names():
    class Source:
        data = catalog()
    projection = _payload(Source(), "hub_list_rooms")
    assert projection["rooms"][0] == "Bathroom"
    assert "rooms" not in projection.get("unmapped_source_fields", [])


@pytest.mark.asyncio
async def test_investigation_recovers_after_unbounded_inventory_proposal():
    rows = _reads()
    by_id = {row["source_data"]["id"]: row["source_data"] for row in rows}
    shower = _source(
        "8888", "Shower Light", ["Light", "Switch", "SwitchLevel"],
        {"switch": "off", "level": 25}, 8)["source_data"]
    ids = ["1079", "7746", "7754", "7818", "7821", "7851"]
    mcp = FakeMCP([DEVICE, ROOM_TOOL])
    async def identities():
        return [{"id": row["source_data"]["id"],
                 "label": row["source_data"]["label"]} for row in rows]
    mcp.get_device_identities = identities
    # Only 9 MCP READ results: room list, room detail, and 7 device states.
    executor = FakeExecutor(mcp,
        [catalog(), _room()] + [by_id[i] for i in ids] + [shower])
    calls = 0

    async def model(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"tool_calls": [native("hub_read_rooms", {
                "tool": "hub_list_rooms", "args": {}})]}
        if calls == 2:
            assert "verified_room_name_catalog" in messages[-1]["content"]
            assert "Bathroom" in messages[-1]["content"]
            # Replays the bad 0.18.222 model decision; host declines this
            # pointless broad source rather than calling it for 20 seconds.
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_devices", "args": {}})]}
        if calls == 3:
            assert "bounded_room_catalog_available" in messages[-1]["content"]
            return {"tool_calls": [native(NAME, {"name": "Bathroom"})]}
        if calls == 4:
            return {"tool_calls": [native("hub_read_rooms", {
                "tool": "hub_get_room", "args": {"room": "Bathroom"}})]}
        batches = [["1079", "7746"], ["7754", "7818"],
                   ["7821", "7851"], ["8888"]]
        if 5 <= calls <= 8:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_get_device",
                "args": {"deviceId": i, "mode": "summary"}})
                for i in batches[calls - 5]]}
        raise AssertionError("Complete group should not need final claim synthesis")

    result = await run_native_read_agent(
        question="Which Bathroom lights are off, and which other "
                 "lights belong to the actual Bathroom room? Read only.",
        chat=model, mcp=mcp, executor=executor,
        max_rounds=8, max_reads=12,
    )
    diagnostics = result["native_diagnostics"]
    assert calls == 8
    assert diagnostics["successful_reads"] == 9
    assert diagnostics["verified_room_name_catalogs"][0][
        "question_matched_rooms"] == ["Bathroom"]
    assert any(x["code"] == "bounded_room_catalog_available"
               for x in diagnostics["failures"])
    assert not diagnostics["timed_out_operations"]
    assert diagnostics["final_synthesis_skipped_reason"] == (
        "complete_verified_entity_group")
    assert diagnostics["entity_group_summary"]["room_membership_verified"] is True
    assert "Bathroom Light 1 and Bathroom Light 2 are both off" in (
        result["answer"]["text"])
    assert "Shower Light:** off" in result["answer"]["text"]
    assert not any(args.get("tool") == "hub_list_devices"
                   for _, args in executor.calls)
