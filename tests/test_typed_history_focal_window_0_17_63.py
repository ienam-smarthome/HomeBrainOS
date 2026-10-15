"""v0.17.63 regressions from the 15 October live evidence samples."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from typed_device_history_evidence import (
    normalize_target_device_history,
    render_target_device_evidence_answer,
)
from shared_investigation_completion import apply_shared_investigation_completion
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent
from request_metrics import RequestMetrics
import mcp_agent_orchestrator as host_module
from test_causal_windowed_source_0_17_21 import (
    _MCP, _Executor, _Evidence, _Catalogue,
)


def mixed_history(*, target="7103", state=True, truncated=True):
    events = [{
        "name": "command-on", "type": "command",
        "date": "2026-10-15T10:44:05.781+0100",
        "producedBy": {
            "appId": 3103,
            "name": "Ikea Rodret Dimmer (room 3): button 2 pushed",
        },
    } for _ in range(12)]
    events += [{
        "name": "command-refresh", "type": "command",
        "date": "2026-10-15T06:00:04.237+0100",
        "producedBy": {"appId": 4072, "name": "Device Health Monitor"},
    } for _ in range(3)]
    if state:
        events.append({
            "name": "mqttStatus", "value": "connected",
            "date": "2026-10-13T22:35:38.773+0100",
            "isStateChange": True,
            "producedBy": {"name": "Bedroom 3 Mesh", "deviceId": "7103"},
        })
    return [{
        "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
        "success": True, "summary": "1 targeted device candidates",
        "arguments": {
            "tool": "hub_list_devices",
            "args": {"labelFilter": "Bedroom 3 Mesh"},
        },
    }, {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "success": True, "timestamp": "2026-10-15T09:53:41.799+00:00",
        "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": target, "hoursBack": 168, "limit": 100},
        },
        "details": {
            "attribute": None, "label": None,
            "hoursBack": 168, "observedEvents": events,
            "observedEventsTruncated": truncated,
        },
    }]


def test_mixed_history_retains_historical_state_without_proving_connectivity():
    sample = mixed_history()
    summary = normalize_target_device_history(sample)
    assert summary is not None
    assert summary["deviceId"] == "7103"
    assert summary["deviceLabel"] == "Bedroom 3 Mesh"
    assert summary["returnedEvents"] == 16
    assert summary["commandCount"] == 15
    assert summary["stateEventCount"] == 1
    assert summary["latestReturnedStateEvent"]["date"].startswith("2026-10-13T22:35")
    assert summary["latestReturnedStateEvent"]["deviceAttributed"]
    assert summary["physicalCommunicationVerified"] is False
    assert summary["acknowledgementVerified"] is False
    assert summary["truncated"] is True
    answer = render_target_device_evidence_answer(sample, summary)
    assert "Device Health Monitor" in answer
    assert "Ikea Rodret Dimmer" in answer
    assert "historical" not in answer or "history" in answer
    assert "not independent proof" in answer
    assert "no device-attributed" not in answer.lower() or "no device-attributed state events" not in answer
    assert "unresponsive" not in answer
    assert "physically non-functional" not in answer
    assert "stale since Oct 12" not in answer
    assert "for device 7103" in answer


def test_direct_mixed_event_receipt_replaces_unverified_model_conclusion():
    evidence = mixed_history()
    evidence.append({
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True, "arguments": {
            "tool": "hub_get_logs", "args": {"pattern": "Bedroom 3 Mesh"},
        }, "details": {"logCount": 10},
    })
    original = AgentOutcome(
        message=(
            "The device is currently non-functional and unresponsive. "
            "Telemetry stopped on October 12. Command-response failure "
            "was confirmed by the absence of acknowledgments."
        ),
        request_class="live-read", evidence=evidence, choices=[],
    )
    response = apply_shared_investigation_completion(
        original,
        "Investigate Bedroom 3 Mesh current health, last telemetry activity "
        "and device logs. Read-only.",
    )
    assert response.investigation_coverage["answerProjection"] == (
        "target-scoped-mixed-event-evidence"
    )
    assert response.investigation_coverage["normalizedDeviceHistory"][
        "stateEventCount"
    ] == 1
    assert response.metrics["outcome"] == "unresolved"
    assert response.metrics["counters"]["typed_device_history_projections"] == 1
    assert "unresponsive" not in response.message
    assert "Telemetry stopped" not in response.message
    assert "command delivery" in response.message
    assert "No verified log read filtered to this" in response.message
    assert "truncated" in response.message


def test_scoping_rejects_other_devices_and_attribute_only_pages():
    rows = mixed_history()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
        "success": True,
        "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "9999", "hoursBack": 168},
        },
        "details": {"observedEvents": [{"name": "switch", "value": "on"}]},
    })
    assert normalize_target_device_history(rows) is None
    rows[-1]["arguments"]["args"]["deviceId"] = "7103"
    rows[-1]["arguments"]["args"]["attribute"] = "switch"
    summary = normalize_target_device_history(rows)
    assert summary is not None and summary["returnedEvents"] == 16
    rows[-1]["details"]["deviceId"] = "9999"
    assert normalize_target_device_history(rows) is not None


def test_a_command_only_direct_page_is_also_projected():
    summary = normalize_target_device_history(mixed_history(state=False))
    assert summary is not None
    assert summary["stateEventCount"] == 0
    rendered = render_target_device_evidence_answer(
        mixed_history(state=False), summary,
    )
    assert "No state or attribute event was found" in rendered
    assert "not proof that physical telemetry never arrived" in rendered


@pytest.mark.asyncio
async def test_historical_on_attempts_at_most_two_focal_sensor_windows(
    monkeypatch,
):
    sensors = [
        {"name": name, "attribute": "motion",
         "candidate": {"id": identifier, "label": name, "room": "Example"}}
        for identifier, name in [
            ("123", "Room sensor"), ("124", "Second sensor"),
        ]
    ]
    monkeypatch.setattr(
        host_module.DeviceQueryService,
        "cached_room_event_source_hints",
        staticmethod(lambda *args, **kwargs: [{"name": "Room sensor"}]),
    )
    monkeypatch.setattr(
        host_module, "controller_history_candidates", lambda *a, **k: [],
    )
    monkeypatch.setattr(
        host_module, "trigger_sensor_history_candidates", lambda *a, **k: sensors,
    )
    monkeypatch.setattr(
        host_module, "prioritize_known_automation_sensor_candidates",
        lambda pool, *a, **k: (pool[:2], False),
    )
    mcp = _MCP(window_supported=False)
    recorder = _Evidence()
    host = SimpleNamespace(
        mcp=mcp, evidence=recorder, executor=_Executor(),
        known_automations=[], _tool_succeeded=lambda result: not result.is_error,
    )
    history = {
        "label": "Example Light", "deviceId": "100", "room": "Example",
        "correlationEvents": [{
            "name": "switch", "value": "on",
            "date": "2026-10-12T08:18:23.830+0100",
        }],
    }
    metric = RequestMetrics()
    token = metric.begin()
    try:
        await UnifiedMCPAgent._collect_reporting_source_secondary_correlation(
            host, subject_history=history, transition="on",
            boundary_match={
                "stateBoundary": "2026-10-12T08:18:23.830+0100",
            },
            explicit_historical_focus=True,
            catalog=_Catalogue(), completed_calls=set(),
        )
        counters = metric.snapshot()["counters"]
    finally:
        metric.reset(token)
    direct = [
        call for call in mcp.calls
        if call["tool"] == "hub_list_device_events"
    ]
    assert len(direct) == 2
    assert all("since" in call["args"] and "until" in call["args"]
               for call in direct)
    assert counters.get("causal_focal_window_reads") == 2
    correlation = next(
        row["details"] for row in recorder.records
        if row["tool"] == "homebrain_causal_secondary_correlation"
    )
    assert correlation["discoveryCoverage"]["outsideRoomAttempted"] == 0
    assert all(
        row["status"] == "unsupported-or-unverified-window"
        for row in correlation["focalWindowRetrieval"]
    )
