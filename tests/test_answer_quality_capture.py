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
            {"tool": "hub_read_devices", "mutates": False, "effect": "read",
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


def test_undocumented_effect_is_not_treated_as_verified_read_only():
    item = response()
    del item["evidence"][0]["effect"]
    packet = extract_capture(
        item, case_id="status_named_dimmer", actual_question=None, root=ROOT,
    )
    assert packet["evidence_read_only_observed"] is False
    assert packet["read_only_classification_unknown_count"] == 1


def test_mutation_in_evidence_is_visible_as_a_number_not_raw_command():
    item = response()
    item["evidence"][0]["mutates"] = True
    packet = extract_capture(
        item, case_id="status_named_dimmer", actual_question=None, root=ROOT,
    )
    assert packet["mutating_receipt_count"] == 1
    assert packet["evidence_read_only_observed"] is False
    assert "SECRET-" not in json.dumps(packet)



def test_source_gaps_are_triaged_without_leaking_untrusted_labels():
    item = response()
    item["investigation_coverage"]["missingSourceKinds"] = [
        "command_history", "sensor_history", "command_history",
        "SECRET-IP-192.168.1.239-and-personal-room", {"private": "SECRET-OBJECT"},
    ]
    packet = extract_capture(
        item, case_id="causal_light2_off", actual_question=None, root=ROOT,
    )
    assert packet["source_gap_reporting"] == "provided"
    assert packet["missing_source_kind_count"] == 5
    assert packet["recognized_missing_source_kinds"] == ["command_history", "sensor_history"]
    assert packet["unclassified_missing_source_count"] == 2
    assert packet["source_packet_completeness"] == "not_independently_verified"
    assert "SECRET-" not in json.dumps(packet)
    assert "192.168" not in json.dumps(packet)


def test_zero_reported_gaps_does_not_claim_source_completeness():
    item = response()
    item["investigation_coverage"]["missingSourceKinds"] = []
    packet = extract_capture(
        item, case_id="device_mqtt_conflict", actual_question=None, root=ROOT,
    )
    assert packet["source_gap_reporting"] == "provided"
    assert packet["missing_source_kind_count"] == 0
    assert packet["recognized_missing_source_kinds"] == []
    assert packet["source_packet_completeness"] == "not_independently_verified"


def test_absent_or_invalid_gap_field_is_not_a_verified_empty_list():
    item = response()
    absent = extract_capture(
        item, case_id="causal_light2_off", actual_question=None, root=ROOT,
    )
    assert absent["source_gap_reporting"] == "not_provided"
    assert absent["missing_source_kind_count"] is None
    item["investigation_coverage"]["missingSourceKinds"] = "SECRET-PRIVATE-GAP"
    invalid = extract_capture(
        item, case_id="causal_light2_off", actual_question=None, root=ROOT,
    )
    assert invalid["source_gap_reporting"] == "not_provided"
    assert invalid["missing_source_kind_count"] is None
    assert "SECRET-PRIVATE-GAP" not in json.dumps(invalid)


def test_real_response_nested_source_coverage_does_not_look_absent():
    item = response()
    item["metrics"]["counters"]["synthesis_repair_failed"] = 1
    item["investigation_coverage"].update({
        "status": "partial-evidence",
        "evidenceComplete": False,
        "sourceChecksComplete": True,
        "sourceIntegrityWarnings": ["SECRET-PRIVATE-EVENT-HISTORY-DETAIL"],
        "sourceCoverage": {
            "missingSourceKinds": [],
            "sourceKindsChecked": True,
        },
    })
    packet = extract_capture(
        item, case_id="causal_light2_off", actual_question=None, root=ROOT,
    )
    assert packet["source_gap_reporting"] == "provided"
    assert packet["missing_source_kind_count"] == 0
    assert packet["source_checks_complete_reported"] is True
    assert packet["source_kinds_checked_reported"] is True
    assert packet["evidence_complete_reported"] is False
    assert packet["source_integrity_warning_count"] == 1
    assert packet["synthesis_repair_failed_reported"] == 1
    assert packet["source_packet_completeness"] == "not_independently_verified"
    assert "SECRET-" not in json.dumps(packet)


def test_nested_missing_kinds_are_allowlisted_and_deduplicated():
    item = response()
    item["investigation_coverage"]["sourceCoverage"] = {
        "missingSourceKinds": [
            "app_logs", "device_history", "app_logs",
            "SECRET-HOUSEHOLD-NAME", {"private": "SECRET-NESTED"},
        ]
    }
    packet = extract_capture(
        item, case_id="device_mqtt_conflict", actual_question=None, root=ROOT,
    )
    assert packet["source_gap_reporting"] == "provided"
    assert packet["missing_source_kind_count"] == 5
    assert packet["recognized_missing_source_kinds"] == ["app_logs", "device_history"]
    assert packet["unclassified_missing_source_count"] == 2
    assert "SECRET-" not in json.dumps(packet)


def test_conflicting_top_level_and_nested_source_gap_reports_fail_closed():
    item = response()
    item["investigation_coverage"]["missingSourceKinds"] = []
    item["investigation_coverage"]["sourceCoverage"] = {
        "missingSourceKinds": ["SECRET-PRIVATE-GAP"]
    }
    packet = extract_capture(
        item, case_id="causal_light2_off", actual_question=None, root=ROOT,
    )
    assert packet["source_gap_reporting"] == "conflicting"
    assert packet["missing_source_kind_count"] is None
    assert packet["recognized_missing_source_kinds"] == []
    assert "SECRET-PRIVATE-GAP" not in json.dumps(packet)


def test_missing_nested_metadata_is_not_false_or_zero():
    item = response()
    packet = extract_capture(
        item, case_id="causal_light2_off", actual_question=None, root=ROOT,
    )
    assert packet["source_checks_complete_reported"] is None
    assert packet["source_kinds_checked_reported"] is None
    assert packet["evidence_complete_reported"] is None
    assert packet["source_integrity_warning_count"] is None
    assert packet["synthesis_repair_failed_reported"] is None


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
