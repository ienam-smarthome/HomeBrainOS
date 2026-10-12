"""Separate ON/OFF provenance and stop OFF sensor timing from becoming a cause.

Uses an arbitrary light, synthetic controller and independent ON/OFF apps:
the same proof classes must work for lighting, switches and other devices.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_claim_verification import (  # noqa: E402
    guard_off_trigger_attribution, verify_causal_claims,
)
from causal_evidence_graph import build_causal_evidence_graph  # noqa: E402
from causal_transition_provenance import (  # noqa: E402
    focal_closed_transition, positive_off_command_already_recorded,
    scoped_off_history_receipt,
)
from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from test_causal_physical_event_0_17_12 import (  # noqa: E402
    _physical_evidence, QUESTION,
)


def _records(*, command=None, open_interval=False):
    records = copy.deepcopy(_physical_evidence())
    history = records[0]["details"]
    history["deviceId"] = "7840"
    original = history["temporalAnalysis"]["observedIntervals"][-1]
    if open_interval:
        original.pop("end", None)
        original["durationSeconds"] = None
    else:
        off_time = original["end"]
        observed_off = {
            "name": "switch", "value": "off",
            "date": off_time, "type": "physical",
            "producedBy": {
                "id": "7790", "label": "Example Matter Bridge",
                "type": "device",
            },
            "triggered": [
                {
                    "name": "Example Lighting Mode Controller",
                    "appId": 4015,
                    "handler": "lightSwitchHandler",
                },
                {
                    "name": "Example Telemetry",
                    "appId": 4129,
                    "handler": "liveDeviceEventHandler",
                },
            ],
        }
        history["boundaryEvents"].insert(0, observed_off)
    if command is not None:
        history["commandEvents"].append(command)
    return records


class _Recorder:
    def __init__(self, rows):
        self.rows = rows

    def receipts(self):
        return self.rows

    def record(self, tool, arguments, **kwargs):
        self.rows.append({
            "tool": tool, "sub_tool": arguments.get("tool"),
            "arguments": arguments, **kwargs,
        })


class _Tools:
    def available_tool(self, name):
        return object() if name in {
            "hub_read_devices", "hub_read_apps_code",
            "hub_read_diagnostics"
        } else None


class _MCP:
    def __init__(self, off_events=None, *, unavailable=False):
        self.calls = []
        self.off_events = off_events if off_events is not None else []
        self.unavailable = unavailable

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        action = arguments["tool"]
        if action == "hub_list_device_events":
            if self.unavailable:
                raise RuntimeError("OFF history currently unavailable")
            data = {"events": self.off_events}
        elif action == "hub_get_logs":
            data = {"logs": []}
        elif action == "hub_get_app_config":
            data = {
                "app": {
                    "id": arguments["args"]["appId"],
                    "label": "Another Rule",
                },
                "settings": {},
            }
        else:
            raise AssertionError(action)
        return SimpleNamespace(data=data)


async def _run(rows, mcp):
    records = _Recorder(rows)
    host = SimpleNamespace(
        evidence=records, mcp=mcp,
        _tool_succeeded=lambda result: True,
    )
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        await UnifiedMCPAgent._collect_focal_off_provenance(
            host, user_prompt=QUESTION, resolved_device_id="7840",
            catalog=_Tools(),
        )
        counters = metrics.snapshot()["counters"]
    finally:
        metrics.reset(token)
    return records.receipts(), counters


def test_focal_off_selection_is_unique_and_does_not_use_other_run():
    rows = _records()
    result = focal_closed_transition(rows, QUESTION)
    assert result["start"] == "2026-10-12T08:16:10.861+0100"
    assert result["end"] == "2026-10-12T08:18:23.830+0100"
    assert result["deviceId"] == "7840"
    assert result["offStateEvent"]["producedBy"]["type"] == "device"
    assert focal_closed_transition(rows, (
        "Why did Example Room Light turn on at 08:16 on 11 October?"
    )) is None
    assert focal_closed_transition(_records(open_interval=True), QUESTION) is None


@pytest.mark.asyncio
async def test_zero_off_history_proves_only_bounded_0_rows_and_scoped_listener_logs():
    records, counters = await _run(_records(), _MCP(off_events=[]))
    tools = [(name, args["tool"]) for name, args in _MCP_unused_calls(records)]
    assert ("hub_read_devices", "hub_list_device_events") in tools
    assert ("hub_read_diagnostics", "hub_get_logs") in tools
    graph = build_causal_evidence_graph(records, QUESTION)
    on = graph["transitionEvidence"]["on"]
    off = graph["transitionEvidence"]["off"]
    assert on["confidence"] == "strong-controller-association"
    assert on["directCommand"] is None
    assert off["observed"] is True
    assert off["commandHistory"]["checked"] is True
    assert off["commandHistory"]["result"] == "zero-recorded-command-off-events"
    assert off["directCommand"] is None
    assert off["status"] == "temporal-sensor-correlation-only"
    assert off["notifiedListenerContext"]["appId"] == "4015"
    assert off["notifiedListenerContext"]["executionLogs"]["result"] == "zero-observed-entries"
    assert off["appProducerContext"]["appId"] == ""
    assert off["internalTimerExecutionVerified"] is False
    assert off["externalAutomationIdentityVerified"] is False
    assert counters["causal_off_provenance_reads"] == 1
    assert counters["causal_off_app_log_reads"] == 1
    assert not positive_off_command_already_recorded(
        records, focal_closed_transition(records, QUESTION)
    )


def _MCP_unused_calls(rows):
    return [
        (row["tool"], row["arguments"])
        for row in rows
        if isinstance(row.get("arguments"), dict)
        and row.get("sub_tool") in {
            "hub_list_device_events", "hub_get_logs", "hub_get_app_config",
        }
    ]


@pytest.mark.asyncio
async def test_direct_off_command_producer_is_independent_of_on_and_has_own_context():
    app_command = {
        "name": "command-off",
        "date": "2026-10-12T08:18:23.710+0100",
        "description": "Command called: off()",
        "producedBy": {
            "id": "9001", "type": "app", "label": "Separate OFF Rule",
        },
    }
    records, counters = await _run(
        _records(), _MCP(off_events=[app_command]),
    )
    graph = build_causal_evidence_graph(records, QUESTION)
    on = graph["transitionEvidence"]["on"]
    off = graph["transitionEvidence"]["off"]
    assert on["directCommand"] is None
    assert off["directCommand"]["producer"]["id"] == "9001"
    assert off["status"] == "confirmed-direct-command-producer"
    assert off["appProducerContext"]["appId"] == "9001"
    assert off["appProducerContext"]["configuration"]["checked"]
    assert off["appProducerContext"]["executionLogs"]["checked"]
    assert not off["internalTimerExecutionVerified"]
    assert off["notifiedListenerContext"]["appId"] == "4015"
    assert not off["notifiedListenerContext"]["executionLogs"]["checked"]
    assert counters["causal_off_provenance_reads"] == 1
    assert counters["causal_off_app_config_reads"] == 1
    assert counters["causal_off_app_log_reads"] == 1


@pytest.mark.asyncio
async def test_positive_prefetched_off_command_is_reused_without_duplicate_history_read():
    app_command = {
        "name": "command-off",
        "date": "2026-10-12T08:18:23.710+0100",
        "description": "Command called: off()",
        "producedBy": {
            "id": "9001", "type": "app", "label": "Separate OFF Rule",
        },
    }
    mcp = _MCP()
    records, counters = await _run(
        _records(command=app_command), mcp,
    )
    assert not any(
        args["tool"] == "hub_list_device_events" for _, args in mcp.calls
    )
    assert counters["causal_off_command_reused"] == 1
    assert build_causal_evidence_graph(records, QUESTION)["offCommand"]["producer"]["id"] == "9001"


@pytest.mark.asyncio
async def test_failed_off_history_is_unknown_not_zero():
    records, counters = await _run(
        _records(), _MCP(unavailable=True),
    )
    off = build_causal_evidence_graph(records, QUESTION)["transitionEvidence"]["off"]
    assert off["directCommand"] is None
    assert off["commandHistory"]["result"] in {"unavailable", "not-checked"}
    assert off["commandHistory"]["result"] != "zero-recorded-command-off-events"
    assert counters["causal_off_provenance_reads"] == 1


def test_generic_off_causality_guard_rejects_likely_sensor_trigger_without_excluding_on():
    rows = _records()
    draft = (
        "The dimmer probably initiated the ON transition.\n"
        "| Likely | The turn-off was triggered by the motion sensor becoming inactive. |\n"
        "The OFF happened 69ms after sensor inactivity; this is temporally "
        "consistent but not independently verified."
    )
    fixed, changed = guard_off_trigger_attribution(
        draft, rows, QUESTION
    )
    assert changed
    assert "The dimmer probably initiated the ON transition." in fixed
    assert "sensor/timer trigger is unverified" in fixed
    assert "OFF command producer is unidentified" in fixed
    assert "| Likely |" in fixed
    assert "temporally consistent but not independently verified" in fixed
    fixed_again, changed_again = guard_off_trigger_attribution(
        fixed, rows, QUESTION
    )
    assert not changed_again
    assert fixed_again == fixed


def test_off_app_command_still_does_not_confirm_why_its_timer_ran():
    command = {
        "name": "command-off",
        "date": "2026-10-12T08:18:23.710+0100",
        "description": "Command called: off()",
        "producedBy": {
            "id": "9001", "type": "app", "label": "Separate OFF Rule",
        },
    }
    draft = "The switch-off was triggered by FP300 motion becoming inactive."
    result, changed = guard_off_trigger_attribution(
        draft, _records(command=command), QUESTION
    )
    assert changed
    assert "sensor/timer trigger is unverified" in result
    assert "producer is unidentified" not in result
    graph = build_causal_evidence_graph(_records(command=command), QUESTION)
    assert graph["transitionEvidence"]["off"]["status"] == "confirmed-direct-command-producer"


def test_insufficient_or_ambiguous_focal_off_does_not_invent_provenance():
    draft = "The light went off at 08:18 because motion stopped."
    fixed, issues = verify_causal_claims(draft, _records(open_interval=True), QUESTION)
    assert not issues
    assert fixed == draft
    rows = _records()
    rows[0]["details"]["temporalAnalysis"]["observedIntervals"].append({
        "start": "2026-10-12T08:16:45.000+0100",
        "end": "2026-10-12T08:19:00.000+0100",
        "durationSeconds": 135,
    })
    fixed, issues = verify_causal_claims(draft, rows, QUESTION)
    assert not issues and fixed == draft
