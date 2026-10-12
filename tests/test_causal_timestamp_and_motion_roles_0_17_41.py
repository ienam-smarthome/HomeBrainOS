"""0.17.41: preserve hub clock and distinguish observed motion from activation.

A collector-received motion event on a relevant keep-on sensor is evidence
of motion; it is *not* a verified motion-activation attempt for app 4019.
"""
from datetime import datetime
from motion_lockout_investigation import (
    last_observed_off, source_local_off_time, observed_motion_correlations,
)
from investigation_intelligence import plan_investigation, assess_investigation


OFF_LOCAL = "2026-10-12T23:49:27.529+0100"
MOTION_UTC = "2026-10-12T22:51:09.904385+00:00"


def _journal(verified=False):
    return [{
        "kind": "sensor", "deviceId": "7778",
        "label": "Linptech Kitchen sensor", "attribute": "motion",
        "activationSourceVerified": verified,
        "activationRole": (
            "verified-activation-source" if verified else
            "unverified-from-current-configuration"
        ),
        "observations": [{
            "observedAt": MOTION_UTC,
            "value": "active",
            "timestampBasis": "collector-received",
        }],
        "gapCount": 2,
    }]


def _plan():
    return plan_investigation(
        "Investigate the latest manual OFF of Livingroom Light 1 "
        "followed by motion. Did app 4019's three-minute motion lockout engage?"
    )


def _receipt(verified=False):
    return [{
        "tool": "homebrain_motion_lockout_investigation",
        "success": True,
        "details": {
            "focalOff": "2026-10-12T22:49:27.529+00:00",
            "focalOffHubLocal": "2026-10-12T23:49:27.529+01:00",
            "sources": [
                {"source": "bounded-light-device-history", "success": True},
                {"source": "bounded-app-execution-logs",
                 "readSucceeded": True, "returnedRows": 2},
            ],
            "journal": _journal(verified),
            "lockoutExecutionVerified": False,
        },
    }]


def test_native_hub_offset_survives_canonical_utc_timestamp():
    data = {"temporalAnalysis": {"intervals": [
        {"start": "2026-10-12T23:49:19.140+0100",
         "end": OFF_LOCAL, "clippedAtWindowEnd": False},
    ]}}
    off = last_observed_off(data)
    assert off == datetime.fromisoformat("2026-10-12T22:49:27.529+00:00")
    assert source_local_off_time(data, off) == "2026-10-12T23:49:27.529+01:00"


def test_collector_motion_is_102_seconds_later_but_eligibility_unknown():
    off = datetime.fromisoformat("2026-10-12T22:49:27.529+00:00")
    result = observed_motion_correlations(
        _journal(), off=off, local_off="2026-10-12T23:49:27.529+01:00")
    assert len(result) == 1
    assert result[0]["secondsAfterOff"] == 102.375
    assert result[0]["observedAtHubOffset"] == (
        "2026-10-12T23:51:09.904+01:00")
    assert result[0]["timestampBasis"] == "collector-received"
    assert result[0]["eligibleActivationSourceVerified"] is False


def test_unknown_activation_role_does_not_satisfy_historical_eligibility():
    plan = _plan()
    assert plan is not None
    coverage = assess_investigation(plan, _receipt())
    states = {r["key"]: r["state"] for r in coverage["requirements"]}
    assert states["target_off"] == "observed"
    assert states["motion"] == "checked-unverified"
    assert states["execution"] == "checked-unverified"
    assert coverage["evidenceComplete"] is False
    assert any("eligibility" in message for message in coverage["warnings"])


def test_explicitly_verified_eligible_source_counts_observed_motion_only():
    plan = _plan()
    coverage = assess_investigation(plan, _receipt(verified=True))
    states = {r["key"]: r["state"] for r in coverage["requirements"]}
    assert states["motion"] == "observed"
    assert states["execution"] == "checked-unverified"
    assert coverage["evidenceComplete"] is False


def test_same_instant_in_different_offsets_and_naive_do_not_create_false_proof():
    data = {"temporalAnalysis": {"intervals": [
        {"end": "2026-10-12T22:49:27.529Z",
         "clippedAtWindowEnd": False},
    ]}}
    stamp = last_observed_off(data)
    assert source_local_off_time(data, stamp) == (
        "2026-10-12T22:49:27.529+00:00")
    no_offset = {"temporalAnalysis": {"intervals": [
        {"end": "2026-10-12T22:49:27.529",
         "clippedAtWindowEnd": False},
    ]}}
    assert last_observed_off(no_offset) is None
