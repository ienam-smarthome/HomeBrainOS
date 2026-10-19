"""v0.18.39: app-log selection must follow same-turn recorded command origin."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))
from provenance_app_log_planner import pending_provenance_app_log_read
from mcp_agent_orchestrator import UnifiedMCPAgent
import mcp_agent_orchestrator as orchestration


QUESTION = (
    "Investigate the Bedroom 3 Mesh OFF event on 12 October 2026 at "
    "approximately 01:30 BST. Compare possible command issuers and "
    "identify evidence gaps. Read-only."
)


def source():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "evidence_kind": "targeted_device_lookup", "success": True,
            "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_list_devices", "args": {
                "labelFilter": "Bedroom 3 Mesh",
            }},
            "details": {"reportedDeviceState": {
                "deviceId": "7103", "label": "Bedroom 3 Mesh",
                "reportedAttributes": {"healthStatus": "offline"},
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "evidence_kind": "authoritative_device_event_history",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_list_device_events", "args": {
                "deviceId": "7103", "since": "2026-10-12T00:20:00Z",
                "until": "2026-10-12T00:40:00Z",
            }},
            "details": {"observedEvents": [
                {"name": "command-off", "type": "command",
                 "date": "2026-10-12T01:30:01.743+0100",
                 "producedBy": {"appId": 3950,
                                "name": "Power saving: Bedroom 3 Mesh off @night"}},
                {"name": "switch", "value": "off",
                 "date": "2026-10-12T01:30:01.914+0100",
                 "producedBy": {"deviceId": "7103"}},
            ]},
        },
    ]


def test_decisive_app_log_read_is_in_correct_utc_window_with_verified_app():
    plan = pending_provenance_app_log_read(QUESTION, source())
    assert plan == {
        "tool": "hub_get_logs", "args": {
            "appId": "3950",
            "since": "2026-10-12T00:20:00Z",
            "until": "2026-10-12T00:40:00Z",
            "limit": 100,
        },
        "reason": "recorded app issuer; verified incident window",
        "deviceId": "7103",
    }


def test_misrouted_app_id_device_event_call_does_not_count_as_app_logs():
    rows = source()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True, "arguments": {
            "tool": "hub_list_device_events", "args": {
                "appId": "3950", "since": "2026-10-12T00:20:00Z",
                "until": "2026-10-12T00:40:00Z",
            },
        }, "details": {"events": []},
    })
    assert pending_provenance_app_log_read(QUESTION, rows) is not None


def test_already_attempted_app_logs_are_not_requeried_even_after_error():
    for success in (True, False):
        rows = source()
        rows.append({
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": success, "arguments": {
                "tool": "hub_get_logs", "args": {
                    "appId": 3950, "since": "2026-10-12T00:15:00Z",
                    "until": "2026-10-12T00:45:00Z",
                },
            },
        })
        assert pending_provenance_app_log_read(QUESTION, rows) is None


def test_wrong_utc_window_does_not_fulfil_incident_app_logs():
    rows = source()
    rows.append({
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "arguments": {
            "tool": "hub_get_logs", "args": {
                "appId": 3950, "since": "2026-10-12T01:20:00Z",
                "until": "2026-10-12T01:40:00Z",
            },
        },
    })
    assert pending_provenance_app_log_read(QUESTION, rows) is not None


def test_fail_closed_without_matched_identity_and_explicit_clock():
    assert pending_provenance_app_log_read(QUESTION, source()[1:]) is None
    assert pending_provenance_app_log_read(
        QUESTION.replace("Bedroom 3 Mesh", "Other Device"), source(),
    ) is None
    assert pending_provenance_app_log_read(
        QUESTION.replace("01:30 BST", "01:30 GMT"), source(),
    ) is None
    assert pending_provenance_app_log_read(
        QUESTION.replace("OFF event", "ON event"), source(),
    ) is None
    assert pending_provenance_app_log_read(
        QUESTION.replace("Mesh OFF", "Mesh (device 9999) OFF"), source(),
    ) is None
    assert pending_provenance_app_log_read(
        "Turn off Bedroom 3 Mesh", source(),
    ) is None


def test_competing_issuer_events_do_not_authorize_arbitrary_app_logs():
    rows = source()
    rows[1]["details"]["observedEvents"].append({
        "name": "command-off", "type": "command",
        "date": "2026-10-12T01:30:02.000+0100",
        "producedBy": {"appId": 9999, "name": "Other app"},
    })
    assert pending_provenance_app_log_read(QUESTION, rows) is None


@pytest.mark.asyncio
async def test_final_answer_queries_one_verified_app_log_then_synthesizes(monkeypatch):
    class MCP:
        async def list_tools(self):
            return []
    class Catalog:
        def available_tool(self, name):
            return SimpleNamespace(name="hub_read_diagnostics") if name == "hub_read_diagnostics" else None
        def gateway_operation_error(self, name, arguments):
            assert name == "hub_read_diagnostics"
            assert arguments["tool"] == "hub_get_logs"
            return None
    captured = []
    class Answers:
        async def answer(self, messages):
            captured.extend(messages)
            return "Recorded issuer app 3950; upstream trigger not verified."
    monkeypatch.setattr(orchestration, "build_focal_source_plan", lambda a, b: None)
    monkeypatch.setattr(orchestration, "pending_device_log_read", lambda a, b: None)
    monkeypatch.setattr(orchestration, "pending_historical_command_read", lambda a, b: None)
    monkeypatch.setattr(orchestration, "pending_scoped_explanation_command_read", lambda a, b: None)
    monkeypatch.setattr(orchestration, "build_request_tool_catalog", lambda _: Catalog())
    monkeypatch.setattr(
        orchestration, "classify_tool_effect", lambda *args: SimpleNamespace(mutates=False),
    )
    agent = UnifiedMCPAgent(MCP(), "unused", ai_client=object())
    agent.final_answers = Answers()
    calls = []
    async def read(name, arguments, **kwargs):
        calls.append((name, arguments))
        agent.evidence.record(
            name, arguments, success=True, elapsed_ms=1, mutates=False,
            effect="read", evidence_kind="authoritative_native_app_logs",
            summary="0 app log rows", details={"logCount": 0, "logs": []},
        )
        return SimpleNamespace(success=True, content='{"logs":[]}')
    monkeypatch.setattr(agent.executor, "execute", read)
    token = agent.evidence.begin()
    goal = agent._current_user_objective.set(QUESTION)
    try:
        agent.evidence.context.get().extend(source())
        reply = await agent._final_answer([{"role": "user", "content": QUESTION}])
        assert "upstream trigger not verified" in reply
        assert calls == [("hub_read_diagnostics", {
            "tool": "hub_get_logs", "args": {
                "appId": "3950", "since": "2026-10-12T00:20:00Z",
                "until": "2026-10-12T00:40:00Z", "limit": 100,
            },
        })]
        assert captured[-1]["role"] == "tool"
        assert captured[-1]["tool_name"] == "hub_read_diagnostics"
        await agent._final_answer([{"role": "user", "content": QUESTION}])
        assert len(calls) == 1
    finally:
        agent._current_user_objective.reset(goal)
        agent.evidence.reset(token)


@pytest.mark.asyncio
async def test_no_read_gateway_cannot_execute_nonexistent_tool(monkeypatch):
    class MCP:
        async def list_tools(self):
            return []
    class Catalog:
        def available_tool(self, name):
            return None
    class Answers:
        async def answer(self, messages):
            return "No app-log source available."
    monkeypatch.setattr(orchestration, "build_focal_source_plan", lambda a, b: None)
    monkeypatch.setattr(orchestration, "pending_device_log_read", lambda a, b: None)
    monkeypatch.setattr(orchestration, "pending_historical_command_read", lambda a, b: None)
    monkeypatch.setattr(orchestration, "pending_scoped_explanation_command_read", lambda a, b: None)
    monkeypatch.setattr(orchestration, "build_request_tool_catalog", lambda _: Catalog())
    agent = UnifiedMCPAgent(MCP(), "unused", ai_client=object())
    agent.final_answers = Answers()
    async def fail(*args, **kwargs):
        raise AssertionError("No MCP operation may run without the gateway")
    monkeypatch.setattr(agent.executor, "execute", fail)
    token = agent.evidence.begin()
    goal = agent._current_user_objective.set(QUESTION)
    try:
        agent.evidence.context.get().extend(source())
        assert await agent._final_answer([{"role": "user", "content": QUESTION}]) == "No app-log source available."
    finally:
        agent._current_user_objective.reset(goal)
        agent.evidence.reset(token)
