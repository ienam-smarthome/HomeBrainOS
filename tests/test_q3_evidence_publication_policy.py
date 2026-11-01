"""Cross-domain negative controls and source-typed publication policy tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai" / "rootfs" / "app"))

from answer_publication_policy import publish_source_typed_answer
from typed_device_history_evidence import (
    render_target_device_evidence_answer,
    render_target_device_evidence_brief,
)


def packet(label="Example socket", *, health="offline", mqtt="connected", count=11):
    return {
        "deviceId": "9911",
        "deviceLabel": label,
        "queryWindowHours": 24,
        "returnedEvents": count,
        "commandCount": 0,
        "stateEventCount": count,
        "commandGroups": [],
        "truncated": False,
        "historicalDataAgeSeconds": None,
        "latestReturnedStateEvent": {
            "attribute": "deviceHealth", "value": "unknown",
            "date": "2026-11-01T18:38:57+00:00",
            "producer": label,
        },
        "reportedDeviceState": {
            "deviceId": "9911", "label": label,
            "observedAt": "2026-11-01T18:43:03+00:00",
            "reportedAttributes": {
                "healthStatus": health, "mqttStatus": mqtt,
                "switch": "off",
            },
        },
    }


def publish(question, summary=None, clock=None):
    summary = packet() if summary is None else summary
    return publish_source_typed_answer(
        question,
        concise=lambda: render_target_device_evidence_brief([], summary, clock_check=clock),
        detailed=lambda: render_target_device_evidence_answer([], summary, clock_check=clock),
        normalized=summary,
        evidence_coverage={"normalizedDeviceHistory": summary},
    )


def test_concise_mode_keeps_verified_status_and_bounded_historical_scope():
    answer, decision = publish("Why do the connectivity and health values disagree?")
    assert decision["mode"] == "concise"
    assert decision["modelProseCertified"] is False
    assert decision["physicalCauseCertified"] is False
    assert decision["coverageReplaced"] is False
    assert "healthStatus=offline" in answer
    assert "mqttStatus=connected" in answer
    assert "11 events" in answer
    assert "0 command invocations" in answer
    assert "**Explanation:**" in answer
    assert "not verified" in answer
    assert "source-side last genuine" in answer
    assert "**Device-scoped logs:**" not in answer
    assert "Code ID " not in answer
    assert "physical device activity or a complete history" in answer
    assert len(answer.split()) < 230


def test_explicit_detailed_report_keeps_full_standalone_renderer():
    summary = packet()
    brief, brief_mode = publish("Why does this device report offline?", summary)
    full, detail_mode = publish("Give the full technical report for this incident.", summary)
    assert detail_mode["mode"] == "requested-detail"
    assert full == render_target_device_evidence_answer([], summary)
    assert "**Device-scoped logs:**" in full
    assert "**History integrity:**" in full
    assert len(brief.split()) < len(full.split())
    assert brief_mode["mode"] == "concise"


def test_other_technical_query_does_not_silently_trigger_exhaustive_mode():
    _, decision = publish("Why might the broker keep a connection while device is offline?")
    assert decision["mode"] == "concise"
    _, decision = publish("List every event row for this device.")
    assert decision["mode"] == "requested-detail"


def test_clock_conflict_printed_once_and_not_turned_into_packet_timestamp():
    summary = packet()
    summary["reportedDeviceState"]["reportedAttributes"].update({
        "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
        "dataAgeSeconds": "162325",
    })
    clock = {
        "sourcesAgree": False, "metadataAgeHoursAtRead": 498.2,
        "reportedDataAgeHours": 45.1,
        "physicalTelemetryProven": False,
    }
    msg, decision = publish("Explain device connectivity", summary, clock)
    assert decision["mode"] == "concise"
    assert msg.count("**Telemetry timing conflict:**") == 1
    assert msg.index("**Telemetry timing conflict:**") < msg.index("**Latest returned state event:**")
    assert "**Telemetry consistency:**" not in msg
    assert "498.2 hours" in msg
    assert "45.1 hours" in msg
    assert "physical device packet" in msg


def test_mqtt_absent_and_non_socket_status_generalize_without_layer_assumptions():
    summary = packet("Anonymised fan controller", health="stale", mqtt="")
    msg, decision = publish("Investigate reported fan status.", summary)
    assert decision["mode"] == "concise"
    assert "Anonymised fan controller" in msg
    assert "healthStatus=stale" in msg
    assert "mqttStatus=" not in msg
    assert "driver/broker connection" not in msg
    assert "device-originated telemetry" in msg
    assert "physical" in msg


def test_missing_health_never_invents_offline_status():
    summary = packet("Different integration", health="", mqtt="")
    msg, _ = publish("Why is this thing unreachable?", summary)
    assert "reports healthStatus=offline" not in msg
    assert "do not independently establish current physical connectivity" in msg
    assert "outage" not in msg or "any communication failure" in msg


def test_typed_decision_fail_closed_on_missing_source_coverage_or_target():
    summary = packet()
    with pytest.raises(ValueError, match="requires coverage"):
        publish_source_typed_answer(
            "Why?", concise=lambda: "anything", detailed=lambda: "details",
            normalized=summary, evidence_coverage=None,
        )
    with pytest.raises(ValueError, match="resolved target"):
        publish_source_typed_answer(
            "Why?", concise=lambda: "anything", detailed=lambda: "details",
            normalized={}, evidence_coverage={},
        )
    with pytest.raises(ValueError, match="cannot be empty"):
        publish_source_typed_answer(
            "Why?", concise=lambda: "", detailed=lambda: "detailed",
            normalized=summary, evidence_coverage={},
        )
