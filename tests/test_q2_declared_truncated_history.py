"""Cross-domain regression for source-declared partial device history projections.

No live device calls, provider invocation or fabricated missing event rows.
A source summary count is not a substitute for observed event bodies.
"""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from mcp_agent_orchestrator import AgentOutcome
from shared_investigation_completion import apply_shared_investigation_completion
from typed_device_history_evidence import (
    normalize_target_device_history,
    render_target_device_evidence_brief,
    render_target_device_evidence_answer,
)


def packet(label="Test Relay", target="9911", reported=19, retained=16):
    events = [
        {
            "name": "deviceHealth", "value": "stale" if i % 2 else "unknown",
            "date": f"2026-11-03T01:{20 + i:02d}:00+00:00",
            "producedBy": {"id": target, "type": "device", "label": label},
        }
        for i in range(retained)
    ]
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "mutates": False, "effect": "read",
            "summary": "1 targeted device candidates",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": label, "detailed": True}},
            "details": {"reportedDeviceState": {
                "deviceId": target, "label": label,
                "source": "targeted-hubitat-device-state",
                "observedAt": "2026-11-03T02:00:00+00:00",
                "isPhysicalConnectivityProof": False,
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                    "dataAgeSeconds": "162325",
                },
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "mutates": False, "effect": "read",
            "timestamp": "2026-11-03T02:00:07.279697+00:00",
            "summary": f"{reported} device events for '{label}'",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": target, "hoursBack": 24,
                                   "limit": 20}},
        },
        {
            "tool": "homebrain_device_history", "sub_tool": None,
            "success": True, "mutates": False, "effect": "read",
            "timestamp": "2026-11-03T02:00:07.282473+00:00",
            "details": {
                "label": label, "hoursBack": 24,
                "observedEvents": events,
                "observedEventsTruncated": retained < reported,
                "sourceEventCount": reported,
                "analysisEventCount": reported,
                "historySourceIntegrityVerified": False,
            },
        },
    ]


def test_declared_partial_history_keeps_retained_rows_and_discloses_missing():
    for label, target in (("Test Relay", "9911"),
                          ("Heating Zone Plug", "9922"),
                          ("Fan Boost Plug", "9933")):
        source = packet(label, target)
        normalized = normalize_target_device_history(source)
        assert normalized is not None
        assert normalized["deviceId"] == target
        assert normalized["joinedDerivedHistory"] is True
        assert normalized["truncated"] is True
        assert normalized["returnedEvents"] == 16
        assert normalized["sourceReportedEventCount"] == 19
        assert normalized["unshownEventCount"] == 3
        assert normalized["stateEventCount"] == 16
        assert normalized["commandCount"] == 0
        assert normalized["sourceIntegrityVerified"] is False
        assert normalized["physicalCommunicationVerified"] is False
        short = render_target_device_evidence_brief(source, normalized)
        full = render_target_device_evidence_answer(source, normalized)
        for text in (short, full):
            assert "19" in text and "16" in text
            assert "omitted" in text
            assert "ghost connection" not in text.casefold()
            assert "actual telemetry" not in text.casefold()


def test_fail_closed_on_unattested_partial_rows_or_ambiguous_source():
    for edit in ("no_truncation", "no_source_count", "count_mismatch",
                 "analysis_mismatch", "wrong_window", "wrong_label",
                 "wrong_time", "wrong_target", "non_dict_row"):
        source = deepcopy(packet())
        derived = source[2]["details"]
        if edit == "no_truncation":
            derived["observedEventsTruncated"] = False
        elif edit == "no_source_count":
            derived.pop("sourceEventCount")
        elif edit == "count_mismatch":
            derived["sourceEventCount"] = 18
        elif edit == "analysis_mismatch":
            derived["analysisEventCount"] = 17
        elif edit == "wrong_window":
            derived["hoursBack"] = 48
        elif edit == "wrong_label":
            derived["label"] = "Different Device"
        elif edit == "wrong_time":
            source[2]["timestamp"] = "2026-11-03T02:01:00+00:00"
        elif edit == "wrong_target":
            source[1]["arguments"]["args"]["deviceId"] = "9955"
        elif edit == "non_dict_row":
            derived["observedEvents"][0] = None
        assert normalize_target_device_history(source) is None, edit
    duplicate = packet()
    duplicate.append(deepcopy(duplicate[2]))
    assert normalize_target_device_history(duplicate) is None


def test_untruncated_full_receipts_remain_accepted():
    source = packet(reported=16, retained=16)
    normalized = normalize_target_device_history(source)
    assert normalized is not None
    assert normalized["returnedEvents"] == 16
    assert normalized["truncated"] is False
    assert normalized["unshownEventCount"] is None


def test_shared_completion_replaces_unsupported_model_cause_using_partial_source():
    source = packet()
    outcome = AgentOutcome(
        message=(
            "The device is in a ghost connection state. The broker has an "
            "active TCP socket, and the physical plug is disconnected."
        ),
        request_class="live-read",
        evidence=source,
        choices=[],
        investigation_coverage={
            "domain": "device_telemetry", "evidenceComplete": False,
            "status": "partial-evidence",
            "hypothesisComparisonStatus":
                "model-proposed-source-checks-not-causal-verdicts",
            "hypothesisComparisons": [{
                "candidate": "endpoint stopped publishing",
                "discriminating_question": "are fresh packets present?",
                "hypothesis_verdict": "unverified",
            }],
        },
    )
    final = apply_shared_investigation_completion(
        outcome, "Why does Test Relay show MQTT connected when its health is offline?",
    )
    answer = final.message
    coverage = final.investigation_coverage
    assert "ghost connection state" not in answer.casefold()
    assert "active TCP socket" not in answer
    assert "physical plug is disconnected" not in answer
    assert "offline" in answer and "connected" in answer
    assert "19" in answer and "16" in answer
    assert coverage["rootCauseVerified"] is False
    assert coverage["questionResolved"] is False
    assert coverage["normalizedDeviceHistory"]["unshownEventCount"] == 3
    assert coverage["answerPublicationDecision"]["modelProseCertified"] is False
    assert coverage["answerPublicationDecision"]["physicalCauseCertified"] is False
