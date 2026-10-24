"""0.18.98: distinguish causal timer clues from observed physical packets.

Replay a live same-device watchdog/MQTT counter correlation without assuming
that software counter zero means last physical telemetry. All tests are
read-only and use synthetic MCP receipts, never a live Hubitat.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from device_watchdog_evidence import (
    correlate_elapsed_watchdog_with_device_events,
    render_elapsed_watchdog_correlation,
)
from incident_reasoning_depth import assess_incident_reasoning_depth
from typed_device_history_evidence import render_target_device_evidence_answer
from shared_investigation_completion import apply_shared_investigation_completion

QUESTION = "Why is Bedroom 3 Mesh offline when MQTT says connected?"


def read(tool, arguments, details=None, *, successful=True):
    return {
        "tool": "hub_read_diagnostics" if tool == "hub_get_logs" else "hub_read_devices",
        "sub_tool": tool,
        "arguments": {"tool": tool, "args": arguments},
        "success": successful,
        "supports_live_claim": successful,
        "mutates": False, "effect": "read",
        "evidence_kind": "tool_result",
        "details": details or {},
    }


def live_fixture():
    return [
        {
            **read("hub_list_devices", {"labelFilter": "Bedroom 3 Mesh"}, {
                "reportedDeviceState": {
                    "deviceId": "7103", "label": "Bedroom 3 Mesh",
                    "observedAt": "2026-10-24T14:49:09.277432+00:00",
                    "reportedAttributes": {
                        "healthStatus": "offline", "mqttStatus": "connected",
                        "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
                        "dataAgeSeconds": "162325",
                    },
                },
            }),
            "evidence_kind": "targeted_device_lookup",
        },
        read("hub_list_device_events", {"deviceId": "7103", "hoursBack": 24}, {
            "observedEventsTruncated": False,
            "historySourceIntegrityVerified": False,
        }),
        {
            **read("homebrain_device_history", {"name": "Bedroom 3 Mesh"}, {
                "label": "Bedroom 3 Mesh",
                "hoursBack": 24,
                "analysisEventCount": 2, "sourceEventCount": 2,
                "observedEvents": [
                    {
                        "name": "mqttStatus", "value": "connected",
                        "date": "2026-10-23T19:48:42.942+0100",
                        "producedBy": {"id": "7103", "label": "Bedroom 3 Mesh"},
                    },
                    {
                        "name": "mqttStatus", "value": "disconnected",
                        "date": "2026-10-23T19:48:37.109+0100",
                        "producedBy": {"id": "7103", "label": "Bedroom 3 Mesh"},
                    },
                ],
                "historySourceIntegrityVerified": False,
            }),
            "evidence_kind": "deterministic_device_event_history",
        },
        read("hub_get_logs", {"deviceId": "7103", "since": "24h"}, {
            "logCount": 44,
            "logs": [
                {
                    "date": "2026-10-24 15:46:55.109",
                    "message": "dev|7103|Bedroom 3 Mesh|Watchdog fired after 71898s without data — reconnecting",
                },
                {
                    "date": "2026-10-24 15:41:53.130",
                    "message": "dev|7103|Bedroom 3 Mesh|Watchdog fired after 71596s without data — reconnecting",
                },
                {
                    "date": "2026-10-24 14:11:17.410",
                    "message": "dev|7103|Bedroom 3 Mesh|Watchdog fired after 66160s without data — reconnecting",
                },
            ],
        }),
        read("hub_get_source", {"type": "driver", "id": "3686"}, {
            "sourceRetrieved": True, "sourceCodeId": "3686",
            "offset": 0, "chunkLength": 20531, "totalLength": 20531,
        }),
        read("hub_get_device_health", {"pingHosts": ["192.168.1.136"]}),
    ]


def test_same_device_elapsed_counter_aligns_with_mqtt_disconnect():
    match = correlate_elapsed_watchdog_with_device_events(live_fixture(), "7103")
    assert match is not None
    assert match["referenceTimeLocal"].startswith("2026-10-23 19:48:37.")
    assert match["matchingEvent"]["attribute"] == "mqttStatus"
    assert match["matchingEvent"]["value"] == "disconnected"
    assert match["sampledDistinctWarningTimes"] == 3
    assert match["referenceSpreadSeconds"] < 1
    assert match["differenceSeconds"] < 1
    assert match["rootCauseVerified"] is False
    assert match["devicePacketTimeVerified"] is False
    rendered = render_elapsed_watchdog_correlation(match)
    assert "software watchdog reference" in rendered
    assert "does NOT verify" in rendered


def test_no_other_device_or_mismatched_counter_can_create_alignment():
    assert correlate_elapsed_watchdog_with_device_events(live_fixture(), "9999") is None
    evidence = live_fixture()
    evidence[2]["details"]["observedEvents"][1]["producedBy"]["id"] = "9999"
    assert correlate_elapsed_watchdog_with_device_events(evidence, "7103") is None
    evidence = live_fixture()
    evidence[3]["details"]["logs"][0]["message"] = (
        "dev|7103|Bedroom 3 Mesh|Watchdog fired after 70100s without data"
    )
    assert correlate_elapsed_watchdog_with_device_events(evidence, "7103") is None


def test_driver_source_retrieval_and_ping_probe_do_not_prove_cause():
    depth = assess_incident_reasoning_depth(live_fixture(), "7103")
    assert depth["driverSourceRetrieved"] is True
    assert depth["driverMethodBehaviourVerified"] is False
    assert depth["controllingAppLinkVerified"] is False
    assert depth["independentUpstreamObservationRetained"] is False
    assert depth["upstreamProbeAttempted"] is True
    assert not depth["keyDiscriminatorsCovered"]
    assert not depth["rootCauseEstablishedByThisAssessment"]


def test_safe_device_summary_includes_correlation_without_physical_verdict():
    summary = {
        "deviceId": "7103", "deviceLabel": "Bedroom 3 Mesh",
        "queryWindowHours": 24, "returnedEvents": 2,
        "commandCount": 0, "stateEventCount": 2,
        "latestReturnedStateEvent": None,
        "reportedDeviceState": live_fixture()[0]["details"]["reportedDeviceState"],
        "historicalDataAgeSeconds": None,
        "commandGroups": [],
        "truncated": False,
    }
    text = render_target_device_evidence_answer(live_fixture(), summary)
    assert "**Watchdog timing correlation:**" in text
    assert "mqttStatus=disconnected" in text
    assert "does NOT verify" in text


def test_final_coverage_separates_standard_source_checks_from_causal_depth():
    outcome = SimpleNamespace(
        message="MCP investigated the offline device.",
        route="unified-mcp-agent", request_class="live-read",
        evidence=live_fixture(), metrics={"outcome": "unresolved", "counters": {}},
        investigation_coverage=None,
    )
    result = apply_shared_investigation_completion(outcome, QUESTION)
    coverage = result.investigation_coverage
    assert coverage["domain"] == "device_telemetry"
    assert coverage["watchdogEventTimingCorrelation"]["matchingEvent"]["value"] == "disconnected"
    assert coverage["incidentReasoningDepth"]["driverSourceRetrieved"]
    assert not coverage["incidentReasoningDepth"]["keyDiscriminatorsCovered"]
    assert coverage["status"] == "partial-evidence"
    assert "not source-traced" in result.message
    assert "19:48:37" in result.message
