"""0.17.32: do not discard archived sensor evidence when MCP windows are empty.

Regression for 12-Oct Bedroom 1 Light: two verified native MCP windows returned
zero records, while HomeBrain's SQLite archive retained four sensor changes.
"""
from __future__ import annotations

from copy import deepcopy

from causal_evidence_graph import build_causal_evidence_graph
from causal_claim_verification import verify_causal_claims
from focal_evidence_reconciliation import (
    reconcile_focal_archived_sensor_evidence,
    guard_sensor_history_source_contradiction,
)
from test_independent_transition_provenance_0_17_15 import _records


OFF = "2026-10-12T08:18:23.830+0100"
QUESTION = (
    "Investigate why Example Room Light switched OFF at 08:18:23 "
    "on 12 October 2026. Read-only."
)


def assembled_receipts():
    evidence = _records()
    evidence.append({
        "tool": "homebrain_causal_secondary_correlation",
        "success": True,
        "arguments": {"subject": "Example Room Light", "transition": "off"},
        "details": {
            "subject": "Example Room Light",
            "transition": "off",
            "requestedBoundary": OFF,
            "localSensorHistoryCoverage": {
                "upstreamHistoricalWindowAvailable": True,
                "historicalCompletenessVerified": False,
            },
            "focalWindowRetrieval": [
                {"deviceId": "7774", "status": "verified-window", "eventCount": 0},
                {"deviceId": "7756", "status": "verified-window", "eventCount": 0},
            ],
            "historicalJournal": {
                "status": "partial-archive-not-causal-proof",
                "historicalCompletenessVerified": False,
                "sensors": [
                    {
                        "deviceId": "7774", "label": "Example FP300",
                        "attribute": "motion", "eventCount": 2,
                        "gapCount": 0,
                        "events": [
                            {"value": "inactive",
                             "observedAt": "2026-10-12T07:18:24.835+00:00",
                             "timestampBasis": "collector-received"},
                            {"value": "active",
                             "observedAt": "2026-10-12T07:19:40.100+00:00",
                             "timestampBasis": "collector-received"},
                        ],
                    },
                    {
                        "deviceId": "7756", "label": "Example Soft Sensor",
                        "attribute": "motion", "eventCount": 2,
                        "gapCount": 0,
                        "events": [
                            {"value": "inactive",
                             "observedAt": "2026-10-12T07:18:25.892+00:00",
                             "timestampBasis": "collector-received"},
                            {"value": "active",
                             "observedAt": "2026-10-12T07:19:40.900+00:00",
                             "timestampBasis": "collector-received"},
                        ],
                    },
                ],
            },
            "sensors": [],
        },
    })
    return evidence


def test_actual_archived_observations_are_preserved_as_partial_evidence():
    receipts = assembled_receipts()
    result = reconcile_focal_archived_sensor_evidence(
        receipts, subject="Example Room Light", off_time=OFF,
    )
    assert result["archivedObservationCount"] == 4
    assert result["verifiedMcpWindowCount"] == 2
    assert result["verifiedMcpReturnedEventCount"] == 0
    assert result["archiveCoverageComplete"] is False
    assert result["mcpEmptyDoesNotNegateArchivedObservations"] is True
    assert result["notProofOfTimerOrOffCommand"] is True
    events = result["observations"]
    assert {e["deviceId"] for e in events} == {"7774", "7756"}
    assert all(e["timestampBasis"] == "collector-received" for e in events)
    assert all(e["deltaRepresentsOriginalEventOrdering"] is False for e in events)
    assert events[0]["receptionDeltaFromOffMs"] == 1005.0
    assert events[1]["receptionDeltaFromOffMs"] == 2062.0


def test_focal_graph_retains_both_distinct_sources_without_proving_off_actor():
    graph = build_causal_evidence_graph(assembled_receipts(), QUESTION)
    off = graph["transitionEvidence"]["off"]
    assert off["archivedSensorEvidence"]["archivedObservationCount"] == 4
    assert off["archivedSensorEvidence"]["verifiedMcpReturnedEventCount"] == 0
    assert off["directCommand"] is None
    assert off["internalTimerExecutionVerified"] is False
    assert off["externalAutomationIdentityVerified"] is False


def test_final_answer_cannot_equate_zero_native_rows_with_zero_sensor_history():
    wrong = (
        "* **Sensor Correlation**: **Incomplete**. Bounded history for the "
        "**Example FP300 sensor** and **Example Soft Sensor** showed no "
        "events during the focal window. Because the returned history was "
        "incomplete, no cause can be established."
    )
    answer, issues = verify_causal_claims(
        wrong, assembled_receipts(), QUESTION
    )
    assert "no sensor event rows" in answer
    assert "Historical Journal retained 4 partial sensor observations" in answer
    assert "collector reception" in answer.lower()
    assert "neither an OFF producer nor a timer execution is proven" in answer
    assert "archived_sensor_not_absent" in issues


def test_correct_source_contrast_and_wrong_focal_boundary_are_untouched():
    receipts = assembled_receipts()
    correct = (
        "Verified MCP sensor windows returned zero rows, but the Historical "
        "Journal retained four partial events, whose timestamps reflect "
        "collector receipt rather than original device event time."
    )
    graph = build_causal_evidence_graph(receipts, QUESTION)
    assert guard_sensor_history_source_contradiction(correct, graph) == (
        correct, False
    )
    other = reconcile_focal_archived_sensor_evidence(
        receipts, subject="Example Room Light",
        off_time="2026-10-12T15:58:11.531+0100",
    )
    assert not other
