"""Proof-carrying model-directed answer acceptance and negative controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from proof_carrying_answer import (
    SCHEMA, attested_telemetry_claims, admit_model_claim_plan, model_claim_prompt
)
from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import build_observed_agent_outcome
from shared_investigation_completion import apply_shared_investigation_completion
from api_response_builder import build_agent_response
from model_first_draft_provenance import PrivateModelDraft


def normalized():
    return {
        "deviceId": "9911", "deviceLabel": "Test Relay",
        "reportedDeviceState": {
            "deviceId": "9911", "label": "Test Relay",
            "source": "targeted-hubitat-device-state",
            "isPhysicalConnectivityProof": False,
            "reportedAttributes": {
                "healthStatus": "offline", "mqttStatus": "connected",
                "lastSeen": "old", "dataAgeSeconds": "123",
            },
        },
        "queryWindowHours": 24, "returnedEvents": 2,
        "stateEventCount": 2, "commandCount": 0,
        "truncated": False, "eventHistoryComplete": False,
        "sourceIntegrityVerified": False,
    }


def coverage():
    return {"rootCauseVerified": False,
            "telemetryClockConsistency": {
                "deviceId": "9911", "sourcesAgree": False,
            }}


def plan(ids=None):
    ids = ids or [
        "reported_health", "reported_mqtt", "clock_conflict",
        "cause_unverified", "next_readonly",
    ]
    return json.dumps({"schema": SCHEMA, "claim_ids": ids})


def test_model_claims_choose_order_but_not_unverified_sentence_content():
    claims = attested_telemetry_claims(normalized(), coverage())
    assert set(["reported_health", "reported_mqtt", "clock_conflict",
                "cause_unverified", "next_readonly"]).issubset(claims)
    prompt = model_claim_prompt(normalized(), coverage())
    assert "OPTIONAL SOURCE-ATTESTED" in prompt
    text, reason = admit_model_claim_plan(plan(), normalized(), coverage())
    assert reason == "source-claim-plan-admitted"
    assert text.startswith("Hubitat reports Test Relay healthStatus=offline")
    assert "mqttStatus=connected" in text
    assert "The saved lastSeen and dataAgeSeconds metadata disagree" in text
    assert "do not establish whether" in text
    assert "next read-only check" in text
    assert "physical endpoint" in text


def test_model_cannot_attach_arbitrary_prose_or_claim_extra_source_and_cause():
    bad = [
        plan(["reported_health", "reported_mqtt", "clock_conflict",
              "cause_unverified", "next_readonly", "physical_power_verified"]),
        plan(["reported_health", "reported_mqtt", "clock_conflict",
              "next_readonly"]),
        plan(["reported_health", "reported_health", "cause_unverified", "next_readonly"]),
        plan() + "\nThe plug is definitely powered off.",
        json.dumps({"schema": SCHEMA, "claim_ids": plan(),
                    "free_text": "plug is dead"}),
    ]
    for draft in bad:
        text, reason = admit_model_claim_plan(draft, normalized(), coverage())
        assert text is None and reason != "source-claim-plan-admitted"


def test_missing_source_proof_and_command_events_force_fallback():
    base = normalized()
    for alteration in (
        {"commandCount": 1},
        {"truncated": True},
        {"deviceId": "9999"},
        {"returnedEvents": 0},
    ):
        item = dict(base, **alteration)
        assert admit_model_claim_plan(plan(), item, coverage())[0] is None
    wrong = dict(base)
    wrong["reportedDeviceState"] = dict(base["reportedDeviceState"],
                                         source="generic-unverified-read")
    assert not attested_telemetry_claims(wrong, coverage())
    assert admit_model_claim_plan(plan(), base, {
        "rootCauseVerified": True,
    })[0] is None


def test_clock_disagreement_is_mandatory_when_source_checked():
    draft = plan(["reported_health", "reported_mqtt", "cause_unverified", "next_readonly"])
    assert admit_model_claim_plan(draft, normalized(), coverage())[1] == "missing-material-proof"
    no_clock = {"rootCauseVerified": False}
    assert admit_model_claim_plan(draft, normalized(), no_clock)[0] is not None


def evidence():
    return [
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_devices",
                          "args": {"labelFilter": "Test Relay"}},
            "summary": "1 targeted device candidates",
            "details": {"reportedDeviceState": {
                "deviceId": "9911", "label": "Test Relay",
                "observedAt": "2026-11-01T21:00:00+00:00",
                "source": "targeted-hubitat-device-state",
                "reportedAttributes": {
                    "healthStatus": "offline", "mqttStatus": "connected",
                },
            }},
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True, "effect": "read",
            "arguments": {"tool": "hub_list_device_events",
                          "args": {"deviceId": "9911", "hoursBack": 24}},
            "details": {"observedEvents": [{
                "name": "deviceHealth", "value": "stale",
                "date": "2026-11-01T20:59:00+00:00",
                "producedBy": {"id": "9911", "type": "device"},
            }]},
        },
    ]


def api_for(draft, *, changed=False, confirmed=False,
            request_class="live-read", incoming_override=None):
    trace = PrivateModelDraft(
        raw_first=draft,
        coordinator_result=("modified" if changed else draft),
        final_answer=("modified" if changed else draft),
        no_tools_final_stage=True,
    )
    outcome = AgentOutcome(
        message=(incoming_override if incoming_override is not None
                 else "modified" if changed else draft),
        request_class=request_class,
        evidence=evidence(), choices=[],
        confirmation_required=confirmed,
        private_model_draft=trace,
    )
    wrapped = build_observed_agent_outcome(
        outcome, {"outcome": "success", "counters": {}, "timings_ms": {}}
    )
    checked = apply_shared_investigation_completion(
        wrapped, "Why does Test Relay show MQTT connected but device health offline?"
    )
    return build_agent_response(checked, model="fixture", version="0.18.339",
                                elapsed_ms=12)


def test_actual_publisher_admits_verified_model_choices_only():
    raw = plan(["reported_mqtt", "reported_health",
                "cause_unverified", "next_readonly"])
    response = api_for(raw)
    cov = response["investigation_coverage"]
    assert cov["answerPublicationDecision"]["mode"] == "model-directed-source-claims"
    assert cov["answerPublicationDecision"]["modelChosenClaimsAttested"] is True
    assert cov["answerPublicationDecision"]["modelProseCertified"] is False
    assert "mqttStatus=connected" in response["message"]
    assert not response["message"].lstrip().startswith("{")
    assert cov["modelFirstDraftBoundary"]["publishedIsFirstModelDraft"] is False
    assert cov["rootCauseVerified"] is False
    assert "claim_ids" not in response["message"]


def test_safe_host_calibration_does_not_veto_source_proven_model_claim_plan():
    raw = plan(["reported_mqtt", "reported_health",
                "cause_unverified", "next_readonly"])
    # A previous host layer can add or alter a confidence qualifier.
    # It is the original unchanged model's typed claim plan that is
    # independently re-attested at the final evidence boundary.
    response = api_for(
        raw, incoming_override=(
            "HOST CAUSAL VERIFICATION: unverified. " + raw
        ),
    )
    coverage = response["investigation_coverage"]
    assert coverage["answerPublicationDecision"]["mode"] == (
        "model-directed-source-claims"
    )
    assert coverage["modelFirstDraftBoundary"][
        "authorAnswerUnchangedAtSharedBoundary"
    ] is False
    assert "HOST CAUSAL VERIFICATION" not in response["message"]
    assert "mqttStatus=connected" in response["message"]
    assert coverage["answerPublicationDecision"]["modelProseCertified"] is False


def test_rejected_unstructured_draft_exposes_fixed_diagnostic_reason():
    response = api_for("The plug must be physically powered off.")
    publication = response["investigation_coverage"]["answerPublicationDecision"]
    assert publication["mode"] == "concise"
    assert publication["modelClaimPlanRejection"] == "not-a-json-plan"
    assert "physically powered off" not in response["message"]


def test_repaired_or_unproved_model_text_never_becomes_public():
    for draft, changed in (
        ("Plug physical power is confirmed OFF.", False),
        (plan(["reported_mqtt", "reported_health",
               "cause_unverified", "next_readonly"]), True),
    ):
        reply = api_for(draft, changed=changed)
        mode = reply["investigation_coverage"]["answerPublicationDecision"]["mode"]
        assert mode == "concise"
        assert "physical power is confirmed OFF" not in reply["message"]
        assert "model-directed-source-claims" not in mode


def test_unrelated_causal_or_write_routes_cannot_gain_telemetry_certificate():
    raw = plan(["reported_mqtt", "reported_health", "cause_unverified", "next_readonly"])
    answer = api_for(raw, request_class="write")
    assert "answerPublicationDecision" not in answer.get("investigation_coverage", {})
