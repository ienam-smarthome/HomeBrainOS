"""Regression: source coverage and UK clock offsets outrank invented causal claims."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from historical_window_integrity import (
    requested_interval, incident_window_instruction,
    assess_retained_incident, calibrate_historical_incident_answer,
)
from shared_investigation_completion import apply_shared_investigation_completion

QUESTION = (
    "Why did Livingroom Light 1 stay ON from approximately 18:37 on "
    "24 October until 00:41 on 25 October 2026? Investigate what happened."
)
DRAFT = (
    "Confidence: Medium-High. The most likely reason is hub instability. "
    "No ON event was recorded, so App 4019 did not know the light was on "
    "and could not start its off timer."
)


def history_receipts(*, include_focal=False):
    rows = [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "evidence_kind": "targeted_device_lookup",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": "Livingroom Light 1"}},
            "details": {"reportedDeviceState": {
                "deviceId": "7805", "label": "Livingroom Light 1",
            }},
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "arguments": {"name": "Livingroom Light 1",
                          "attribute": "switch", "hours_back": 168},
            "details": {
                "label": "Livingroom Light 1", "attribute": "switch",
                "sourceEventCount": 11,
                "historySourceIntegrityVerified": False,
                "observedEventsTruncated": False,
                "observedEvents": [
                    {"name": "switch", "value": "off",
                     "date": "2026-10-25T01:09:41.835+0100"},
                    {"name": "switch", "value": "off",
                     "date": "2026-10-25T17:01:17.095+0000"},
                ],
            },
        },
    ]
    if include_focal:
        rows[1]["details"]["observedEvents"].append({
            "name": "switch", "value": "on",
            "date": "2026-10-24T18:37:15.000+0100",
        })
    return rows


def test_overnight_bst_range_converts_to_canonical_utc():
    begin, end = requested_interval(QUESTION)
    assert begin.isoformat() == "2026-10-24T17:37:00+00:00"
    assert end.isoformat() == "2026-10-24T23:41:00+00:00"
    guidance = incident_window_instruction(QUESTION)
    assert "since=2026-10-24T17:37:00Z" in guidance
    assert "until=2026-10-24T23:41:00Z" in guidance
    assert "target-scoped" in guidance


def test_different_uk_offsets_crossing_the_clock_change_are_ordered_by_instant():
    question = "from 23:50 on 24 October until 02:20 on 25 October 2026"
    begin, end = requested_interval(question)
    assert begin.isoformat() == "2026-10-24T22:50:00+00:00"
    assert end.isoformat() == "2026-10-25T02:20:00+00:00"


def test_ambiguous_repeated_local_hour_is_not_assigned_a_guess():
    assert requested_interval(
        "from 23:50 on 24 October until 01:30 on 25 October 2026"
    ) is None


def test_retention_window_rejects_false_absence_and_hub_failure_conclusion():
    rows = history_receipts()
    scope = assess_retained_incident(QUESTION, rows)
    assert scope["recordedSwitchRowsInWindow"] == 0
    assert scope["latestPageDoesNotReachWindow"] is True
    assert scope["absenceEstablished"] is False
    assert scope["oldestRetainedUtc"] == "2026-10-25T00:09:41.835000+00:00"
    response, supplied = calibrate_historical_incident_answer(
        QUESTION, rows, DRAFT, causal=True,
    )
    assert supplied == scope
    assert "Historical cause not established" in response
    assert "medium-high" not in response.casefold()
    assert "did not know the light" not in response
    assert "No automation or device was modified" in response


def test_positive_focal_observation_prevents_false_negative_override():
    rows = history_receipts(include_focal=True)
    response, scope = calibrate_historical_incident_answer(
        QUESTION, rows, "Observed event with limited interpretation.",
        causal=True,
    )
    assert response == "Observed event with limited interpretation."
    assert scope["recordedSwitchRowsInWindow"] == 1
    assert scope["latestPageDoesNotReachWindow"] is False


def test_target_matched_archived_focal_verification_is_preserved():
    rows = history_receipts()
    rows.append({
        "tool": "homebrain_evidence_journal", "success": True,
        "evidence_kind": "focal_archived_state_history",
        "details": {"deviceId": "7805", "sourceVerifiedOn": True},
    })
    response, _ = calibrate_historical_incident_answer(
        QUESTION, rows, "Archive-backed, qualified causal discussion.",
        causal=True,
    )
    assert response == "Archive-backed, qualified causal discussion."


def test_incidental_device_status_and_undated_queries_are_untouched():
    rows = history_receipts()
    assert requested_interval("Why is Livingroom Light 1 on?") is None
    assert calibrate_historical_incident_answer(
        QUESTION, rows, "Light is off now.", causal=False
    )[0] == "Light is off now."
    assert calibrate_historical_incident_answer(
        "Why is Livingroom Light 1 on?", rows, DRAFT, causal=True
    )[0] == DRAFT


def test_shared_api_boundary_cannot_publish_unverified_historical_verdict():
    outcome = SimpleNamespace(
        message=DRAFT, route="unified-mcp-agent", request_class="live-read",
        metrics={"outcome": "unresolved", "counters": {}},
        evidence=history_receipts(), investigation_coverage=None,
    )
    checked = apply_shared_investigation_completion(outcome, QUESTION)
    assert "Historical cause not established" in checked.message
    assert checked.metrics["outcome"] == "unresolved"
    assert checked.investigation_coverage["historicalWindowIntegrity"][
        "latestPageDoesNotReachWindow"
    ] is True
