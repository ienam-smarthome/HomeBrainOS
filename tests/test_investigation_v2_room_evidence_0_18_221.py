"""0.18.221: source-attested room membership and natural-language answers."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool
from investigation_v2.native_room_evidence import (
    verified_room_inventory, natural_entity_answer)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import FakeMCP, FakeExecutor
from test_investigation_v2_native_entity_lookup_0_18_184 import NAME, DEVICE, native
from test_investigation_v2_entity_comparison_0_18_219 import _lookup, _reads, _source


ROOM_TOOL = MCPTool(
    "hub_read_rooms", "Read Hubitat rooms",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_get_room"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]},
    annotations={"readOnlyHint": True},
)


def _room(name="Bathroom"):
    names = {x["source_data"]["id"]: x["source_data"]["label"]
             for x in _reads()}
    names["8888"] = "Shower Light"
    members = [{"id": ident, "label": label} for ident, label in names.items()
               if ident not in ("1079", "7851")]
    return {"id": 3, "name": name, "deviceCount": len(members),
            "devices": members}


def test_room_requires_exact_source_identity_and_explicit_members():
    source = _room()
    found = verified_room_inventory(source, "Bathroom", read=2)
    assert found["inventory_complete"] is True
    assert "8888" in found["member_ids"]
    assert "1079" not in found["member_ids"]
    assert verified_room_inventory(source, "Kitchen", read=2) is None
    assert verified_room_inventory({"name": "Bathroom"}, "Bathroom", read=2) is None
    assert verified_room_inventory({
        "name": "Bathroom", "deviceCount": 2,
        "devices": [{"id": 1}, {"id": 1}],
    }, "Bathroom", read=2) is None
    partial = {**source, "deviceCount": 999}
    assert not verified_room_inventory(partial, "Bathroom", read=2)["inventory_complete"]


def test_natural_answer_includes_shower_light_only_when_individually_read():
    rows = _reads()
    shower = _source("8888", "Shower Light", ["Light", "Switch", "SwitchLevel"],
                     {"switch": "off", "level": 25}, 8)
    room = verified_room_inventory(_room(), "Bathroom", read=7)
    out = natural_entity_answer(_lookup(), rows + [shower], [room])
    assert out["room_membership_verified"] is True
    assert out["room_unread_count"] == 0
    assert out["room_only_count"] >= 1
    assert "Bathroom Light 1 and Bathroom Light 2 are both off" in out["text"]
    assert "**Shower Light:** off" in out["text"]
    assert "saved dimmer level 25%" in out["text"]
    assert "Bathroom Button" in out["text"]
    assert "not listed in the Bathroom room" in out["text"]
    assert "switch=off" not in out["text"]
    assert len(out["evidence_reads"]) == 8


def test_unread_room_member_gets_no_invented_switch_state():
    room = verified_room_inventory(_room(), "Bathroom", read=7)
    out = natural_entity_answer(_lookup(), _reads(), [room])
    assert out["room_unread_count"] == 1
    assert "Shower Light" in out["text"]
    assert "**Not yet checked:**" in out["text"]
    assert "**Shower Light:** off" not in out["text"]


def test_name_only_group_is_natural_and_does_not_claim_room_membership():
    out = natural_entity_answer(_lookup(), _reads())
    assert "are both off" in out["text"]
    assert "saved dimmer level 60%" in out["text"]
    assert "Room membership is not verified" in out["text"]
    assert out["matched_light_count"] == 2
    assert out["room_unread_count"] == 0


@pytest.mark.asyncio
async def test_live_selected_room_read_authorises_only_exact_room_member():
    rows = _reads()
    by_id = {row["source_data"]["id"]: row["source_data"] for row in rows}
    shower = _source("8888", "Shower Light", ["Light", "Switch", "SwitchLevel"],
                     {"switch": "off", "level": 25}, 8)["source_data"]
    order = ["1079", "7746", "7754", "7818", "7821", "7851"]
    mcp = FakeMCP([DEVICE, ROOM_TOOL])
    async def identities():
        return [{"id": row["source_data"]["id"],
                 "label": row["source_data"]["label"]} for row in rows]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [_room()] + [by_id[i] for i in order] + [shower])
    turns = 0

    async def model(messages, tools):
        nonlocal turns
        turns += 1
        if turns == 1:
            return {"tool_calls": [native(NAME, {"name": "Bathroom"})]}
        if turns == 2:
            return {"tool_calls": [
                native("hub_read_rooms", {"tool": "hub_get_room",
                                           "args": {"room": "Bathroom"}})]}
        batches = [["1079", "7746"], ["7754", "7818"],
                   ["7821", "7851"], ["8888"]]
        if 3 <= turns <= 6:
            return {"tool_calls": [
                native("hub_read_devices", {
                    "tool": "hub_get_device",
                    "args": {"deviceId": i, "mode": "summary"}})
                for i in batches[turns - 3]]}
        raise AssertionError("Complete verified room must skip final model call")

    result = await run_native_read_agent(
        question="Investigate all Bathroom-named devices, and check which "
                 "lights are actually assigned to the Bathroom room.",
        chat=model, mcp=mcp, executor=executor,
        max_rounds=6, max_reads=9)
    d = result["native_diagnostics"]
    assert turns == 6
    assert d["successful_reads"] == 8
    assert d["verified_room_inventories"][0]["name"] == "Bathroom"
    assert d["final_synthesis_skipped_reason"] == "complete_verified_entity_group"
    assert d["entity_group_summary"]["room_membership_verified"] is True
    assert "Shower Light" in result["answer"]["text"]
    assert "Shower Light:** off" in result["answer"]["text"]
    assert "Room membership is not verified" not in result["answer"]["text"]
    assert all(call[1]["tool"].startswith("hub_") for call in executor.calls)
