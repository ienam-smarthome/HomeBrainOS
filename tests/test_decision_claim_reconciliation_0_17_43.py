"""Reusable evidence semantics: command, declared decision and actual effect.

The 0.17.42 live result quoted an app log declaring 'blocked for 300 min',
despite the user's three-minute target and without confirmed eligible motion
suppression. The API coverage did not classify the excerpt's claimed decision.
This test avoids app-specific wording as an execution validator.
"""
from __future__ import annotations

import json
from datetime import datetime

from decision_claim_reconciliation import (
    quantities, reconcile_decision_claims,
)
from final_answer_coordinator import _synthesis_instruction
from investigation_intelligence import plan_investigation, assess_investigation


OFF = datetime.fromisoformat("2026-10-12T22:49:27.529+00:00")
QUESTION = (
    "Investigate the latest manual OFF of Livingroom Light 1 followed by "
    "motion. Determine whether app 4019's three-minute motion lockout actually "
    "engaged. Reconstruct the event sequence. Read-only."
)


def _row(message, *, basis="requested-backend-filter-only", offset=True):
    return {
        "sourceRowId": "app-log-1",
        "appId": "4019",
        "scopeBasis": basis,
        "timestamp": (
            "2026-10-12T23:49:27.542+01:00" if offset
            else "2026-10-12 23:49:27.542"
        ),
        "message": message,
    }


def test_generic_unit_semantics_preserve_number_and_convert_to_seconds():
    assert quantities("three-minute motion lockout") == [
        {"value": 3, "unit": "minute", "seconds": 180}]
    assert quantities("motion turn-on blocked for 300 min") == [
        {"value": 300, "unit": "min", "seconds": 18000}]
    assert quantities("blocked for five hours") == [
        {"value": 5, "unit": "hours", "seconds": 18000}]
    assert quantities("delay 150 ms then retry after 30 sec") == [
        {"value": 150, "unit": "ms", "seconds": 0.15},
        {"value": 30, "unit": "sec", "seconds": 30}]


def test_live_duration_disagreement_and_declaration_not_effect():
    packet = reconcile_decision_claims(
        QUESTION, [_row("** motion turn-on blocked for 300 min (Button Controller toggle OFF)")],
        focal_off=OFF,
    )
    assert packet["schema"] == "decision-evidence-v1"
    assert packet["durationMismatchObserved"] is True
    assert packet["durationComparisons"] == [{
        "sourceRowId": "app-log-1",
        "requestedSeconds": 180,
        "reportedSeconds": 18000,
        "differenceSeconds": 17820,
        "matches": False,
    }]
    candidate = packet["logDeclarationCandidates"][0]
    assert candidate["timeFromFocalMs"] == 13
    assert candidate["evidenceLevel"] == "textual-declaration-only"
    assert candidate["sourceIdentity"] == "requested-backend-filter-only"
    assert candidate["effectiveActionProvenByThisRow"] is False
    assert packet["decisionStage"]["textualDecisionReported"] is True
    assert packet["decisionStage"]["textualReportSourceIndependentlyVerified"] is False
    assert packet["decisionStage"]["configuredDurationVerified"] is False
    assert packet["decisionStage"]["effectivelyPreventedActionVerified"] is False
    assert "Button Controller" not in json.dumps(packet)
    assert packet["containsPrivateLogContent"] is False


def test_explicit_app_id_and_matched_duration_still_not_effect_proof():
    packet = reconcile_decision_claims(
        QUESTION,
        [_row("motion turn-on blocked for 3 minutes", basis="explicit-app-id")],
        focal_off=OFF,
    )
    assert packet["durationMismatchObserved"] is False
    assert packet["decisionStage"]["textualReportSourceIndependentlyVerified"]
    assert not packet["decisionStage"]["effectivelyPreventedActionVerified"]


def test_unrelated_app_log_or_unstamped_candidate_cannot_prove_decision():
    no_declaration = reconcile_decision_claims(
        QUESTION, [_row("motionLockoutOffHandler entered; debug log")],
        focal_off=OFF,
    )
    assert no_declaration["durationMismatchObserved"] is None
    assert not no_declaration["decisionStage"]["textualDecisionReported"]
    no_offset = reconcile_decision_claims(
        QUESTION, [_row("motion turn-on blocked for 300 min", offset=False)],
        focal_off=OFF,
    )
    assert no_offset["logDeclarationCandidates"][0]["timeFromFocalMs"] is None
    assert no_offset["logDeclarationCandidates"][0]["timestampOffsetVerified"] is False


def test_generic_non_lighting_decision_quantity_conflict():
    packet = reconcile_decision_claims(
        "Did the watchdog wait five seconds before retrying?",
        [{"sourceRowId": "app-log-2", "scopeBasis": "explicit-app-id",
          "timestamp": "2026-10-12T23:49:27+01:00",
          "message": "watchdog retry blocked for 30 sec"}],
        focal_off=OFF,
    )
    assert packet["durationMismatchObserved"] is True
    assert packet["durationComparisons"][0]["reportedSeconds"] == 30


def test_public_coverage_exposes_conflict_not_private_log_or_execution_proof():
    reconciliation = reconcile_decision_claims(
        QUESTION, [_row("motion turn-on blocked for 300 min token=private123")],
        focal_off=OFF,
    )
    details = {
        "focalOff": OFF.isoformat(),
        "lockoutExecutionVerified": False,
        "decisionClaimReconciliation": reconciliation,
        "sources": [
            {"source": "bounded-light-device-history"},
            {"source": "bounded-app-execution-logs", "readSucceeded": True}
        ],
    }
    goal = plan_investigation(QUESTION)
    assert goal is not None
    coverage = assess_investigation(goal, [{
        "tool": "homebrain_motion_lockout_investigation",
        "success": True, "details": details,
    }])
    states = {x["key"]: x["state"] for x in coverage["requirements"]}
    assert states["target_off"] == "observed"
    assert states["execution"] == "checked-unverified"
    public = coverage["decisionClaimEvidence"]
    assert public["stage"]["textualDecisionReported"] is True
    assert not public["stage"]["effectivelyPreventedActionVerified"]
    assert public["durationMismatchObserved"] is True
    assert all("message" not in x for x in public["durationComparisons"])
    assert "private123" not in json.dumps(coverage)


def test_focal_investigation_synthesis_does_not_request_whole_day_usage_table():
    output = _synthesis_instruction(QUESTION)
    assert "Present the requested focal event" in output
    assert "daily light-on interval tables" in output
    assert "source-reported duration" in output
    assert "When several bounded intervals are available" not in output
