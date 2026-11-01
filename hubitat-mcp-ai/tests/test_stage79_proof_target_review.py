"""Stage 7.9: independent typed proof-target compatibility without prose certification.

All sources fictional. All model turns are synthetic/mock, never Ollama Cloud.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from stage6_adaptive_benchmark import _CASES, _validate_answer, Stage6Benchmark  # noqa: E402
from stage7_review_packet import build_review_packet  # noqa: E402
from stage78_followup_sufficiency import validate_followup_assessment  # noqa: E402
from stage79_proof_target_review import build_stage79_review  # noqa: E402
from webui import render_page  # noqa: E402


def answer(kind="watchdog_history", target="exact_connectivity_loss_instant"):
    return {
        "schema": "homebrain-stage6-answer.v3",
        "sentences": [{
            "text": "The device was reported offline at 01:50:00Z.",
            "kind": "state_report", "evidence_ids": ["I1"],
            "atoms": [{"record_id": "I1", "field": "state", "value": "offline"}],
            "epistemic": {"position": "affirmed", "scope": "examined_records"},
        }],
        "uncertainties": ["The exact physical cause has not been independently established"],
        "next_evidence": "Inspect watchdog history to pinpoint the exact physical disconnection time.",
        "next_evidence_assessment": {
            "proposal_kind": kind,
            "proof_target": target,
            "could_establish": "The precise time a device physically went offline.",
            "cannot_establish": "The cause of the loss without corroboration.",
            "additional_proof_needed": "Independent device packet and clock calibration records.",
        },
    }


def packet(draft=None, case="stale_connectivity"):
    return build_review_packet(
        case, _CASES[case], ["S1", "S2", "S3"],
        answer() if draft is None else draft)


def test_single_watchdog_history_cannot_establish_exact_physical_loss_instant():
    draft = answer()
    validated = _validate_answer(json.dumps(draft), [_CASES["stale_connectivity"]["initial"]])
    assert validated == draft
    result = packet(validated)["stage79_proof_target_review"]
    assert result["class_target_status"] == "insufficient_source_class_alone"
    assert "cannot pinpoint" in result["target_evidence_boundary"]
    assert result["source_class_is_proof"] is False
    assert result["publisher_approval"] is False


@pytest.mark.parametrize("kind,target,expected", [
    ("watchdog_history", "watchdog_detection_window", "compatible_class_not_proof"),
    ("watchdog_history", "exact_connectivity_loss_instant", "insufficient_source_class_alone"),
    ("device_telemetry", "specific_command_caused_outcome", "insufficient_source_class_alone"),
    ("device_telemetry", "reported_device_state", "compatible_class_not_proof"),
    ("broker_session", "broker_transport_status", "compatible_class_not_proof"),
    ("broker_session", "reported_device_state", "insufficient_source_class_alone"),
    ("command_history", "physical_actuation", "insufficient_source_class_alone"),
    ("command_execution_receipt", "physical_actuation", "compatible_class_not_proof"),
    ("clock_correlation", "source_clock_accuracy", "compatible_class_not_proof"),
    ("controller_decision_log", "controller_decision", "compatible_class_not_proof"),
    ("other", "exact_connectivity_loss_instant", "unclassified_requires_human"),
])
def test_generic_source_type_and_proof_target_pairs(kind, target, expected):
    p = packet(answer(kind, target))["stage79_proof_target_review"]
    assert p["class_target_status"] == expected
    assert p["human_followup_quality_verdict"] == "not_reviewed"
    assert p["structured_match_is_not_natural_language_verification"] is True


def test_structured_match_does_not_approve_stronger_contradictory_free_text():
    # The source class can support a detection window conditionally, but
    # the text falsely claims the exact moment. Host must NOT certify it.
    draft = answer("watchdog_history", "watchdog_detection_window")
    p = packet(draft)["stage79_proof_target_review"]
    assert p["class_target_status"] == "compatible_class_not_proof"
    assert p["model_proof_target_matches_authored_next_evidence"] == "not_reviewed"
    assert p["model_could_establish_text_matches_target"] == "not_reviewed"
    assert p["publisher_approval"] is False


def test_legacy_v3_assessment_without_target_does_not_fail():
    d = answer()
    d["next_evidence_assessment"].pop("proof_target")
    assert _validate_answer(json.dumps(d), [_CASES["stale_connectivity"]["initial"]]) == d
    p = packet(d)["stage79_proof_target_review"]
    assert p["class_target_status"] == "not_declared"


@pytest.mark.parametrize("target", ["made_up", "", None, [], 44])
def test_invalid_target_discarded_without_losing_factual_sentences(target):
    d = answer()
    d["next_evidence_assessment"]["proof_target"] = target
    processed = _validate_answer(json.dumps(d), [_CASES["stale_connectivity"]["initial"]])
    assert processed["sentences"] == d["sentences"]
    assert "next_evidence_assessment" not in processed
    assert processed["_followup_validation"] == {"next_evidence_assessment": "invalid"}
    p = packet(processed)["stage79_proof_target_review"]
    assert p["class_target_status"] == "not_declared"
    assert p["publisher_approval"] is False


def test_unexpected_extra_fields_still_fail_and_no_free_text_heuristic_certification():
    d = answer()
    d["surprise"] = "not allowed"
    with pytest.raises(ValueError, match="structure"):
        _validate_answer(json.dumps(d), [_CASES["stale_connectivity"]["initial"]])
    d.pop("surprise")
    d["sentences"][0]["evidence_ids"] = ["not-a-real-source"]
    with pytest.raises(ValueError, match="citation"):
        _validate_answer(json.dumps(d), [_CASES["stale_connectivity"]["initial"]])


def test_absent_or_malformed_suggestion_never_gets_automatic_grade():
    d = answer()
    d["next_evidence"] = ["bad", "optional"]
    processed = _validate_answer(json.dumps(d), [_CASES["stale_connectivity"]["initial"]])
    p = packet(processed)["stage79_proof_target_review"]
    assert p["class_target_status"] == "no_valid_proposal_text"
    assert not p["source_class_is_proof"]
    assert p["publisher_approval"] is False


@pytest.mark.parametrize("case", list(_CASES))
def test_same_source_rule_applies_to_every_benchmark_case(case):
    p = packet(answer(), case=case)["stage79_proof_target_review"]
    assert p["class_target_status"] == "insufficient_source_class_alone"
    assert p["synthetic_postrun_only"] is True
    assert p["extra_model_requests"] == 0
    assert p["hidden_reference_oracle_used"] is False


class MockCloud:
    base_url = "https://ollama.com"
    model_name = "gemma4:31b-cloud"
    api_key = "private-test-credential"
    timeout_seconds = 60
    configured = True

    def __init__(self):
        self.calls = []

    async def _chat_post(self, messages, tools, **kwargs):
        self.calls.append(messages)
        assert tools == [] and kwargs["disable_thinking"]
        prompt = json.dumps(messages)
        assert "hidden_reference_oracle_used" not in prompt
        assert "class_target_status" not in prompt
        assert "private-test-credential" not in prompt
        payload = json.loads(messages[1]["content"])
        if "remaining_source_titles" in payload:
            index = len(payload["sources_already_examined"])
            return {"content": json.dumps({
                "schema": "homebrain-stage6-next.v1", "action": "read",
                "source_id": ["S1", "S2", "S3"][index],
                "reason": "Read distinct evidence relevant to the question",
            })}
        assert "proof_target" in messages[0]["content"]
        return {"content": json.dumps(answer())}


def test_four_calls_and_no_background_inference_or_publication():
    transport = MockCloud()
    out = asyncio.run(Stage6Benchmark().run_case(
        transport, "stale_connectivity", confirmed=True))
    assert out["success"] is True
    assert len(transport.calls) == out["cloud_requests_attempted"] == 4
    p = out["independent_review_packet"]["stage79_proof_target_review"]
    assert p["class_target_status"] == "insufficient_source_class_alone"
    assert p["extra_model_requests"] == 0
    assert out["independent_review_packet"]["publisher_approval"] is False


def test_mobile_independent_reviewer_displays_both_claim_and_uncertainty():
    html = render_page("HomeBrainOS", "0.18.312")
    for phrase in (
        "Stage 7.9 · Does the proposed source support its claimed conclusion?",
        "stage79_proof_target_review",
        "insufficient_source_class_alone",
        "Does the actual proposal imply stronger certainty",
        "this check does NOT certify prose",
        "production_publication_approval:false",
    ):
        assert phrase in html


def test_production_modules_remain_isolated():
    for name in ("mcp_agent_orchestrator.py", "tool_executor.py",
                 "causal_claim_publication.py", "final_answer_coordinator.py"):
        assert "stage79_proof_target_review" not in (APP / name).read_text()
