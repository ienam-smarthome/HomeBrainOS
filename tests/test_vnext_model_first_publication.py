"""vNext opt-in model-first publication safety and fallback negative controls.

Synthetic model drafts and read-only receipts only; these tests do not
establish factual accuracy, Claude parity, or production root cause.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from model_first_draft_provenance import PrivateModelDraft
from model_first_publication import admit_model_first_telemetry_answer


NORMALIZED = {
    "deviceId": "9911", "deviceLabel": "Test plug",
    "commandCount": 0, "truncated": False,
    "reportedDeviceState": {
        "deviceId": "9911",
        "source": "targeted-hubitat-device-state",
        "isPhysicalConnectivityProof": False,
        "reportedAttributes": {
            "healthStatus": "offline", "mqttStatus": "connected",
        },
    },
}
COVERAGE = {"rootCauseVerified": False}
NATURAL = (
    "Hubitat currently reports Test plug as offline, while its MQTT connection "
    "is reported connected. That second reading describes the saved driver "
    "connection state and cannot establish whether the actual plug is online. "
    "The saved timestamps may refer to different reporting clocks; there "
    "is no independently verified recent physical packet in this evidence. "
    "The cause remains unknown. Next, check the device-originated MQTT "
    "messages or the router's current Wi-Fi association as a read-only step."
)


def trace(text: str = NATURAL, **overrides):
    values = dict(
        raw_first=text, coordinator_result=text, final_answer=text,
        no_tools_final_stage=True,
    )
    values.update(overrides)
    return PrivateModelDraft(**values)


def test_opt_in_allows_natural_evidence_calibrated_unchanged_model_draft():
    accepted, reason = admit_model_first_telemetry_answer(
        NATURAL, trace(), NORMALIZED, COVERAGE,
    )
    assert accepted == NATURAL
    assert reason == "model-authored-bounded-telemetry"
    assert "next" in accepted.lower()
    assert "cause remains unknown" in accepted


def test_changed_or_missing_model_provenance_falls_back():
    for t in (
        None,
        trace(raw_first=None),
        trace(coordinator_result="Changed"),
        trace(final_answer="Changed"),
        trace(no_tools_final_stage=False),
    ):
        accepted, reason = admit_model_first_telemetry_answer(
            NATURAL, t, NORMALIZED, COVERAGE,
        )
        assert accepted is None
        assert reason == "model-draft-provenance-changed"
    assert admit_model_first_telemetry_answer(
        NATURAL + " Host-added paragraph", trace(), NORMALIZED, COVERAGE,
    )[0] is None


def test_missing_verified_source_scope_or_physical_cause_is_never_admitted():
    examples = (
        ({**NORMALIZED, "deviceId": "1234"}, COVERAGE),
        ({**NORMALIZED, "reportedDeviceState": {
            **NORMALIZED["reportedDeviceState"], "isPhysicalConnectivityProof": True,
        }}, COVERAGE),
        (NORMALIZED, {"rootCauseVerified": True}),
        (NORMALIZED, {}),
        ({**NORMALIZED, "reportedDeviceState": {
            **NORMALIZED["reportedDeviceState"], "source": "unknown",
        }}, COVERAGE),
    )
    for normalized, coverage in examples:
        assert admit_model_first_telemetry_answer(
            NATURAL, trace(), normalized, coverage,
        )[0] is None


def test_positive_causal_assertion_physical_claim_and_fake_write_are_rejected():
    for line in (
        "The root cause is the nighttime power saving rule.",
        "The plug went offline because of an access point failure.",
        "The last real packet was received on October 12.",
        "The MQTT connected status proves the plug is online and powered.",
        "I restarted the plug to diagnose it.",
    ):
        candidate = NATURAL + "\n\n" + line
        accepted, reason = admit_model_first_telemetry_answer(
            candidate, trace(candidate), NORMALIZED, COVERAGE,
        )
        assert accepted is None, line
        assert reason in {
            "unverified-definitive-cause",
            "unverified-physical-telemetry",
            "unverified-action-claim",
        }


def test_omitted_health_mqtt_or_uncertainty_fails_conservatively():
    candidates = [
        ("The endpoint is unknown. MQTT is connected. " + "X " * 55,
         "reported-health-omitted"),
        ("Hubitat reports the plug offline; it may be wrong. " + "X " * 55,
         "broker-versus-endpoint-omitted"),
        ("Hubitat reports offline. MQTT reports connected. " + "X " * 55,
         "material-uncertainty-omitted"),
        ('{"schema":"homebrain-source-claim-plan.v1","claim_ids":["reported_health"]}',
         "not-a-natural-explanation"),
    ]
    for candidate, expected in candidates:
        actual, reason = admit_model_first_telemetry_answer(
            candidate, trace(candidate), NORMALIZED, COVERAGE,
        )
        assert actual is None
        assert reason == expected


def test_not_applied_to_command_or_ambiguous_target_history():
    for n in (
        {**NORMALIZED, "commandCount": 1},
        {**NORMALIZED, "truncated": True},
        {**NORMALIZED, "deviceId": ""},
    ):
        accepted, reason = admit_model_first_telemetry_answer(
            NATURAL, trace(), n, COVERAGE,
        )
        assert accepted is None
        assert reason == "unverified-source-scope"
