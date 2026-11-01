"""Q1 capture: safe meta-only outputs never masquerade as a benchmark score."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from answer_quality_capture import extract_capture, main
from answer_quality_scorecard import ScorecardInputError


def response():
    return {
        "success": True,
        "route": "unified-mcp-agent",
        "message": (
            "Hallway motion event SECRET-RAW-ANSWER-TOKEN. "
            "Known light ID and private address http://192.168.1.239."
        ),
        "version": "0.18.330",
        "model": "gemma4:31b",
        "elapsed_ms": 46333,
        "model_tier_requested": "free",
        "metrics": {
            "outcome": "unresolved",
            "counters": {"tool_calls": 18, "model_rounds": 9},
            "timings_ms": {"total": 45124},
            "model_round_details": [
                {"model": "gemma4:31b", "provider": "ollama-cloud"}
            ],
        },
        "evidence": [
            {"tool": "hub_read_devices", "mutates": False,
             "arguments": {"args": {"password": "SECRET-RAW-SOURCE-TOKEN",
                                    "deviceId": "7829"}},
             "details": {"events": [
                 {"description": "SECRET-HOUSEHOLD-LABEL"}
             ]}},
        ],
        "investigation_coverage": {
            "rootCauseVerified": None,
            "questionResolved": False,
            "hypothesisComparisons": [
                {"hypothesis_verdict": "unverified", "candidate": "SECRET-APP-NAME"},
                {"hypothesis_verdict": "unverified"},
            ],
        },
    }


def test_capture_does_not_export_answer_tool_args_or_private_receipt_content():
    packet = extract_capture(
        response(), case_id="causal_light2_off", actual_question=None,
        root=ROOT,
    )
    encoded = json.dumps(packet)
    assert "SECRET-" not in encoded
    assert "192.168" not in encoded
    assert "7829" not in encoded
    assert "Hallway" not in encoded
    assert packet["review"]["status"] == "pending_independent_source_review"
    assert packet["capture_is_quality_review"] is False
    assert packet["prompt_match"] == "not_checked"
    assert packet["matches_registered_live_question"] is False
    assert packet["tool_calls_reported"] == 18
    assert packet["model_rounds_reported"] == 9
    assert packet["wall_elapsed_ms"] == 46333
    assert packet["provider"] == "ollama-cloud"
    assert packet["hypotheses_explicitly_unverified"] == 2
    assert packet["question_resolution_reported"] is False
    assert packet["causal_verification_reported"] is None
    assert packet["evidence_read_only_observed"] is True


def test_exact_live_prompt_must_be_explicitly_given_for_comparison():
    task = json.loads(
        (ROOT / "tests/fixtures/homebrain_golden_tasks_v1.json").read_text()
    )["tasks"]
    exact = next(t["prompt"] for t in task if t["key"] == "causal_light2_off")
    record = extract_capture(
        response(), case_id="causal_light2_off",
        actual_question="\n " + exact + " \n", root=ROOT,
    )
    assert record["prompt_match"] == "exact"
    assert record["matches_registered_live_question"] is True
    altered = extract_capture(
        response(), case_id="causal_light2_off",
        actual_question=exact + " Also explain something else.", root=ROOT,
    )
    assert altered["prompt_match"] == "different"
    assert not altered["matches_registered_live_question"]


def test_offline_source_packet_is_not_equivalent_to_live_HomeBrain_question():
    curated = json.loads(
        (ROOT / "tests/fixtures/answer_quality_cases_v1.json").read_text()
    )["cases"][0]
    packet = extract_capture(
        response(), case_id=curated["id"],
        actual_question=curated["prompt"], root=ROOT,
    )
    assert packet["prompt_match"] == "exact"
    assert packet["case_origin"] == "offline_source_packet"
    assert packet["matches_registered_live_question"] is False


def test_empty_evidence_cannot_pass_even_the_read_only_observed_flag():
    item = response()
    item["evidence"] = []
    packet = extract_capture(
        item, case_id="status_named_dimmer", actual_question=None, root=ROOT,
    )
    assert packet["evidence_receipt_count"] == 0
    assert packet["evidence_read_only_observed"] is False


def test_mutation_in_evidence_is_visible_as_a_number_not_raw_command():
    item = response()
    item["evidence"][0]["mutates"] = True
    packet = extract_capture(
        item, case_id="status_named_dimmer", actual_question=None, root=ROOT,
    )
    assert packet["mutating_receipt_count"] == 1
    assert packet["evidence_read_only_observed"] is False
    assert "SECRET-" not in json.dumps(packet)


def test_missing_model_answer_is_invalid():
    item = response()
    item["message"] = None
    with pytest.raises(ScorecardInputError, match="string message"):
        extract_capture(
            item, case_id="causal_light2_off",
            actual_question=None, root=ROOT,
        )


def test_unknown_case_is_invalid():
    with pytest.raises(ScorecardInputError, match="Unknown benchmark"):
        extract_capture(
            response(), case_id="made_up_case", actual_question=None, root=ROOT,
        )


def test_opaque_or_secret_model_names_are_dropped():
    item = response()
    item["model"] = "gemma\ngive_me_a_token"
    item["version"] = "http://192.168.1.239/key"
    item["metrics"]["model_round_details"] = [
        {"provider": "SECRET-PRIVATE-PROVIDER"}
    ]
    packet = extract_capture(
        item, case_id="status_named_dimmer",
        actual_question=None, root=ROOT,
    )
    assert packet["model"] is None
    assert packet["add_on_version"] is None
    assert packet["provider"] is None


def test_cli_uses_private_input_and_generates_ungraded_metadata(tmp_path):
    input_path = tmp_path / "private-input.json"
    question_path = tmp_path / "question.txt"
    output_path = tmp_path / "capture.json"
    input_path.write_text(json.dumps(response()), encoding="utf-8")
    question_path.write_text(
        "Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.",
        encoding="utf-8",
    )
    assert main([
        "--case-id", "causal_light2_off",
        "--input", str(input_path),
        "--question-file", str(question_path),
        "--output", str(output_path),
    ]) == 0
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert packet["matches_registered_live_question"] is True
    assert packet["review"]["status"] == "pending_independent_source_review"
    assert "SECRET-" not in output_path.read_text(encoding="utf-8")
