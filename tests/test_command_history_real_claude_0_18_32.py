"""Regression: 0.18.31 Claude used a label history but never checked command-off."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from skill_source_completion import pending_historical_command_read
from mcp_agent_orchestrator import UnifiedMCPAgent
import mcp_agent_orchestrator as orchestrator

REQUEST = (
    'Verify whether the automation "Power saving: Bedroom 3 Mesh off @night" '
    '(app 3950) actually issued an OFF command to Bedroom 3 Mesh (device 7103) '
    'on 12 October 2026 at approximately 01:30 BST. Check original device '
    'events and automation execution evidence. Read-only.'
)


def observed_claude_receipts():
    """Faithful sanitized shape of the successful 0.18.31 read receipts."""
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "evidence_kind": "targeted_device_lookup",
            "arguments": {"tool": "hub_list_devices", "args": {
                "labelFilter": "Bedroom 3 Mesh", "detailed": True,
            }},
            "details": {"reportedDeviceState": {
                "deviceId": "7103", "label": "Bedroom 3 Mesh",
                "reportedAttributes": {"switch": "off", "healthStatus": "offline"},
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "arguments": {"tool": "hub_list_device_events",
                "args": {"deviceId": "7103", "hoursBack": 168,
                         "limit": 50, "attribute": "switch"}},
            "summary": "6 device events for Bedroom 3 Mesh",
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "arguments": {
                "name": "Bedroom 3 Mesh", "attribute": "switch",
                "hours_back": 168, "limit": 50,
            },
            "details": {
                "label": "Bedroom 3 Mesh",
                "historySourceIntegrity": "unverified",
                "boundaryEvents": [{
                    "name": "switch", "value": "off",
                    "date": "2026-10-12T01:30:01.914+0100",
                    "producedBy": {"type": "device", "id": "7103"},
                    "triggered": [{"appId": 4129}],
                }],
            },
        },
        {
            "tool": "hub_manage_logs", "sub_tool": "hub_get_logs",
            "success": True,
            "arguments": {"tool": "hub_get_logs", "args": {
                "appId": 3950, "since": "2026-10-11T23:00:00Z",
                "until": "2026-10-12T02:00:00Z"}},
            "details": {"logCount": 0, "logs": []},
        },
    ]


def test_exact_real_claude_label_history_plans_command_history():
    plan = pending_historical_command_read(REQUEST, observed_claude_receipts())
    assert plan == {
        "deviceId": "7103", "label": "Bedroom 3 Mesh",
        "hoursBack": 168, "action": "off",
    }


def test_targeted_id_label_works_even_without_optional_label_history():
    rows = observed_claude_receipts()[:2]
    assert pending_historical_command_read(REQUEST, rows)["deviceId"] == "7103"


def test_original_legacy_id_only_history_still_supported():
    rows = observed_claude_receipts()
    rows[0] = {"tool": "hub_read_devices", "sub_tool": "hub_get_device",
               "success": True, "arguments": {
                   "tool": "hub_get_device", "args": {"deviceId": "7103"}}}
    rows[2]["arguments"]["name"] = "7103"
    assert pending_historical_command_read(REQUEST, rows)["hoursBack"] == 168


def test_reject_unbound_history_label_or_different_target():
    rows = observed_claude_receipts()
    rows[0]["details"]["reportedDeviceState"]["deviceId"] = "7104"
    rows[1]["arguments"]["args"]["deviceId"] = "7104"
    assert pending_historical_command_read(REQUEST, rows) is None


def test_reject_history_label_that_conflicts_with_verified_identity():
    rows = observed_claude_receipts()
    rows[2]["details"]["label"] = "Hallway Socket"
    rows[2]["arguments"]["name"] = "Hallway Socket"
    # Correct targeted identity can still safely drive the command read,
    # but the mismatched local history cannot supply another horizon.
    rows[2]["arguments"]["hours_back"] = 720
    result = pending_historical_command_read(REQUEST, rows)
    assert result["label"] == "Bedroom 3 Mesh"
    assert result["hoursBack"] == 168


def test_failed_targeted_lookup_does_not_authorize_command_read_alone():
    rows = observed_claude_receipts()
    rows[0]["success"] = False
    rows[1]["success"] = False
    assert pending_historical_command_read(REQUEST, rows) is None


def test_existing_failed_command_query_must_not_loop_or_charge_again():
    rows = observed_claude_receipts()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": False,
        "arguments": {"tool": "hub_list_device_events", "args": {
            "deviceId": "7103", "attribute": "command-off", "hoursBack": 168}},
    })
    assert pending_historical_command_read(REQUEST, rows) is None


@pytest.mark.asyncio
async def test_final_source_completion_executes_exact_read_once_from_claude_shape(monkeypatch):
    class MCP:
        async def list_tools(self):
            return []
    class Catalog:
        def available_tool(self, name):
            return object() if name == "hub_read_devices" else None
    captured = []
    class Final:
        async def answer(self, messages):
            captured[:] = deepcopy(messages)
            return "The hub recorded switch=off; issuer remains unverified."

    monkeypatch.setattr(orchestrator, "build_focal_source_plan",
                        lambda receipts, objective: None)
    monkeypatch.setattr(orchestrator, "pending_device_log_read",
                        lambda objective, receipts: None)
    monkeypatch.setattr(orchestrator, "build_request_tool_catalog",
                        lambda tools: Catalog())
    agent = UnifiedMCPAgent(MCP(), "unused", ai_client=object())
    agent.final_answers = Final()
    calls = []
    async def command_read(*, device_id, label, hours_back, actions):
        calls.append((device_id, label, hours_back, actions))
        agent.evidence.record("hub_read_devices", {
            "tool": "hub_list_device_events", "args": {
                "deviceId": device_id, "attribute": "command-off",
                "hoursBack": hours_back,
            }}, success=True, elapsed_ms=1, summary="0 rows",
            effect="read", mutates=False,
            evidence_kind="authoritative_command_event_history",
            details={"eventName": "command-off", "eventCount": 0,
                     "events": [], "label": label})
        return []
    monkeypatch.setattr(agent.device_history, "_read_command_events", command_read)
    proof = agent.evidence.begin()
    obj = agent._current_user_objective.set(REQUEST)
    try:
        agent.evidence.context.get().extend(observed_claude_receipts())
        result = await agent._final_answer([{"role": "user", "content": REQUEST}])
        assert "issuer remains unverified" in result
        assert calls == [("7103", "Bedroom 3 Mesh", 168, ("off",))]
        host_rows = [row for row in captured
                     if row.get("tool_name") == "hub_read_devices"]
        assert len(host_rows) == 1
        host = json.loads(host_rows[0]["content"])
        assert host["sourceQuerySucceeded"] is True
        assert host["attribute"] == "command-off"
        assert host["returnedCommandEvents"] == []
        await agent._final_answer([{"role": "user", "content": REQUEST}])
        assert len(calls) == 1
    finally:
        agent._current_user_objective.reset(obj)
        agent.evidence.reset(proof)


def test_state_event_does_not_justify_unqualified_command_dispatch_claim():
    from historical_causal_claim_guard import reconcile_historical_dispatch_claim
    text = ("The hub recorded switch=off. The command dispatch is established; "
            "the commanding app is unverified.")
    corrected, changed = reconcile_historical_dispatch_claim(
        text, REQUEST, observed_claude_receipts(),
    )
    assert changed is True
    assert "command dispatch is established" not in corrected
    assert "command dispatch remains unverified" in corrected
    assert "The hub recorded switch=off" in corrected


def test_empty_successful_command_history_is_not_positive_command_evidence():
    from historical_causal_claim_guard import reconcile_historical_dispatch_claim
    receipts = observed_claude_receipts() + [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "7103", "attribute": "command-off"},
        }, "details": {"events": [], "eventCount": 0},
    }]
    corrected, changed = reconcile_historical_dispatch_claim(
        "The command dispatch was confirmed.", REQUEST, receipts,
    )
    assert changed is True
    assert "remains unverified" in corrected


def test_positive_matching_command_event_does_not_trigger_false_rewrite():
    from historical_causal_claim_guard import reconcile_historical_dispatch_claim
    receipts = observed_claude_receipts() + [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "7103", "attribute": "command-off"},
        }, "details": {"events": [{
            "name": "command-off",
            "date": "2026-10-12T01:30:00+0100",
        }]},
    }]
    text, changed = reconcile_historical_dispatch_claim(
        "The command dispatch is established.", REQUEST, receipts,
    )
    assert changed is False
    assert text == "The command dispatch is established."


def test_unrelated_device_command_event_cannot_authorize_target_dispatch():
    from historical_causal_claim_guard import reconcile_historical_dispatch_claim
    receipts = observed_claude_receipts() + [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "9999", "attribute": "command-off"},
        }, "details": {"events": [{"name": "command-off"}]},
    }]
    text, changed = reconcile_historical_dispatch_claim(
        "The command dispatch has been verified.", REQUEST, receipts,
    )
    assert changed is True
    assert "remains unverified" in text
