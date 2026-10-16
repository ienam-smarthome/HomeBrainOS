"""0.17.87 cross-domain tests from live incident/audit/telemetry outcomes."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
))

from incident_grounded_fallback import (
    is_open_ended_incident_request, render_grounded_incident_fallback,
)
from device_watchdog_evidence import summarize_device_watchdog, render_device_watchdog
from automation_diagnostic_policy import is_broad_automation_runtime_diagnostic
from typed_device_history_evidence import render_target_device_evidence_answer


PROMPT = (
    "Choose a recent unexpected device state change with sufficient "
    "recorded evidence. Reconstruct its timeline, investigate relevant "
    "controlling automations and sensors, evaluate competing causes, "
    "and explain the strongest supported conclusion. Read-only."
)


def _incident_evidence():
    return [
        {
            "tool": "hub_read_devices",
            "sub_tool": "hub_list_devices",
            "success": True, "evidence_kind": "targeted_device_lookup",
            "details": {
                "reportedDeviceState": {
                    "deviceId": "7804", "label": "Bedroom 2 Light",
                    "observedAt": "2026-10-16T13:48:19+00:00",
                    "reportedAttributes": {"switch": "on"},
                },
            },
        },
        {
            "tool": "homebrain_device_history",
            "success": True, "evidence_kind": "deterministic_device_event_history",
            "details": {
                "label": "Bedroom 2 Light",
                "historySourceIntegrityVerified": False,
                "observedEventsTruncated": True,
                "observedEvents": [
                    {
                        "name": "level", "value": "10",
                        "date": "2026-10-16T14:47:57.145+0100",
                        "isStateChange": True,
                        "producedBy": {
                            "label": "Matter Hue Bridge Pro", "id": "7790",
                            "type": "device"
                        },
                        "triggered": [
                            {"name": "SenseCap D1 Settings", "appId": 4129}
                        ],
                    },
                    {
                        "name": "switch", "value": "on",
                        "date": "2026-10-16T14:07:56.526+0100",
                        "isStateChange": True,
                        "producedBy": {
                            "label": "Matter Hue Bridge Pro", "id": "7790",
                            "type": "device"
                        },
                    },
                ],
            },
        },
    ]


def test_open_ended_device_mismatch_recovers_one_grounded_partial_history():
    assert is_open_ended_incident_request(PROMPT)
    result = render_grounded_incident_fallback(PROMPT, _incident_evidence())
    assert result is not None
    assert "Bedroom 2 Light (device 7804)" in result
    assert "2026-10-16T14:47:57.145+01:00" in result
    assert "level=10" in result
    assert "Matter Hue Bridge Pro" in result
    assert "Bedroom 2 Soft Sensor" not in result
    assert "not proof of the initiating controller" in result
    assert "incomplete" in result
    assert "SenseCap" not in result  # listeners are not origin proof


def test_explicitly_named_different_device_does_not_get_swapped():
    requested = "Why did Bedroom 2 Soft Sensor turn on?"
    assert not is_open_ended_incident_request(requested)
    assert render_grounded_incident_fallback(requested, _incident_evidence()) is None


def test_missing_identity_or_multiple_targets_do_not_give_speculative_fallback():
    evidence = _incident_evidence()
    assert render_grounded_incident_fallback(PROMPT, evidence[1:]) is None
    evidence.extend([
        {
            "tool": "hub_read_devices", "success": True,
            "evidence_kind": "targeted_device_lookup",
            "details": {"reportedDeviceState": {
                "deviceId": "7902", "label": "Different Light",
            }},
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "evidence_kind": "deterministic_device_event_history",
            "details": {
                "label": "Different Light",
                "observedEvents": [{
                    "name": "switch", "value": "off",
                    "date": "2026-10-16T12:00:01+01:00",
                    "isStateChange": True,
                }],
            },
        },
    ])
    assert render_grounded_incident_fallback(PROMPT, evidence) is None


@pytest.mark.parametrize("question", [
    "Investigate all my broken, incomplete, disabled or potentially faulty Hubitat automations. Check their configuration, required expressions, device dependencies, execution history and available logs. Identify specific problems, distinguish confirmed faults from suspected issues, and rank findings by severity. Read-only.",
    "Investigate all my broken, incomplete, disabled or potentially faulty Hubitat automations.",
    "Diagnose all my incomplete, disabled or faulty rules.",
])
def test_whole_automation_population_uses_comprehensive_audit(question):
    assert is_broad_automation_runtime_diagnostic(question)


@pytest.mark.parametrize("question", [
    "Why did Bedroom 2 Light turn on at 14:07? Check app 4016.",
    "Investigate why a single lighting rule did not fire at 08:00.",
    "Why did the bathroom light turn itself off?",
])
def test_named_incident_not_broad_automation_audit(question):
    assert not is_broad_automation_runtime_diagnostic(question)


def _log_receipt(device_id="7103"):
    rows = [
        (f"2026-10-16 14:{m}:57.434", gap)
        for m,gap in [("24",25688),("29",25994),("34",26296),
                       ("39",26628),("44",26930),("49",27232)]
    ]
    return {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {
            "tool": "hub_get_logs",
            "args": {"deviceId": device_id, "limit": 100},
        },
        "details": {
            "logCount": 51,
            "logs": [{
                "date": timestamp,
                "message": (
                    f"dev|{device_id}|Bedroom 3 Mesh|Bedroom 3 Mesh: "
                    f"Watchdog fired after {gap}s without data — reconnecting"
                ),
                "level": "WARN",
            } for timestamp,gap in rows] + [
                {
                    "date": "2026-10-16 14:48:00.000",
                    "message": "dev|7804|Different device: Watchdog fired after 80000s without data",
                },
            ],
        },
    }


def test_watchdog_summary_preserves_critical_pattern_and_scoped_identity():
    evidence = [_log_receipt()]
    summary = summarize_device_watchdog(evidence, "7103")
    assert summary is not None
    assert summary["sampledWarnings"] == 6
    assert summary["latestSecondsWithoutData"] == 27232
    assert summary["latestGapHours"] == pytest.approx(7.56, abs=.01)
    assert summary["oldestSecondsWithoutData"] == 25688
    assert summary["physicalCauseEstablished"] is False
    assert summary["recoveryConfirmed"] is False
    result = render_device_watchdog(summary)
    assert "27,232 seconds" in result
    assert "recovery attempts" in result
    assert "not successful reconnection" in result
    assert summarize_device_watchdog(evidence, "7804") is None
    assert summarize_device_watchdog([{
        **evidence[0], "success": False
    }], "7103") is None


def test_telemetry_answer_retains_logs_and_does_not_invent_commands():
    summary = {
        "deviceId": "7103", "deviceLabel": "Bedroom 3 Mesh",
        "queryWindowHours": 168, "returnedEvents": 16,
        "commandCount": 0, "stateEventCount": 16,
        "commandGroups": [], "latestReturnedStateEvent": {
            "attribute": "deviceHealth", "value": "unknown",
            "date": "2026-10-16T14:51:19+01:00",
            "producer": "Bedroom 3 Mesh",
        },
        "historicalDataAgeSeconds": None,
        "truncated": True,
    }
    result = render_target_device_evidence_answer([_log_receipt()], summary)
    assert "No command invocation was returned" in result
    assert "Command invocations are recorded" not in result
    assert "27,232 seconds" in result
    assert "7.56 hours" in result
    assert "older events" in result.lower()
