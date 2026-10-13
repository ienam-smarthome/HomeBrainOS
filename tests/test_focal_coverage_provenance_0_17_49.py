"""0.17.49: user-visible coverage must agree with requested-event evidence.

The 0.17.48 live run recovered native button 746/app1251 command but the
source-scoped device 7805 switch history lacked the requested OFF. Journal
collector-received OFF *was* observed. The public coverage incorrectly
labelled 'target_off observed' with source 'targeted switch-event history'
because newer unrelated native OFF rows were in the 26-hour feed.
"""
from __future__ import annotations

from investigation_intelligence import plan_investigation, assess_investigation


QUESTION = (
    "Independently reconstruct Livingroom Light 1's OFF at approximately "
    "23:49:27 BST on 12 October 2026. Correlate device 746's native physical "
    "button press, app 1251's OFF command, native device 7805 state history, "
    "Historical Journal OFF observations, subsequent motion, and app 4019's "
    "lockout decision. Distinguish native event timestamps from collector-received "
    "timestamps and explain any missing evidence. Read-only."
)


def source_detail(*, native_off=False, journal_off=True,
                  native_command=True, motion_eligible=False):
    return {
        "status": "partial-focal-sequence" if native_off
                  else "explicit-event-not-observed",
        "appId": "4019", "lightDeviceId": "7805",
        "lockoutExecutionVerified": False,
        "focalOff": (
            "2026-10-12T22:49:27.529+00:00"
            if native_off else None
        ),
        "focalSelection": {
            "explicitTargetUtc": "2026-10-12T22:49:27+00:00",
            "selectedOff": (
                "2026-10-12T22:49:27.529+00:00"
                if native_off else None
            ),
            "manualOffVerified": native_off and native_command,
            "physicalButtonCommandChain": (
                [{"verified": True}] if native_off and native_command else []
            ),
        },
        "crossSourceFocalProvenance": {
            "requestedEventUtc": "2026-10-12T22:49:27+00:00",
            "nativeButtonCommandVerified": native_command,
            "nativeLightStateObserved": native_off,
            "journalLightOffObserved": journal_off,
        },
        "sources": [
            {"source": "bounded-light-device-history", "success": True},
            {"source": "targeted-native-controller-history",
             "readSucceeded": True},
            {"source": "bounded-app-execution-logs",
             "readSucceeded": True, "returnedRows": 0},
        ],
        "journal": (
            [{"kind": "light", "deviceId": "7805", "observations": [
                {"value": "off",
                 "observedAt": "2026-10-12T22:49:28.623+00:00",
                 "timestampBasis": "collector-received"},
            ]}] if journal_off else []
        ),
        "motionCorrelations": [
            {"deviceId": "7981", "label": "FP400 Computer Desk",
             "eligibleActivationSourceVerified": motion_eligible,
             "observedAtUtc": "2026-10-12T22:49:33.826+00:00",
             "timestampBasis": "collector-received"},
        ],
    }


def _scoped(detail):
    return {"tool": "homebrain_motion_lockout_investigation",
            "success": True, "details": detail}


def _latest_unrelated_native_off():
    return {
        "tool": "hub_read_devices",
        "sub_tool": "hub_list_device_events",
        "success": True,
        "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": "7805", "hoursBack": 26},
        },
        "details": {"events": [
            {"name": "switch", "value": "off",
             "date": "2026-10-13T22:52:21.258+01:00"},
            {"name": "motion", "value": "active",
             "date": "2026-10-13T22:52:22.258+01:00"},
        ]},
    }


def assessment(detail):
    p = plan_investigation(QUESTION)
    assert p is not None and p.domain == "manual_motion_lockout"
    return assess_investigation(
        p, [_latest_unrelated_native_off(), _scoped(detail)]
    )


def test_collector_observed_focal_is_not_falsely_sourced_to_native_switch():
    r = assessment(source_detail())
    reqs = {row["key"]: row for row in r["requirements"]}
    assert reqs["target_off"]["state"] == "observed"
    assert "Historical Journal" in reqs["target_off"]["source"]
    assert "native state-event time unverified" in reqs["target_off"]["source"]
    assert reqs["controller"]["state"] == "observed"
    assert "independent native physical button" in reqs["controller"]["source"]
    assert reqs["motion"]["state"] == "checked-unverified"
    assert "activation eligibility unverified" in reqs["motion"]["source"]
    assert reqs["execution"]["state"] == "checked-unverified"
    proof = r["focalSourceEvidence"]
    assert proof["nativeLightOffObserved"] is False
    assert proof["collectorReceivedLightOffObserved"] is True
    assert proof["nativeButtonCommandLinked"] is True
    assert proof["postOffMotionObserved"] is True
    assert proof["motionActivationEligibilityVerified"] is False
    assert proof["historicalLockoutExecutionVerified"] is False
    assert not r["evidenceComplete"]


def test_absent_requested_off_not_satisfied_by_unrelated_newer_off():
    r = assessment(source_detail(journal_off=False))
    states = {row["key"]: row["state"] for row in r["requirements"]}
    assert states["target_off"] == "checked-unverified"
    assert states["controller"] == "observed"
    assert "targeted native light history and Historical Journal" in (
        next(x["source"] for x in r["requirements"]
             if x["key"] == "target_off")
    )
    assert "Historical Journal" not in (
        next(x["source"] for x in r["requirements"]
             if x["key"] == "controller")
    )


def test_native_focal_off_keeps_authoritative_native_source():
    r = assessment(source_detail(native_off=True))
    target = next(x for x in r["requirements"] if x["key"] == "target_off")
    assert target["state"] == "observed"
    assert target["source"] == "targeted native light switch-state history"
    assert r["focalSourceEvidence"]["nativeLightOffObserved"] is True


def test_journal_button_without_native_command_does_not_establish_controller():
    r = assessment(source_detail(native_command=False))
    controller = next(x for x in r["requirements"] if x["key"] == "controller")
    assert controller["state"] == "checked-unverified"
    assert r["focalSourceEvidence"]["nativeButtonCommandLinked"] is False


def test_motion_activeness_is_not_automatically_eligible_activation():
    r = assessment(source_detail(motion_eligible=True))
    motion = next(x for x in r["requirements"] if x["key"] == "motion")
    assert motion["state"] == "observed"
    assert r["focalSourceEvidence"]["motionActivationEligibilityVerified"] is True


def test_generic_manual_question_unchanged_without_explicit_focal_timestamp():
    p = plan_investigation(
        "Investigate manual OFF followed by motion three-minute lockout"
    )
    req = assess_investigation(p, [_latest_unrelated_native_off()])
    assert "focalSourceEvidence" not in req
    assert next(x for x in req["requirements"] if x["key"] == "target_off"
                )["state"] == "observed"
