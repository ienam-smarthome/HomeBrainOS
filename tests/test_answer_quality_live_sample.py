"""Q1 live single-answer intake: source scope/identity, not automatic grading.

All fixtures are synthetic. Never contact HomeBrain, Hubitat, or the router.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/answer_quality_live_sample.py"
SPEC = importlib.util.spec_from_file_location("answer_quality_live_sample", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

QUESTION = "Compare the states of Hallway Light 1 and Livingroom Light 2."
CASE = "multi_device_named"
HASH = hashlib.sha256(QUESTION.encode("utf-8")).hexdigest()


def make_response(*, digest=HASH, outcome="success", request_class="live-read"):
    return {
        "success": True,
        "request_class": request_class,
        "model": "gemma4:31b",
        "version": "0.18.399",
        "message": (
            "Private household: 192.168.1.123; token=do-not-publish. "
            "Hallway Light 1 is physically on with high confidence."
        ),
        "elapsed_ms": 12801,
        "metrics": {
            "outcome": outcome,
            "timings_ms": {"total": 12789, "provider": 9001},
            "counters": {
                "tool_calls": 3, "model_rounds": 2,
                "read_only_model_write_blocked": 1,
            },
        },
        "request_provenance": {
            "source": "api_ask_request",
            "normalization": "collapse-whitespace-v1",
            "normalized_prompt_sha256": digest,
            "model_delivery_verified": False,
            "first_attempt_verified": False,
            "deployed_build_sha_verified": False,
        },
        "evidence": [{
            "tool": "hub_read_devices",
            "success": True,
            "mutates": False,
            "effect": "read",
            "arguments": {
                "tool": "hub_get_device",
                "args": {"deviceId": "private-device-123",
                         "label": "Household-name-not-for-repo"}
            },
            "summary": "192.168.1.123 token=do-not-publish",
        } for _ in range(2)] + [{
            "tool": "hub_read_devices",
            "success": False,
            "mutates": False,
            "effect": "read",
            "arguments": {"token": "do-not-publish"},
        }],
    }


def test_frozen_source_exact_question_is_identified_without_claim_scoring():
    assert MOD.registered_read_only_prompt(CASE) == QUESTION
    result = MOD.intake(make_response(), CASE)
    assert result["schema"] == MOD.SCHEMA
    assert result["registered_api_question_match"] is True
    assert result["q1_observational_read_only_sample"] is True
    assert result["q1_source_review"] == "pending_independent_review"
    assert result["q1_first_attempt_accuracy"] == "not_measured"
    assert result["q1_factual_grounding"] == "not_measured"
    assert result["q1_question_resolution"] == "not_measured"
    assert result["successful_read_receipts"] == 2
    assert result["failed_read_receipts"] == 1
    assert "source_read_failures_require_review" in result["completeness_warnings"]
    assert result["observed_write_receipts"] == 0
    assert result["wall_time_ms"] == 12801
    assert result["agent_time_ms"] == 12789
    assert result["provider_time_ms"] == 9001
    assert result["tool_calls_reported"] == 3
    assert result["blocked_model_write_batches_reported"] == 1
    assert result["model_reported"] == "gemma4:31b"
    assert result["version_reported"] == "0.18.399"


def test_privacy_including_device_identifiers_and_raw_source_never_published():
    raw = make_response()
    raw["evidence"][0]["arguments"]["args"]["deviceId"] = "abcdef-private"
    raw["evidence"][0]["summary"] = "Password=secret/private-host"
    serialized = json.dumps(MOD.intake(raw, CASE))
    for text in [
        "192.168.", "do-not-publish", "Hallway Light", "Livingroom Light",
        "private-device-123", "Household-name-not-for-repo",
        "abcdef-private", "Password=secret/private-host", HASH,
    ]:
        assert text not in serialized


@pytest.mark.parametrize("bad_digest", [
    "b" * 64, "WRONG", "", None, 17,
])
def test_not_identical_api_prompt_cannot_enter_q1_observational_cohort(bad_digest):
    result = MOD.intake(make_response(digest=bad_digest), CASE)
    assert result["registered_api_question_match"] is False
    assert result["q1_observational_read_only_sample"] is False
    assert "registered_api_question_not_attested" in result["completeness_warnings"]


def test_missing_or_conflicting_request_provenance_is_not_promoted_to_first_attempt():
    response = make_response()
    response["request_provenance"] = {
        **response["request_provenance"],
        "source": "model_response",
        "first_attempt_verified": True,
        "model_delivery_verified": True,
        "deployed_build_sha_verified": True,
    }
    result = MOD.intake(response, CASE)
    assert result["registered_api_question_match"] is False
    assert result["q1_first_attempt_accuracy"] == "not_measured"
    assert result["api_provenance_flags"]["independently_authenticated"] is False


@pytest.mark.parametrize("case_id", [
    "control_on", "control_brightness", "control_multi",
    "rule_create_light", "refuse_unknown_device", "unregistered-case",
])
def test_writes_and_unregistered_cases_are_not_eligible_for_read_only_intake(case_id):
    with pytest.raises(MOD.LiveSampleError):
        MOD.intake(make_response(), case_id)


def test_read_only_case_that_requests_write_is_rejected_for_observational_set():
    response = make_response(request_class="write")
    response["evidence"].append({
        "tool": "hub_manage_devices", "effect": "sensitive_write",
        "mutates": True, "success": True,
        "arguments": {"deviceId": "private-household-device"},
    })
    result = MOD.intake(response, CASE)
    assert result["observed_write_receipts"] == 1
    assert result["q1_observational_read_only_sample"] is False
    assert "write_receipts_present" in result["completeness_warnings"]
    assert "not_a_read_only_request" in result["completeness_warnings"]


def test_unsupported_outcome_and_missing_evidence_refused():
    response = make_response()
    response["metrics"]["outcome"] = "unknown-status"
    with pytest.raises(MOD.LiveSampleError, match="outcome"):
        MOD.intake(response, CASE)
    response = make_response()
    response["evidence"] = "driver reported success"
    with pytest.raises(MOD.LiveSampleError, match="evidence"):
        MOD.intake(response, CASE)


def test_transport_success_and_answer_quality_are_not_equivalent():
    response = make_response(outcome="unresolved")
    result = MOD.intake(response, CASE)
    assert result["transport_success"] is True
    assert result["outcome"] == "unresolved"
    assert "request_outcome_not_success" in result["completeness_warnings"]
    assert result["q1_factual_grounding"] == "not_measured"


def test_missing_metrics_are_missing_not_zero_or_success():
    response = make_response()
    del response["metrics"]["timings_ms"]["total"]
    response["metrics"]["counters"]["tool_calls"] = True
    response["metrics"]["counters"].pop("model_rounds")
    response["metrics"]["counters"]["read_only_model_write_blocked"] = "0"
    result = MOD.intake(response, CASE)
    assert result["agent_time_ms"] is None
    assert result["tool_calls_reported"] is None
    assert result["model_rounds_reported"] is None
    assert result["blocked_model_write_batches_reported"] is None


def test_evidence_without_any_read_does_not_prove_source_coverage():
    response = make_response()
    response["evidence"] = []
    result = MOD.intake(response, CASE)
    assert result["successful_read_receipts"] == 0
    assert result["q1_observational_read_only_sample"] is False
    assert "no_successful_source_read_receipts" in result["completeness_warnings"]


def test_false_first_attempt_flags_do_not_default_to_certification():
    response = make_response()
    response["request_provenance"].update({
        "model_delivery_verified": True,
        "first_attempt_verified": True,
        "deployed_build_sha_verified": True,
    })
    result = MOD.intake(response, CASE)
    assert result["api_provenance_flags"]["first_attempt_reported"] is True
    assert result["api_provenance_flags"]["independently_authenticated"] is False
    assert result["q1_first_attempt_accuracy"] == "not_measured"


def test_untrusted_model_and_version_names_are_suppressed():
    response = make_response()
    response["model"] = "secret user password\nshould not be included"
    response["version"] = "token=123\n0.18.399"
    result = MOD.intake(response, CASE)
    assert result["model_reported"] is None
    assert result["version_reported"] is None
    assert "secret user" not in json.dumps(result)


def test_whitespace_normalization_matches_api_contract():
    assert MOD.normalise("Compare \t the   states\nof  X.") == "Compare the states of X."


def test_cli_can_intake_private_json_without_emitting_raw_answer(tmp_path, capsys):
    response = tmp_path / "private-response.json"
    response.write_text(json.dumps(make_response()), encoding="utf-8")
    assert MOD.main(["--case", CASE, "--receipt", str(response)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["registered_api_question_match"]
    assert data["q1_source_review"] == "pending_independent_review"
    assert "do-not-publish" not in json.dumps(data)
