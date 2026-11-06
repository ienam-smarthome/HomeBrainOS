"""Frozen Q2 historical metadata audit: never invent answer quality."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from answer_quality_fixed_packets import ScorecardInputError, build_fixed_packets
from answer_quality_q2_recorded_pairs import (
    ARCHIVE, audit_recorded_pairs, main,
)


def archive():
    return json.loads(ARCHIVE.read_text(encoding="utf-8"))


def test_actual_four_recorded_pairs_match_frozen_packets_without_scores():
    result = audit_recorded_pairs(archive())
    assert result["recorded_pairs"] == 4
    assert result["validated_frozen_packet_hash_pairs"] == 4
    assert result["recorded_checkout_sha_count"] == 4
    assert result["cross_session_builds_identical"] is False
    assert result["official_quality_measurement"] == "not_measured"
    assert result["reviewed_human_pairs"] == 0
    assert result["formal_accuracy_percentage"] is None
    assert result["observed_baseline_median_ms"] == 21508
    assert result["observed_candidate_median_ms"] == 8414
    assert result["observed_paired_candidate_minus_baseline_median_ms"] == -13781.5
    assert result["observed_candidate_faster_cases"] == 4
    assert all(item["human_review_grade"] is None for item in result["cases"])


def test_archive_is_private_answer_free_and_has_only_fixed_case_metadata():
    obj = archive()
    assert len(obj["pairs"]) == 4
    names = {p["case_id"] for p in obj["pairs"]}
    assert names <= {p["case_id"] for p in build_fixed_packets()}
    for p in obj["pairs"]:
        assert set(p) == {"case_id", "baseline", "candidate"}
        assert p["baseline"]["build_sha"] == p["candidate"]["build_sha"]
        assert p["baseline"]["attempt_index"] == p["candidate"]["attempt_index"] == 1
    report = json.dumps(audit_recorded_pairs(obj))
    for p in obj["pairs"]:
        for side in ("baseline", "candidate"):
            assert p[side]["answer_sha256"] not in report


def test_invalid_packet_digest_fails_closed():
    obj = archive()
    obj["pairs"][0]["candidate"]["packet_sha256"] = "f" * 64
    with pytest.raises(ScorecardInputError, match="source packet differs"):
        audit_recorded_pairs(obj)


def test_archived_metadata_must_not_contain_raw_answers_or_logs():
    obj = archive()
    obj["pairs"][0]["baseline"]["answer"] = "raw-private-model-answer"
    with pytest.raises(ScorecardInputError, match="metadata-only"):
        audit_recorded_pairs(obj)


def test_recorded_first_attempt_cannot_be_retroactively_changed():
    obj = archive()
    obj["pairs"][0]["candidate"]["attempt_index"] = 2
    with pytest.raises(ScorecardInputError, match="first attempts"):
        audit_recorded_pairs(obj)


def test_recorded_pair_must_share_checkout_but_cross_case_checkouts_may_differ():
    obj = archive()
    obj["pairs"][0]["candidate"]["build_sha"] = "e" * 40
    with pytest.raises(ScorecardInputError, match="one checkout SHA"):
        audit_recorded_pairs(obj)


def test_duplicate_recorded_case_is_not_counted_twice():
    obj = archive()
    obj["pairs"].append(copy.deepcopy(obj["pairs"][0]))
    with pytest.raises(ScorecardInputError, match="duplicate recorded"):
        audit_recorded_pairs(obj)


def test_wrong_case_id_is_not_treated_as_fixed_packet_match():
    obj = archive()
    obj["pairs"][0]["case_id"] = "aq_early_heating_off_resume"
    with pytest.raises(ScorecardInputError):
        audit_recorded_pairs(obj)


def test_same_model_comparison_is_not_a_model_ab_trial():
    obj = archive()
    obj["pairs"][0]["candidate"]["model"] = "qwen3.5:4b"
    with pytest.raises(ScorecardInputError, match="distinct model identities"):
        audit_recorded_pairs(obj)


def test_no_reviews_and_broken_archive_rejected():
    obj = archive()
    obj["pairs"] = []
    with pytest.raises(ScorecardInputError, match="Invalid recorded Q2 metadata"):
        audit_recorded_pairs(obj)


def test_cli_emits_only_descriptive_metadata(tmp_path):
    target = tmp_path / "audit.json"
    assert main(["--output", str(target)]) == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["recorded_pairs"] == 4
    assert result["reviewed_human_pairs"] == 0
    assert result["formal_accuracy_percentage"] is None
    assert result["timing_scope"] == "offline_model_request_only_not_homebrain_live_latency"
