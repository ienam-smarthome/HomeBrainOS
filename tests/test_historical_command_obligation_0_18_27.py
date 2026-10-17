"""Mandatory historical command-history source checking, not an app-specific patch."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from skill_source_completion import pending_historical_command_read
from mcp_agent_orchestrator import UnifiedMCPAgent
import mcp_agent_orchestrator as orchestrator


QUESTION = (
    'Verify whether the automation "Power saving: Bedroom 3 Mesh off @night" '
    '(app 3950) actually issued an OFF command to Bedroom 3 Mesh '
    '(device 7103) on 12 October 2026 at approximately 01:30 BST. '
    'Read-only.'
)


def evidence():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_get_device",
            "success": True, "arguments": {
                "tool": "hub_get_device", "args": {"deviceId": "7103"},
            },
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "arguments": {
                "tool": "hub_list_device_events",
                "args": {"deviceId": "7103", "attribute": "switch", "hoursBack": 168},
            },
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "arguments": {"name": "7103", "attribute": "switch", "hours_back": 168},
            "details": {"label": "Bedroom 3 Mesh", "boundaryEvents": [{
                "name": "switch", "value": "off", "producedBy": {
                    "type": "device", "id": "7103",
                }, "triggered": [{"appId": 4129}],
            }]},
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "arguments": {
                "tool": "hub_get_logs", "args": {"appId": 3950},
            }, "details": {"logCount": 0, "logs": []},
        },
    ]


def test_real_01826_history_requires_separate_command_stream():
    result = pending_historical_command_read(QUESTION, evidence())
    assert result == {
        "deviceId": "7103", "label": "Bedroom 3 Mesh",
        "hoursBack": 168, "action": "off",
    }


@pytest.mark.parametrize("question", [
    "Verify whether app 3950 issued an OFF command to device 7104 yesterday.",
    "Verify whether app 3950 issued an OFF command yesterday.",
    "Review app 3950 configuration for device 7103.",
    "Verify whether device 7103 went off yesterday.",
])
def test_never_infer_or_substitute_a_historical_command_target(question):
    assert pending_historical_command_read(question, evidence()) is None


def test_deduplicate_command_query_even_when_it_failed():
    rows = evidence()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": False, "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "7103", "attribute": "command-off"},
        },
    })
    assert pending_historical_command_read(QUESTION, rows) is None


def test_unverified_device_history_cannot_authorise_command_read():
    rows = evidence()
    rows[0]["success"] = False
    rows[1]["success"] = False
    rows[2]["success"] = False
    assert pending_historical_command_read(QUESTION, rows) is None


def test_command_horizon_is_taken_from_verified_history_not_guessed():
    rows = evidence()
    rows[1]["arguments"]["args"]["hoursBack"] = 24
    rows[2]["arguments"]["hours_back"] = 48
    result = pending_historical_command_read(QUESTION, rows)
    assert result["hoursBack"] == 48


@pytest.mark.asyncio
async def test_final_answer_completes_command_obligation_once(monkeypatch):
    class MCP:
        async def list_tools(self):
            return []

    class Catalog:
        def available_tool(self, name):
            return object() if name == "hub_read_devices" else None

    captured = []
    class FinalAnswers:
        async def answer(self, messages):
            captured.extend(messages)
            return "The historical command issuer remains unverified."

    monkeypatch.setattr(orchestrator, "build_focal_source_plan",
                        lambda receipts, objective: None)
    monkeypatch.setattr(orchestrator, "pending_device_log_read",
                        lambda objective, receipts: None)
    monkeypatch.setattr(orchestrator, "build_request_tool_catalog",
                        lambda tools: Catalog())

    agent = UnifiedMCPAgent(MCP(), "unused", ai_client=object())
    agent.final_answers = FinalAnswers()
    calls = []
    async def command_read(*, device_id, label, hours_back, actions):
        calls.append((device_id, label, hours_back, actions))
        agent.evidence.record(
            "hub_read_devices", {
                "tool": "hub_list_device_events", "args": {
                    "deviceId": device_id, "attribute": "command-off",
                    "hoursBack": hours_back,
                },
            }, success=True, elapsed_ms=1,
            summary="0 command-off events returned",
            effect="read", mutates=False,
            evidence_kind="authoritative_command_event_history",
            details={"label": label, "eventCount": 0, "events": []},
        )
        return []
    monkeypatch.setattr(agent.device_history, "_read_command_events", command_read)
    receipt_token = agent.evidence.begin()
    objective_token = agent._current_user_objective.set(QUESTION)
    try:
        for row in evidence():
            agent.evidence.context.get().append(row)
        outcome = await agent._final_answer([
            {"role": "user", "content": QUESTION},
        ])
        assert "unverified" in outcome
        assert calls == [("7103", "Bedroom 3 Mesh", 168, ("off",))]
        tool_messages = [m for m in captured if m.get("tool_name") == "hub_read_devices"]
        assert len(tool_messages) == 1
        data = json.loads(tool_messages[0]["content"])
        assert data["requiredHistoricalCommandRead"] is True
        assert data["attribute"] == "command-off"
        assert data["returnedCommandEvents"] == []
        assert "do not prove no historic" in data["note"]
        # A second synthesis cannot re-read a source already attempted.
        await agent._final_answer([{"role": "user", "content": QUESTION}])
        assert len(calls) == 1
    finally:
        agent._current_user_objective.reset(objective_token)
        agent.evidence.reset(receipt_token)


@pytest.mark.asyncio
async def test_no_gateway_means_no_unregistered_or_mutating_call(monkeypatch):
    class MCP:
        async def list_tools(self):
            return []
    class Catalog:
        def available_tool(self, name):
            return None
    class FinalAnswers:
        async def answer(self, messages):
            return "Historical command source unavailable."

    monkeypatch.setattr(orchestrator, "build_focal_source_plan",
                        lambda receipts, objective: None)
    monkeypatch.setattr(orchestrator, "pending_device_log_read",
                        lambda objective, receipts: None)
    monkeypatch.setattr(orchestrator, "build_request_tool_catalog",
                        lambda tools: Catalog())
    agent = UnifiedMCPAgent(MCP(), "unused", ai_client=object())
    agent.final_answers = FinalAnswers()
    token = agent.evidence.begin()
    goal = agent._current_user_objective.set(QUESTION)
    try:
        agent.evidence.context.get().extend(evidence())
        text = await agent._final_answer([{"role": "user", "content": QUESTION}])
        assert "unavailable" in text
        assert not any(
            r.get("sub_tool") == "hub_list_device_events"
            and (r.get("arguments") or {}).get("args", {}).get("attribute") == "command-off"
            for r in agent.evidence.receipts()
        )
    finally:
        agent._current_user_objective.reset(goal)
        agent.evidence.reset(token)
