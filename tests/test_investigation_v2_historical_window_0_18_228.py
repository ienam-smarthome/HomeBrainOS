"""v0.18.228: recover an actual source event window without a keyword router.

The operator's later confirmation that the socket was physically unplugged
is ground truth for this replay, NOT a fact that can be inferred from a
Hubitat command. No unverified root-cause claim may be manufactured.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp_client import MCPTool

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from investigation_v2.native_history_recovery import (
    requested_history_bounds, normalize_selected_history_read,
)
from investigation_v2.native_read_agent import run_native_read_agent
from test_investigation_v2_temporal_lead_0_18_225 import device, events
from test_investigation_v2_native_entity_lookup_0_18_184 import native
from test_investigation_v2_native_read_agent_0_18_181 import (
    FakeMCP, FakeExecutor,
)

QUESTION = (
    "Investigate why Bedroom 3 Mesh stopped communicating on 12 October "
    "2026. Correlate the power-saving rule's OFF command with subsequent "
    "lastSeen, switch-state and health-status events, including exact "
    "timestamps. Inspect available rule actions and execution logs, "
    "distinguish confirmed Hubitat events from actual physical behaviour. "
    "Read only; change nothing."
)
READ_DEVICE = MCPTool(
    "hub_read_devices", "READ events and devices",
    {"type": "object", "properties": {
        "tool": {"type": "string", "enum": [
            "hub_get_device", "hub_list_device_events"]},
        "args": {"type": "object", "additionalProperties": True},
    }, "required": ["tool", "args"]},
    annotations={"readOnlyHint": True},
)


def test_user_date_bounds_reach_october_12_and_are_timezone_padded():
    scope = requested_history_bounds(QUESTION)
    assert scope["since"] == "2026-10-11T00:00:00+00:00"
    assert scope["until"] == "2026-10-14T00:00:00+00:00"
    assert scope["hub_timezone_verified"] is False
    assert requested_history_bounds("Why is the freezer offline?") is None


def test_verified_unique_subject_repairs_model_omitted_id_and_date():
    fixed, receipt = normalize_selected_history_read(
        "hub_read_devices",
        {"tool": "hub_list_device_events",
         "args": {"limit": 10}},
        focus_ids={"7103"}, verified_device_ids={"7103"},
        question=QUESTION,
    )
    assert fixed["args"] == {
        "deviceId": "7103",
        "limit": 100,
        "since": "2026-10-11T00:00:00+00:00",
        "until": "2026-10-14T00:00:00+00:00",
    }
    assert receipt["verified_device_id_inserted"] is True
    assert receipt["historical_window"]["source"] == (
        "explicit_user_calendar_date")


@pytest.mark.parametrize("focus,verified,arguments", [
    (set(), {"7103"}, {"tool":"hub_list_device_events", "args":{}}),
    ({"7103","7104"}, {"7103","7104"},
     {"tool":"hub_list_device_events", "args":{}}),
    ({"7103"}, set(), {"tool":"hub_list_device_events", "args":{}}),
    ({"7103"}, {"7103"},
     {"tool":"hub_list_device_events", "args":{"deviceId":"7104"}}),
    ({"7103"}, {"7103"},
     {"tool":"hub_list_device_events", "args":{"mode":"hub"}}),
    ({"7103"}, {"7103"},
     {"tool":"hub_list_device_events", "args":{"appId":"3950"}}),
    ({"7103"}, {"7103"}, {"tool":"hub_delete_device", "args":{}}),
])
def test_scope_repair_never_guesses_or_changes_unrelated_tools(
        focus, verified, arguments):
    result, receipt = normalize_selected_history_read(
        "hub_read_devices", arguments, focus_ids=focus,
        verified_device_ids=verified, question=QUESTION)
    assert result == arguments
    assert receipt is None


def test_explicit_model_history_scope_is_not_overridden():
    original = {"tool": "hub_list_device_events",
                "args": {"deviceId": "7103", "limit": 20,
                         "since": "2026-10-12T00:00:00+01:00"}}
    result, receipt = normalize_selected_history_read(
        "hub_read_devices", original, focus_ids={"7103"},
        verified_device_ids={"7103"}, question=QUESTION)
    assert result == original
    assert receipt is None


@pytest.mark.asyncio
async def test_live_shaped_question_recovers_scope_and_read_only_timeline():
    mcp = FakeMCP([READ_DEVICE])
    async def identities():
        return [{"id": "7103", "label": "Bedroom 3 Mesh",
                 "name": "Tasmota MQTT - Bedroom3_Mesh"}]
    mcp.get_device_identities = identities
    executor = FakeExecutor(mcp, [device(), events()])
    step = 0
    async def model(messages, tools):
        nonlocal step
        step += 1
        if step == 1:
            return {"tool_calls": [native(
                "homebrain_find_device", {"name": "Bedroom 3 Mesh"})]}
        if step == 2:
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_get_device",
                "args": {"deviceId": "7103", "mode": "summary"}})]}
        if step == 3:
            # Exact failure in live run: missing deviceId and only 10
            # newest health events; host repairs from verified focus.
            return {"tool_calls": [native("hub_read_devices", {
                "tool": "hub_list_device_events", "args": {"limit": 10}})]}
        return {"content": '{"claims":[]}'}
    result = await run_native_read_agent(
        question=QUESTION, chat=model, mcp=mcp, executor=executor,
        max_rounds=4, max_reads=4)
    assert len(executor.calls) == 2
    assert executor.calls[1][1]["args"]["deviceId"] == "7103"
    assert executor.calls[1][1]["args"]["since"].startswith("2026-10-11")
    assert executor.calls[1][1]["args"]["limit"] == 100
    diagnostics = result["native_diagnostics"]
    assert diagnostics["rejected_scope_history_reads"] == 0
    assert diagnostics["normalized_history_reads"][0][
        "verified_device_id_inserted"] is True
    assert diagnostics["verified_temporal_lead"]["app_id"] == "3950"
    assert diagnostics["successful_reads"] == 2
    assert diagnostics["concise_answer_source"] == (
        "source_verified_temporal_lead")
    assert "not a verified cause" in result["answer"]["text"]
    assert "socket was physically disconnected" not in result["answer"]["text"]
    assert "No independently verifiable source claim" not in (
        result["answer"]["text"])
