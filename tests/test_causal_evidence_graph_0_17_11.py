"""Generic evidence-graph and source-sufficiency tests for causal questions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_evidence_graph import (  # noqa: E402
    build_causal_evidence_graph,
    needs_mode_history,
    render_causal_evidence_graph,
    select_focal_sensor_events,
    supports_one_pass_deep_synthesis,
)
from homebrain_agent import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402

QUESTION = (
    "Investigate thoroughly why Example Light 1 turned on at 07:53:36 on "
    "12 October. Check the controlling app, configured triggers, actual sensor "
    "events, app execution logs and possible alternative causes. Read-only."
)


def _receipts(*, include_mode=True, include_handler=True, include_off_command=False):
    app_id, sensor_id = "4013", "7895"
    commands = [{
        "name": "command-setLevel",
        "date": "2026-10-12T07:53:36.621+0100",
        "description": "Command called: setLevel(50)",
        "producedBy": {
            "type": "app", "id": app_id, "label": "Example Lighting Automation"
        },
    }]
    if include_off_command:
        commands.append({
            "name": "command-off",
            "date": "2026-10-12T08:10:58.085+0100",
            "description": "Command called: off()",
            "producedBy": {
                "type": "app", "id": app_id, "label": "Example Lighting Automation"
            },
        })
    receipts = [
        {
            "tool": "homebrain_device_history", "success": True,
            "details": {
                "label": "Example Light 1", "attribute": "switch",
                "temporalAnalysis": {
                    "intervalCount": 1,
                    "observedIntervals": [{
                        "start": "2026-10-12T07:53:36.721+0100",
                        "end": "2026-10-12T08:10:58.185+0100",
                        "durationSeconds": 1041,
                    }],
                },
                "commandEvents": commands,
            },
        },
        {
            "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
            "success": True,
            "arguments": {"tool": "hub_get_app_config", "args": {
                "appId": app_id, "includeSettings": False,
            }},
            "details": {
                "appId": app_id,
                "configured": [
                    "Activation sources motion, manual turn-on, mode changes.",
                    "Off after 10 seconds inactive",
                ],
            },
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True,
            "arguments": {"tool": "hub_get_logs", "args": {
                "appId": app_id,
                "since": "2026-10-12T06:53:24.621Z",
                "until": "2026-10-12T06:53:42.621Z",
            }},
            "details": {"logCount": 0, "execution": []},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "arguments": {"tool": "hub_list_device_events", "args": {
                "deviceId": sensor_id, "attribute": "motion",
            }},
            "details": {
                "deviceId": sensor_id,
                "events": [
                    {
                        "name": "motion", "value": "active",
                        "date": "2026-10-12T07:53:36.542+0100",
                        "triggered": (
                            [{"appId": 4013, "handler": "motionHandler"}]
                            if include_handler else []
                        ),
                    },
                    {
                        "name": "motion", "value": "inactive",
                        "date": "2026-10-12T08:10:58.021+0100",
                        "triggered": (
                            [{"appId": 4013, "handler": "motionHandler"}]
                            if include_handler else []
                        ),
                    },
                ],
            },
        },
        {
            "tool": "homebrain_causal_trigger_correlation", "success": True,
            "arguments": {"appId": app_id, "deviceId": sensor_id, "attribute": "motion"},
            "details": {
                "label": "Example Occupancy",
                "attribute": "motion", "configured": True,
                "sensorEvent": "2026-10-12T07:53:36.542+0100",
                "stateBoundary": "2026-10-12T07:53:36.721+0100",
                "signedDeltaSeconds": -0.179,
            },
        },
    ]
    if include_mode:
        receipts.append({
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "evidence_kind": "authoritative_location_event_history",
            "arguments": {"tool": "hub_list_device_events", "args": {
                "hoursBack": 24, "limit": 20,
            }},
            "details": {"count": 3, "events": [
                {"name": "mode", "value": "School Run",
                 "date": "2026-10-12T07:15:01.264+0100"},
                {"name": "mode", "value": "Morning",
                 "date": "2026-10-12T08:30:01.911+0100"},
            ]},
        })
    return receipts


def test_graph_preserves_direct_command_and_sensor_listener_without_inferring_internal_logic():
    graph = build_causal_evidence_graph(_receipts(), QUESTION)
    assert graph["scope"] == "single-observed-event"
    assert graph["focus"]["durationSeconds"] == 1041
    assert graph["directCommand"]["status"] == "confirmed-direct-command-producer"
    assert graph["directCommand"]["producer"]["id"] == "4013"
    assert graph["directCommand"]["commandBeforeStateMs"] == 100.0
    assert graph["initiatorCandidate"]["entity"] == "Example Occupancy"
    assert graph["initiatorCandidate"]["beforeCommandMs"] == 79.0
    assert graph["initiatorCandidate"]["notifiedAppHandler"] == {
        "appId": "4013", "handler": "motionHandler"
    }
    assert graph["initiatorCandidate"]["notProofOfInternalDecision"]
    assert graph["initiatorCandidate"]["endEvent"]["beforeEndMs"] == 164.0
    assert graph["initiatorCandidate"]["endEvent"]["relationship"] == "temporal-correlation-only"
    assert graph["offCommand"] is None
    assert graph["offAttribution"] == "unresolved-no-proven-off-command"
    assert graph["executionLogs"]["result"] == "zero-observed-entries"
    assert graph["executionLogs"]["checked"]
    assert graph["locationMode"]["lastObservedBeforeEvent"]["value"] == "School Run"
    assert graph["locationMode"]["transitionObservedNearEvent"] is False
    assert graph["ready"]


def test_observed_off_command_promotes_only_off_command_not_sensor_trigger_certainty():
    graph = build_causal_evidence_graph(
        _receipts(include_off_command=True, include_handler=False), QUESTION
    )
    assert graph["offCommand"]["action"] == "off"
    assert graph["offCommand"]["producer"]["id"] == "4013"
    assert graph["offAttribution"] == "confirmed-direct-command"
    assert graph["initiatorCandidate"]["notifiedAppHandler"] is None
    assert graph["initiatorCandidate"]["notProofOfInternalDecision"]


def test_graph_does_not_claim_late_sensor_can_initiate_prior_command():
    receipts = _receipts()
    for row in receipts:
        if row.get("tool") == "homebrain_causal_trigger_correlation":
            row["details"]["sensorEvent"] = "2026-10-12T07:53:37.521+0100"
    graph = build_causal_evidence_graph(receipts, QUESTION)
    assert graph["initiatorCandidate"] is None
    assert not graph["ready"]
    assert "configured-or-correlated-upstream-sensor-event" in graph["missing"]


def test_graph_does_not_equate_a_checked_app_log_with_a_filled_execution_trace():
    graph = build_causal_evidence_graph(_receipts(), QUESTION)
    assert graph["executionLogs"]["observedRows"] == 0
    assert graph["executionLogs"]["internalDecisionProven"] is False
    rendered = render_causal_evidence_graph(_receipts(), QUESTION)
    assert "not a pre-decided causal verdict" in rendered
    assert "not prove the rule's OFF logic" in rendered
    assert "motionHandler" in rendered


def test_bounded_sensor_receipts_keep_start_end_notifications_and_drop_old_history():
    payload = {"events": [
        {"name": "motion", "value": "active",
         "date": "2026-10-10T01:00:00+0100"},
        *(_receipts()[3]["details"]["events"]),
        {"name": "motion", "value": "inactive",
         "date": "2026-10-11T00:00:00+0100"},
    ]}
    events = select_focal_sensor_events(payload, {
        "start": "2026-10-12T07:53:36.721+0100",
        "end": "2026-10-12T08:10:58.185+0100",
    })
    assert len(events) == 2
    assert all(event.get("triggered") for event in events)
    assert events[0]["date"].startswith("2026-10-12")


def test_optional_mode_history_is_one_bounded_gap_not_an_exhaustive_negative_claim():
    partial = build_causal_evidence_graph(_receipts(include_mode=False), QUESTION)
    assert partial["ready"]  # ON chain known but alternate mode read is still useful
    assert needs_mode_history(partial, QUESTION)
    assert not supports_one_pass_deep_synthesis(partial, QUESTION)
    complete = build_causal_evidence_graph(_receipts(), QUESTION)
    assert not needs_mode_history(complete, QUESTION)
    assert supports_one_pass_deep_synthesis(complete, QUESTION)
    assert complete["locationMode"]["coverage"] == "returned-rows-only"


def test_ambiguous_multi_interval_history_does_not_become_single_focal_certainty():
    receipts = _receipts()
    intervals = receipts[0]["details"]["temporalAnalysis"]["observedIntervals"]
    intervals.append({
        "start": "2026-10-11T07:53:36.721+0100",
        "end": "2026-10-11T08:10:58.185+0100",
        "durationSeconds": 1041,
    })
    graph = build_causal_evidence_graph(receipts, QUESTION)
    assert graph["scope"] == "ambiguous-or-unobserved-event"
    assert not graph["ready"]


class _NoAIProvider:
    async def aclose(self):
        return None

    async def post(self, *_args, **_kwargs):
        raise AssertionError("Test should call overridden _chat, not a provider")


@pytest.mark.asyncio
async def test_complete_explicit_deep_question_uses_one_final_model_synthesis():
    # Extend the existing in-repo native MCP fake. This keeps the normal
    # prefetch/command-provenance code path rather than manufacturing a
    # pre-computed graph in the test.
    from test_causal_rule_decision_context import _MCP

    class MCP(_MCP):
        async def call_tool(self, name, arguments):
            leaf, args = arguments["tool"], arguments.get("args") or {}
            if name == "hub_read_diagnostics" and leaf == "hub_get_logs" and args.get("appId") == "3602":
                # The live case had zero scoped app-log entries. When logs
                # already prove a different trigger, the host must not pretend
                # that missing sensor history has been examined.
                self.calls.append((name, arguments))
                return MCPToolResult(name, arguments, {}, "ok", {"logs": []})
            if name == "hub_read_devices" and leaf == "hub_list_device_events":
                if args.get("deviceId") == "7771":
                    self.calls.append((name, arguments))
                    return MCPToolResult(name, arguments, {}, "ok", {
                        "events": [{
                            "name": "motion", "value": "active",
                            "date": "2026-10-11T12:00:02.915+0100",
                            "triggered": [{"appId": 3602, "handler": "motionHandler"}],
                        }]
                    })
                if args.get("deviceId") is None:
                    self.calls.append((name, arguments))
                    return MCPToolResult(name, arguments, {}, "ok", {
                        "count": 2,
                        "events": [
                            {"name": "mode", "value": "Afternoon",
                             "date": "2026-10-11T11:00:00+0100"},
                            {"name": "mode", "value": "Late Morning",
                             "date": "2026-10-11T09:00:00+0100"},
                        ],
                    })
            return await super().call_tool(name, arguments)

    class Agent(UnifiedMCPAgent):
        async def _chat(self, messages, tools):
            self.chat_calls = getattr(self, "chat_calls", [])
            self.chat_calls.append((messages, tools))
            return {
                "role": "assistant",
                "content": (
                    "Livingroom Light 1 turned on at 12:00:03 because the "
                    "Lighting: livingroom low light app (3602) issued an ON "
                    "command. Configured sensor activity preceded it; the "
                    "exact internal condition remains unverified."
                ),
                "tool_calls": [],
            }

    mcp = MCP()
    agent = Agent(mcp, "key", "model", ai_client=_NoAIProvider(),
                  require_sensitive_confirmation=False)
    outcome = await agent.process_user_request_result(
        "Investigate thoroughly why Livingroom Light 1 turned on at 12:00:03 "
        "on 11 October. Check the controlling app, configured triggers, actual "
        "sensor events, app execution logs and possible alternative causes. Read-only."
    )
    assert "Lighting: livingroom low light" in outcome.message
    post_graph = build_causal_evidence_graph(outcome.evidence, (
        "Investigate thoroughly why Livingroom Light 1 turned on at 12:00:03 "
        "on 11 October. Check the controlling app, configured triggers, actual "
        "sensor events, app execution logs and possible alternative causes. Read-only."
    ))
    assert supports_one_pass_deep_synthesis(post_graph, (
        "Investigate thoroughly why Livingroom Light 1 turned on at 12:00:03 "
        "on 11 October. Check the controlling app, configured triggers, actual "
        "sensor events, app execution logs and possible alternative causes. Read-only."
    )), {"graph": post_graph, "mcp_calls": mcp.calls}
    assert len(agent.chat_calls) == 1, {"model": [bool(t) for _, t in agent.chat_calls]}
    assert agent.chat_calls[0][1] == []  # final synthesis, not tool planning
    assert any(
        "HOST STRUCTURED CAUSAL EVIDENCE GRAPH" in str(m.get("content") or "")
        for m in agent.chat_calls[0][0]
    )
    assert [(gateway, a["tool"]) for gateway, a in mcp.calls].count(
        ("hub_read_apps_code", "hub_get_app_config")
    ) == 1
    assert [(gateway, a["tool"]) for gateway, a in mcp.calls].count(
        ("hub_read_devices", "hub_list_device_events")
    ) >= 1
    assert outcome.metrics["counters"].get("causal_graph_sufficient") == 1
