"""General source-timed investigation replay; never turn proximity into cause."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from mcp_client import MCPTool
from investigation_v2.native_temporal_lead import (
    verified_temporal_lead, temporal_lead_brief, _timestamp,
)
from investigation_v2.native_provenance import event_summary
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor,
)
from test_investigation_v2_native_entity_lookup_0_18_184 import (
    NAME, DEVICE, native,
)

EVENTS = MCPTool(
    "hub_read_events", "Read scoped device events",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["hub_list_device_events"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]}, annotations={"readOnlyHint": True},
)


def device():
    return {"id": "7103", "name": "Tasmota MQTT - Bedroom3_Mesh",
            "label": "Bedroom 3 Mesh", "attributes": [
                {"name": "lastSeen", "value": "Mon Oct 12 01:30:01 BST 2026"},
                {"name": "healthStatus", "value": "offline"},
                {"name": "mqttStatus", "value": "connected"},
                {"name": "switch", "value": "off"},
                {"name": "dataAgeSeconds", "value": 162325},
            ]}


def events():
    return {"events": [
        {"name": "command-on", "date": "2026-10-19T21:50:18.778+0100",
         "producedBy": {"appId": "3103", "name": "Ikea Rodret Dimmer"}},
        {"name": "command-off", "date": "2026-10-12T01:30:01.743+0100",
         "producedBy": {"appId": "3950",
                        "name": "Power saving: Bedroom 3 Mesh off @night"}},
        {"name": "deviceHealth", "value": "unknown",
         "date": "2026-10-29T17:36:46.684+0000",
         "producedBy": {"deviceId": "7103"}},
    ]}


def receipts():
    return [
        {"read": 1, "operation": "hub_get_device",
         "read_filters": {"deviceId": "7103"}, "source_data": device()},
        {"read": 2, "operation": "hub_list_device_events",
         "read_filters": {"deviceId": "7103"},
         "source_data": event_summary(events())},
    ]


def test_bst_october_2026_matches_explicit_iso_offset_without_dst_guessing():
    same = _timestamp("Mon Oct 12 01:30:01 BST 2026")
    event = _timestamp("2026-10-12T01:30:01.743+0100")
    assert same is not None
    assert (event-same).total_seconds() == .743
    assert _timestamp("2026-10-12T01:30:01") is None
    assert _timestamp("Oct 12 01:30:01 UK 2026") is None
    assert _timestamp("Sun Oct 25 01:30:01 BST 2026") is not None
    assert _timestamp("Sun Oct 25 01:30:01 GMT 2026") is not None
    assert (_timestamp("Sun Oct 25 01:30:01 GMT 2026")
            -_timestamp("Sun Oct 25 01:30:01 BST 2026")).total_seconds()==3600


def test_attested_off_command_near_reported_last_seen_is_lead_not_cause():
    result = verified_temporal_lead(receipts(), ["7103"])
    assert result["app_id"] == "3950"
    assert result["command"] == "off"
    assert result["absolute_gap_seconds"] == .743
    assert result["later_on_commands"] == 1
    assert result["mechanism_verified"] is False
    assert result["physical_command_delivery_verified"] is False
    answer = temporal_lead_brief(result)
    assert "Power saving: Bedroom 3 Mesh off @night" in answer
    assert "lastSeen=Mon Oct 12 01:30:01 BST 2026" in answer
    assert "0.743 seconds" in answer
    assert "not a verified cause" in answer
    assert "does not independently confirm device connectivity" in answer
    assert "later `on` command" in answer
    assert "lastActivity" not in answer


@pytest.mark.parametrize("mutation", [
    lambda rs: rs[1]["read_filters"].update({"deviceId": "9999"}),
    lambda rs: rs[1]["read_filters"].clear(),
    lambda rs: rs[0]["source_data"].update({"id": "9999"}),
    lambda rs: rs[0]["read_filters"].update({"deviceId": "9999"}),
    lambda rs: rs[0]["source_data"]["attributes"][0].update(
        {"value": "unknown"}),
    # A source-projected direct event can now verify a command even
    # when the five-sample issuer summary is empty. Remove BOTH real
    # source paths when testing an absent command.
    lambda rs: rs[1]["source_data"].update({
        "issuer_apps": [],
        "events": [event for event in rs[1]["source_data"]["events"]
                   if not event["name"].startswith("command-")],
    }),
])
def test_unmatched_or_missing_source_identity_cannot_create_timing_lead(mutation):
    rs = receipts()
    mutation(rs)
    assert verified_temporal_lead(rs, ["7103"]) is None


def test_unrelated_and_unverifiable_timestamps_cannot_create_timing_lead():
    rs = receipts()
    for issuer in rs[1]["source_data"]["issuer_apps"]:
        for sample in issuer["samples"]:
            sample["date"] = "2026-10-10T08:00:00+0000"
    # The complete projected event page is a second independent source
    # path. Move the command timestamps there too for this no-nearby-
    # command test; otherwise the new interpreter correctly finds them.
    for event in rs[1]["source_data"]["events"]:
        if event["name"].startswith("command-"):
            event["date"] = "2026-10-10T08:00:00+0000"
    assert verified_temporal_lead(rs, ["7103"]) is None
    rs = receipts()
    assert verified_temporal_lead(rs, ["7103", "8000"]) is None


def test_duplicate_scoped_event_pages_cannot_inflate_recovery_count():
    rs = receipts()
    rs.append({**rs[1], "read": 3})
    result = verified_temporal_lead(rs, ["7103"])
    assert result["later_on_commands"] == 1


@pytest.mark.asyncio
async def test_native_investigation_publishes_timed_lead_not_unstructured_cause():
    mcp = FakeMCP([DEVICE, EVENTS])
    async def identities():
        return [{"id": "7103", "name": "Tasmota MQTT - Bedroom3_Mesh",
                 "label": "Bedroom 3 Mesh"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [device(), events()])
    step = 0

    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            return {"tool_calls": [native(
                NAME, {"name": "Bedroom 3 Mesh"})]}
        if step == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_get_device",
                "args": {"deviceId": "7103"}})]}
        if step == 3:
            return {"tool_calls": [native("hub_read_events", {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7103"}})]}
        assert "verified_command_time_lead" in messages[-1]["content"]
        return {"content":
                "The power-saving rule definitely broke the device."}

    result = await run_native_read_agent(
        question="Why did Bedroom 3 Mesh lose communication?",
        chat=model, mcp=mcp, executor=executor,
        max_rounds=4, max_reads=4)
    diagnostics = result["native_diagnostics"]
    assert len(executor.calls) == 2
    assert diagnostics["verified_temporal_lead"]["app_id"] == "3950"
    assert diagnostics["concise_answer_source"] == (
        "source_verified_temporal_lead")
    assert diagnostics["claim_publication"]["used_for_display_answer"] is False
    assert result["answer"]["validation_issues"][:2] == [
        "source_verified_temporal_command_lead",
        "physical_causation_unverified",
    ]
    answer = result["answer"]["text"]
    assert "0.743 seconds apart" in answer
    assert "Power saving: Bedroom 3 Mesh off @night" in answer
    assert "definitely broke" not in answer
    assert "Cause not confirmed" in answer
    assert "Read #2" in result["report"]["text"]
    assert "Read #1" in result["report"]["text"]
    assert "not a verified cause" in result["report"]["text"]
