"""0.18.93: the model, not keyword clusters, selects ambiguous read workflows.

These tests run a fake no-tools model, never a real Hubitat or model provider.
They test adversarial/invalid replies and preserve explicit user scope and
the host's separate no-write confirmation boundary.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ai_investigation_routing import (
    ReadRouteDecision, _parse_route, active_read_route, decide_read_route,
    explicit_system_check_command, reset_read_route, set_read_route,
    explicit_whole_hub_report_request, explicit_aggregate_performance_request,
)
from investigation_objective import resolve_primary_objective
from health_audit_service import is_comprehensive_system_audit_request


CLAUDE_COMPARISON = (
    "Perform a comprehensive READ-ONLY root-cause investigation of "
    "Bedroom 3 Mesh (Hubitat device ID 7103). Investigate logs, device "
    "driver source, historical events, app configuration and scheduled jobs. "
    "Explain why MQTT status connected can coexist with health offline. "
    "Use relevant live MCP tools and distinguish verified events from "
    "hypotheses. Do not modify anything."
)
NO_ID_FOCUSED = (
    "Comprehensively investigate why Bedroom 3 Mesh is offline. "
    "Check device events, automation logs, apps, performance stats, "
    "scheduled jobs and driver source to determine the cause. "
    "This is read-only; do not modify anything."
)
WHOLE_HUB = (
    "Perform a comprehensive system audit of my entire Hubitat hub. "
    "Include all devices, installed apps, logs, performance and scheduled jobs."
)
PERFORMANCE = (
    "Compare aggregate hub performance and resource usage statistics "
    "for the past day. Do not change settings."
)


def fake_chat(response, calls):
    async def chat(messages, tools):
        calls.append((messages, tools))
        return {"content": response}
    return chat


@pytest.mark.asyncio
async def test_replays_named_device_and_named_only_incident_without_keyword_hijack():
    calls = []
    decision = await decide_read_route(
        fake_chat('{"route":"model_led"}', calls), NO_ID_FOCUSED
    )
    assert decision == ReadRouteDecision(
        "model_led", "model_choice", objective="general_investigation",
    )
    assert len(calls) == 1
    assert calls[0][1] == []  # arbitration has no MCP tools
    assert "system" in calls[0][0][0]["role"]
    assert "Comprehensively investigate" in calls[0][0][1]["content"]
    assert resolve_primary_objective(CLAUDE_COMPARISON).is_targeted_device


@pytest.mark.asyncio
async def test_model_can_select_true_whole_hub_report_or_performance_stats():
    for question, result in (
        (WHOLE_HUB, "system_audit"),
        (PERFORMANCE, "performance_report"),
    ):
        selected = await decide_read_route(
            fake_chat('{"route":"' + result + '","objective":"' + result + '"}', []), question
        )
        assert selected.route == result
        assert selected.provenance == "model_choice"


@pytest.mark.asyncio
async def test_unjustified_fast_report_choice_is_demoted_to_interactive_mcp():
    for text, guess in (
        (NO_ID_FOCUSED, "system_audit"),
        (NO_ID_FOCUSED, "performance_report"),
        ("Read-only investigate app 3977 LimitExceededException and performance",
         "performance_report"),
        ("Investigate why device 7103 is offline using all relevant logs",
         "system_audit"),
    ):
        chosen = await decide_read_route(
            fake_chat('{"route":"' + guess + '"}', []), text
        )
        assert chosen.route == "model_led"
        assert chosen.provenance == "host_scope_override"


@pytest.mark.asyncio
async def test_invalid_timeout_or_tool_call_never_executes_tools_or_forces_report():
    for response in (
        "The best route is a system report.",
        '{"route":"enable_device"}',
        '{"route":["system_audit"]}',
        '{"route":"system_audit","unexpected":"hint"}\nadditional text',
    ):
        chosen = await decide_read_route(fake_chat(response, []), WHOLE_HUB)
        assert chosen.route == "model_led"

    async def call_with_tool_request(messages, tools):
        assert tools == []
        return {"content": '{"route":"system_audit"}',
                "tool_calls": [{"function": {"name": "hub_send_command"}}]}
    assert (await decide_read_route(call_with_tool_request, WHOLE_HUB)).route == "model_led"

    async def slow(messages, tools):
        await asyncio.sleep(0.05)
        return {"content": '{"route":"system_audit"}'}
    # Real minimum timeout is one second; test cancellation independently.
    cancelled = asyncio.create_task(decide_read_route(slow, WHOLE_HUB))
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled


@pytest.mark.asyncio
async def test_short_explicit_system_check_keeps_zero_model_overhead():
    calls = []
    selected = await decide_read_route(
        fake_chat('{"route":"model_led"}', calls), "Run system check"
    )
    assert selected == ReadRouteDecision("system_audit", "explicit_command")
    assert not calls
    assert explicit_system_check_command("Please show my system check report")
    assert not explicit_system_check_command(CLAUDE_COMPARISON)


def test_deliberate_entire_hub_and_scheduler_reports_skip_router():
    assert explicit_whole_hub_report_request(WHOLE_HUB)
    assert explicit_whole_hub_report_request(
        "Perform a comprehensive read-only investigation of my Hubitat system."
    )
    assert explicit_whole_hub_report_request(
        "Review all devices and installed automations with scheduler logs."
    )
    assert not explicit_whole_hub_report_request(NO_ID_FOCUSED)
    assert not explicit_whole_hub_report_request(CLAUDE_COMPARISON)
    assert explicit_aggregate_performance_request(
        "Analyse all scheduled jobs by handler and suggest efficiency improvements."
    )
    assert not explicit_aggregate_performance_request(NO_ID_FOCUSED)


def test_model_route_context_is_request_local_and_reset():
    assert active_read_route() is None
    token = set_read_route("model_led")
    try:
        assert active_read_route() == "model_led"
    finally:
        reset_read_route(token)
    assert active_read_route() is None


def test_app_and_agent_act_on_model_arbitration_before_host_shortcuts():
    app_py = (APP / "app.py").read_text(encoding="utf-8")
    agent_py = (APP / "homebrain_agent.py").read_text(encoding="utf-8")
    assert '"model_led" if (targeted_device or targeted_rule)' in app_py
    assert "or targeted_rule" in app_py
    assert "model_route == decision.route" in app_py
    assert 'if (model_route == "system_audit"' in app_py
    assert 'model_route == "model_led"' in app_py
    assert 'active_read_route() == "model_led"' in agent_py
    assert "reset_read_route(route_token)" in app_py
    assert "not _explicit_mutation_request(request.message)" in app_py
