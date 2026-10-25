"""Regression: a verified inactivity sequence must survive causal caution.

The synthetic receipts preserve the exact event timestamps, producer identity,
and listener metadata in the user's v0.18.116 investigation. No devices are
changed; the implementation must be device- and app-ID agnostic.
"""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from occupancy_timing_correlation import (
    correlate_occupancy_off_timing, summarize_supported_off_timing,
)
from occupancy_causal_proof import guard_unverified_occupancy_cause
from api_response_builder import build_agent_response


def _receipt(attribute, label, events, intervals=()):
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "effect": "read", "mutates": False,
        "details": {
            "label": label, "attribute": attribute,
            "boundaryEvents": events,
            "temporalAnalysis": {"observedIntervals": list(intervals)},
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
        },
    }


def _event(name, value, at, app=None, producer=None):
    return {
        "name": name, "value": value, "date": f"2026-10-25T{at}+00:00",
        "triggered": ([{"appId": app, "handler": "motionHandler"}]
                      if app is not None else []),
        "producedBy": producer or {},
    }


def _light():
    data = [
        _event("command-off", None, "16:58:58.691",
               producer={"type": "app", "id": "4019"}),
        _event("switch", "off", "16:58:58.937",
               producer={"type": "device", "id": "7790"}),
        _event("command-off", None, "17:01:16.922",
               producer={"type": "app", "id": "4019"}),
        _event("switch", "off", "17:01:17.095",
               producer={"type": "device", "id": "7790"}),
    ]
    return _receipt("switch", "Livingroom Light 1", data, [{
        "start": "2026-10-25T16:30:46.568+00:00",
        "end": "2026-10-25T16:58:58.937+00:00",
        "durationSeconds": 1692,
    }])


def _sensor(label, spans, app=4019):
    evts, windows = [], []
    for begin, end in spans:
        evts.extend([
            _event("motion", "active", begin, app),
            _event("motion", "inactive", end, app),
        ])
        windows.append({
            "start": f"2026-10-25T{begin}+00:00",
            "end": f"2026-10-25T{end}+00:00",
        })
    return _receipt("motion", label, evts, windows)


def _case():
    return [
        _light(),
        _sensor("FP400 motion sensor", [
            ("15:38:37.493", "16:58:28.633"),
            ("17:00:16.851", "17:00:40.144"),
        ]),
        _sensor("Matter LWR01 Livingroom Occupancy", [
            ("16:56:49.038", "16:58:11.413"),
            ("17:00:16.431", "17:00:46.653"),
        ]),
        _sensor("Linptech Kitchen sensor", [
            ("17:00:21.061", "17:00:26.835"),
        ]),
        # Clone reports state but only SenseCap, never the OFF-producing app.
        _sensor("Livingroom Soft Sensor", [
            ("14:59:34.389", "16:58:29.649"),
            ("17:00:16.883", "17:00:41.163"),
        ], app=4129),
    ]


def test_exact_live_timings_identify_distinct_last_reported_inactive_input():
    correlations = correlate_occupancy_off_timing(_case())
    assert len(correlations) == 2
    assert [(x["lastObservedInactiveSensor"],
             x["inactiveToCommandSeconds"],
             x["ackSeconds"]) for x in correlations] == [
        ("FP400 motion sensor", 30.058, 0.246),
        ("Matter LWR01 Livingroom Occupancy", 30.269, 0.173),
    ]
    assert correlations[0]["sensorActiveFrom"].endswith("15:38:37.493000+00:00")
    assert all("Soft Sensor" not in x["lastObservedInactiveSensor"] for x in correlations)


def test_mechanism_preserves_bounded_active_interval_but_does_not_assert_ghosting():
    summary = summarize_supported_off_timing(_case())
    assert "FP400 motion sensor reported inactive at 16:58:28.633" in summary
    assert "Matter LWR01 Livingroom Occupancy reported inactive at 17:00:46.653" in summary
    assert "30.058s later" in summary
    assert "30.269s later" in summary
    assert "15:38:37" in summary
    assert "Soft Sensor" not in summary
    assert "do not prove" in summary


