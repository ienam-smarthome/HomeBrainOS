"""Regression cases from v0.17.65 read-only live investigations."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from causal_command_provenance import (
    preceding_command_candidates,
    render_preceding_command_candidates,
)
from typed_device_history_evidence import reported_telemetry_consistency


def _command_receipt(label="Livingroom Light 1", when="2026-10-14T19:54:46.691+0100"):
    return {
        "success": True,
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "arguments": {"args": {"attribute": "command-on", "deviceId": "7805"}},
        "details": {
            "label": label,
            "eventName": "command-on",
            "events": [{
                "name": "command-on", "date": when,
                "description": "Command called: on()",
                "type": "command",
                "producedBy": {"label": "SenseCap D1 Settings", "id": "4129", "type": "app"},
            }],
        },
    }


def test_sensecap_command_is_preceding_candidate_not_verified_cause():
    boundary = "2026-10-14T19:55:00.049+0100"
    rows = preceding_command_candidates(
        [_command_receipt()], subject="Livingroom Light 1",
        transition="on", requested_boundary=boundary,
    )
    assert len(rows) == 1
    assert rows[0]["producer"]["label"] == "SenseCap D1 Settings"
    assert rows[0]["delaySeconds"] == 13.358
    assert rows[0]["evidenceClass"] == "preceding-command-candidate-not-cause"
    message = render_preceding_command_candidates(
        [_command_receipt()], subject="Livingroom Light 1",
        transition="on", requested_boundary=boundary,
    )
    assert "NOT VERIFIED INITIATORS" in message
    assert "13.358 seconds" in message


def test_candidate_rejects_wrong_subject_future_and_stale_commands():
    boundary = "2026-10-14T19:55:00.049+0100"
    receipts = [
        _command_receipt(label="Other Light"),
        _command_receipt(when="2026-10-14T19:55:01.000+0100"),
        _command_receipt(when="2026-10-14T19:53:00.000+0100"),
    ]
    assert preceding_command_candidates(
        receipts, subject="Livingroom Light 1",
        transition="on", requested_boundary=boundary,
    ) == []


def test_telemetry_reports_disagreeing_cached_attributes():
    reported = {
        "observedAt": "2026-10-15T12:42:57.586031+00:00",
        "reportedAttributes": {
            "lastSeen": "Mon Oct 12 01:30:01 BST 2026",
            "dataAgeSeconds": "162325",
            "healthStatus": "offline",
            "mqttStatus": "connected",
        },
    }
    finding = reported_telemetry_consistency(reported)
    assert finding is not None
    assert "disagree" in finding
    assert "neither establishes a fresh device-originated packet" in finding.lower()


def test_telemetry_agreement_and_missing_inputs_are_not_false_warnings():
    reported = {
        "observedAt": "2026-10-15T12:42:57+00:00",
        "reportedAttributes": {
            "lastSeen": "Thu Oct 15 13:40:00 BST 2026",
            "dataAgeSeconds": "177",
        },
    }
    assert reported_telemetry_consistency(reported) is None
    assert reported_telemetry_consistency({"reportedAttributes": {"healthStatus": "offline"}}) is None
