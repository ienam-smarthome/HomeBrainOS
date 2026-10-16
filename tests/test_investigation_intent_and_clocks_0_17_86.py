"""Live v0.17.85 cross-domain failures, generalized intent and evidence guards."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] /
           "hubitat-mcp-ai" / "rootfs" / "app")
)

from contextual_read_fast_path import parse_device_selection
from automation_diagnostic_policy import (
    has_broad_automation_scope,
    is_broad_automation_runtime_diagnostic,
)
from shared_investigation_completion import apply_shared_investigation_completion
from telemetry_clock_consistency import (
    assess_telemetry_clock_consistency, render_telemetry_clock_qualification,
)


OPEN_ENDED = (
    "Choose a recent unexpected device state change with sufficient recorded "
    "evidence. Reconstruct its timeline, investigate relevant controlling "
    "automations and sensors, evaluate competing causes, and explain the "
    "strongest supported conclusion. Read-only."
)


@pytest.mark.parametrize("question", [
    OPEN_ENDED,
    "Choose a recent device state change",
    "Select a motion sensor to investigate",
    "Choose an incident from the historical journal",
    "Select a recent event. Explain why it happened.",
    "Use the device that has been offline longest, and diagnose it",
    "Choose an app to inspect",
])
def test_open_ended_selection_is_not_target_resolution(question):
    assert parse_device_selection(question) is None


@pytest.mark.parametrize(("question", "device"), [
    ("Choose the Hallway Light 1", "Hallway Light 1"),
    ("Select Bedroom 3 Mesh", "Bedroom 3 Mesh"),
    ("Use the Livingroom TRV", "Livingroom TRV"),
    ("I mean Bedroom 1 Light", "Bedroom 1 Light"),
    ("Choose the Hallway FP300", "Hallway FP300"),
])
def test_explicit_device_choice_still_supported(question, device):
    assert parse_device_selection(question) == device


@pytest.mark.parametrize("question", [
    "Investigate my broken or incomplete Hubitat automations. Identify faults and logs. Read-only.",
    "Diagnose all paused or failed automations and rank them.",
    "Audit my installed and disabled rules.",
])
def test_broad_fault_scope_enters_comprehensive_audit(question):
    assert has_broad_automation_scope(question)
    assert is_broad_automation_runtime_diagnostic(question)


@pytest.mark.parametrize("question", [
    "Investigate why Livingroom Light 1 turned on yesterday; check automations.",
    "Why did my kitchen light turn on at 19:55? Check the rule.",
    "Investigate a broken rule 3602",
])
def test_single_subject_forensics_not_whole_hub_audit(question):
    assert not is_broad_automation_runtime_diagnostic(question)


def _receipt(*, last_seen="Mon Oct 12 01:30:01 BST 2026",
             age="162325", observed="2026-10-16T12:03:30+00:00",
             status="connected"):
    return [{
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_devices",
        "success": True,
        "effect": "read",
        "evidence_kind": "targeted_device_lookup",
        "arguments": {"tool": "hub_list_devices",
                      "args": {"labelFilter": "Bedroom 3 Mesh"}},
        "details": {
            "reportedDeviceState": {
                "deviceId": "7103",
                "label": "Bedroom 3 Mesh",
                "observedAt": observed,
                "reportedAttributes": {
                    "mqttStatus": status,
                    "lastSeen": last_seen,
                    "dataAgeSeconds": age,
                },
            },
        },
    }]


def test_bedroom_mesh_live_clock_discrepancy_detected():
    value = assess_telemetry_clock_consistency(_receipt())
    assert value is not None
    assert value["sourcesAgree"] is False
    assert value["metadataAgeHoursAtRead"] > 100
    assert value["reportedDataAgeHours"] == pytest.approx(45.1, abs=.1)
    assert value["physicalPowerProvenByMqttStatus"] is False
    description = render_telemetry_clock_qualification(value)
    assert "disagree" in description
    assert "powered" in description


def test_clock_agreement_and_malformed_values_not_overclaimed():
    consistent = assess_telemetry_clock_consistency(_receipt(age="387209"))
    assert consistent is not None
    assert consistent["sourcesAgree"] is True
    assert consistent["physicalTelemetryProven"] is False
    assert assess_telemetry_clock_consistency(_receipt(last_seen="unknown")) is None
    assert assess_telemetry_clock_consistency(_receipt(age="not a number")) is None
    assert assess_telemetry_clock_consistency(_receipt(observed="not-a-date")) is None


def test_shared_api_completion_keeps_conflicting_time_sources_visible():
    prior = SimpleNamespace(
        request_class="live-read",
        message=("Conclusion: device likely powered on because MQTT is connected"),
        evidence=_receipt(),
        investigation_coverage=None,
        metrics={"outcome": "success", "counters": {}},
        choices=[],
        confirmation_required=False,
        confirmation_count=0,
    )
    result = apply_shared_investigation_completion(
        prior, "Diagnose why Bedroom 3 Mesh is not reporting device telemetry"
    )
    assert result.investigation_coverage["telemetryClockConsistency"]["sourcesAgree"] is False
    assert "Telemetry timing conflict" in result.message
    assert "reported MQTT 'connected' status alone" in result.message
    assert result.metrics["outcome"] == "unresolved"


def test_broker_connection_is_not_power_proof_even_without_clock_disagreement():
    value = assess_telemetry_clock_consistency(_receipt(age="387209"))
    assert value["physicalPowerProvenByMqttStatus"] is False
    assert "does not verify" not in str(value)  # structured flags, no invented certainty