def test_original_bad_ghosting_diagnosis_is_repaired_without_erasing_best_evidence():
    bad = (
        "The most likely cause of Livingroom Light 1 staying ON is ghost motion. "
        "The automation is working exactly as configured; sensors are triggering falsely."
    )
    msg, changed = guard_unverified_occupancy_cause(bad, _case())
    assert changed
    assert "**Supported inactivity mechanism:**" in msg
    assert "**Cause not verified:**" in msg
    assert "FP400 motion sensor" in msg
    assert "Matter LWR01 Livingroom Occupancy" in msg
    assert "30.058s" in msg and "30.269s" in msg
    assert "most likely cause" not in msg


def test_generic_unresolved_answer_is_enriched_when_positive_evidence_exists():
    answer = (
        "Cause not verified: we cannot establish whether any input stayed active."
    )
    msg, changed = guard_unverified_occupancy_cause(answer, _case())
    assert changed
    assert msg.startswith("**Supported inactivity mechanism:**")
    assert answer in msg


def test_unrelated_question_and_good_positive_answer_are_not_rewritten():
    ordinary = "1 light is on in Living Room."
    assert guard_unverified_occupancy_cause(ordinary, _case()) == (ordinary, False)
    cautious = "FP400 is a reported input. False motion is possible, not verified."
    assert guard_unverified_occupancy_cause(cautious, _case()) == (cautious, False)


def test_reactivation_cancels_candidate_inactive_edge():
    rows = _case()
    # A later ACTIVE edge contradicts the first FP400 inactive edge.
    rows[1]["details"]["boundaryEvents"].append(
        _event("motion", "active", "16:58:45.000", app=4019)
    )
    matches = correlate_occupancy_off_timing(rows)
    assert matches[0]["lastObservedInactiveSensor"] == "Matter LWR01 Livingroom Occupancy"


def test_disconnected_clone_cannot_claim_last_input_even_with_closer_inactive():
    rows = _case()
    # Clone's 16:58:29.649 edge is 1s later than FP400's; still not a
    # controller input because it does NOT list app 4019 as a listener.
    matches = correlate_occupancy_off_timing(rows)
    assert matches[0]["lastObservedInactiveSensor"] == "FP400 motion sensor"


def test_without_confirmed_off_state_no_mechanism_or_timings():
    rows = _case()
    rows[0]["details"]["boundaryEvents"] = [
        e for e in rows[0]["details"]["boundaryEvents"]
        if e.get("name") != "switch"
    ]
    assert not correlate_occupancy_off_timing(rows)
    assert not summarize_supported_off_timing(rows)


def test_not_a_hardcoded_sensor_or_app_id_feature():
    rows = _case()
    for receipt in rows:
        for event in receipt["details"]["boundaryEvents"]:
            for listener in event.get("triggered") or []:
                if listener.get("appId") == 4019:
                    listener["appId"] = 720
            if event.get("producedBy", {}).get("id") == "4019":
                event["producedBy"]["id"] = "720"
    matches = correlate_occupancy_off_timing(rows)
    assert len(matches) == 2 and all(row["appId"] == "720" for row in matches)


def test_api_builder_presents_positive_mechanism_and_keeps_technical_evidence():
    rows = _case()
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message="False motion is the most likely cause; the timer is working exactly as configured.",
        evidence=rows, metrics={"outcome": "unresolved", "counters": {}, "timings_ms": {}},
        investigation_coverage={"domain": "causal_provenance", "sourceChecksComplete": False},
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=53000, version="0.18.117"
    )
    assert response["evidence_validation"]["unverified_occupancy_cause_corrected"]
    assert "**Supported inactivity mechanism:**" in response["message"]
    assert "30.058s" in response["message"]
    assert "30.269s" in response["message"]
    assert response["evidence"] == rows
