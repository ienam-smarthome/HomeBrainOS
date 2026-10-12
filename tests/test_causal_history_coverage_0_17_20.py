"""Focal history coverage is an evidence boundary, never an OFF actor."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from causal_history_coverage import (
    assess_local_sensor_history_coverage, guard_history_gap_claims,
)
from causal_answer_plan import build_causal_answer_plan


OFF = "2026-10-12T08:18:23.830+01:00"


def _history(label, *dates):
    return {"label": label, "attribute": "motion", "room": "Example",
            "observedEvents": [
                {"date": date, "name": "motion", "value": "active"} for date in dates
            ], "historySourceIntegrityVerified": False}


def _graph(coverage):
    return {
        "scope": "single-observed-event",
        "focus": {"subject": "Example Light", "on": "2026-10-12T08:16:10+01:00",
                  "off": OFF, "durationSeconds": 133},
        "transitionEvidence": {"off": {
            "observed": True, "time": OFF,
            "directCommand": None,
            "state": {"reporter": {"label": "Example Reporting Bridge"}},
            "sensorHistoryCoverage": coverage,
            "sensorCorrelations": [],
            "commandHistory": {
                "checked": True, "eventCount": 2,
                "result": "recorded-command-off-events",
            },
        }},
        "offHypotheses": {
            "status": "producer-unresolved", "sensorTimerComparisons": [],
            "historicalConfigVerified": False,
        },
    }


def test_newer_only_local_pages_fail_closed_without_asserting_deleted_events():
    coverage = assess_local_sensor_history_coverage(
        [_history("Primary FP300",
                  "2026-10-12T08:19:11.046+01:00",
                  "2026-10-12T11:44:07+01:00"),
         _history("Virtual Motion",
                  "2026-10-12T08:19:11.023+01:00")],
        OFF,
    )
    assert coverage["status"] == "pre-focal-not-observed-in-returned-pages"
    assert coverage["historiesWithOnlyLater"] == 2
    assert coverage["historiesWithPreFocal"] == 0
    assert coverage["historicalCompletenessVerified"] is False
    assert coverage["oldestReturnedEvent"].startswith("2026-10-12T08:19:11.023")
    plan = build_causal_answer_plan(
        _graph(coverage), "Why did Example Light switch OFF at 08:18:23?"
    )
    assert plan is not None
    assert plan["evidence"]["sensorHistoryCoverage"] == coverage
    assert not plan["evidence"]["timerComparisons"]


def test_pre_focal_observed_does_not_claim_complete_history():
    coverage = assess_local_sensor_history_coverage(
        [_history("FP300", "2026-10-12T08:18:23.761+01:00"),
         _history("Virtual Sensor", "2026-10-12T08:19:11+01:00")],
        OFF,
    )
    assert coverage["status"] == "at-least-one-pre-focal-event-returned"
    assert coverage["historiesWithPreFocal"] == 1
    assert coverage["historicalCompletenessVerified"] is False


def test_unresolvable_timestamp_is_not_a_fake_gap():
    coverage = assess_local_sensor_history_coverage(
        [_history("FP300", "2026-10-12T08:19:11+01:00")], "nonsense"
    )
    assert coverage["status"] == "unknown-boundary"


def test_missing_pages_are_not_misreported_as_no_inactivity():
    coverage = assess_local_sensor_history_coverage(
        [_history("FP300")], OFF
    )
    assert coverage["status"] == "pre-focal-not-observed-in-returned-pages"
    assert coverage["historiesWithoutEvents"] == 1


def test_focal_gap_guard_clears_false_external_and_no_hub_proof():
    coverage = assess_local_sensor_history_coverage(
        [_history("FP300", "2026-10-12T08:19:11+01:00")], OFF
    )
    draft = """### Causal Assessment
* **External Control/Bridge**: Because no Hubitat-side command exists, Hue must be responsible.
| Sensor Events | Motion became active after the light turned off | Inconsistent |
**Conclusion**: Hubitat acted only as a listener to the state change rather than the initiator."""
    result, changed = guard_history_gap_claims(draft, _graph(coverage))
    assert changed
    assert "Historical sensor coverage" in result
    assert "no Hubitat-side command exists" not in result
    assert "Hubitat acted only as a listener" not in result
    assert "| Coverage unavailable |" in result
    assert "OFF command producer remains unidentified" in result
    # Local repairs are stable and cannot trigger an endless rewrite.
    assert guard_history_gap_claims(result, _graph(coverage)) == (result, False)


def test_guard_not_applied_to_pre_focal_observed_history():
    coverage = assess_local_sensor_history_coverage(
        [_history("FP300", "2026-10-12T08:18:23.761+01:00")], OFF
    )
    draft = "No Hubitat-side command exists."
    assert guard_history_gap_claims(draft, _graph(coverage)) == (draft, False)
